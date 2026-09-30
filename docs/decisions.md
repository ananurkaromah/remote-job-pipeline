# Design Decisions

Architecture Decision Records (ADR) for `remote-job-pipeline`. Each entry states the context, the decision, and its consequences. Values marked *tunable* are starting points to be validated against the labeled sets in `tests/labeled/`.

Status legend: **Accepted** (agreed), **Tunable** (accepted, threshold to be validated).

---

## ADR-001: Use APIs and feeds first; do not scrape LinkedIn

- **Status:** Accepted (2026-09-28)
- **Context:** LinkedIn has no public job-search API for individual developers. Scraping conflicts with its User Agreement, risks account restrictions, and is blocked quickly on datacenter IPs such as GitHub Actions runners. A public repository containing such a scraper also signals weak compliance awareness.
- **Decision:** Prioritize official APIs and public feeds (RemoteOK, Remotive, Himalayas, JSearch). Coverage of LinkedIn-originated postings comes indirectly through the JSearch aggregator, recorded in `origin_portal`. Regional scrapers (Glints, Jobstreet) come last and only if their terms allow it.
- **Consequences:** More stable and compliant pipeline; coverage depends on API quotas. New sources can be added as extractors without changing the pipeline. A "Data Sources & Compliance" document explains the choice.

## ADR-002: Keep the raw lake unfiltered

- **Status:** Accepted
- **Context:** API quotas are small. Filtering rules will change while they are being tuned.
- **Decision:** Store raw payloads in Cloudflare R2 exactly as extracted, partitioned by date. All filtering happens after the raw write, in the transform stage. Rejected records are stored separately with reason codes.
- **Consequences:** Rules can be changed and data reprocessed with `scripts/reprocess_from_r2.py` without new API calls. Storage grows slightly; a lifecycle rule can expire old partitions.

## ADR-003: Extractors raise; an empty list means "no data"

- **Status:** Accepted
- **Context:** An extractor that swallows errors and returns `[]` makes a broken source look like a quiet day.
- **Decision:** Extractors raise `ExtractionError(source, reason)` on any failure, including changed response shapes. `extract_all_sources()` collects one `SourceResult` per source. Only the orchestrator interprets an empty list, and it does so as "no data", not "failure".
- **Consequences:** Every failure names its source and reason. Partial failures continue with a warning; total failure exits with code 1.

## ADR-004: Guard clauses and neutral warning wording for empty results

- **Status:** Accepted
- **Context:** Calling `load_raw_to_r2([])` and `load_to_supabase([])` is wasteful, and a message such as "ran successfully" hides suspicious empty runs.
- **Decision:** Return early when there are no raw jobs or no survivors after filtering. Notify with warning wording ("verify this is expected"). Never overwrite an existing good raw file with an empty or partial result.
- **Consequences:** Repeated warnings become a signal for manual inspection. Slightly more branching in `main.py`, covered by tests.

## ADR-005: Tri-state eligibility with evidence

- **Status:** Accepted
- **Context:** The core value of the project is finding roles open to Indonesia. A binary flag forces a guess on ambiguous postings, and a wrong drop is invisible to the user.
- **Decision:** `eligibility_status` is `eligible`, `restricted`, or `unknown`, stored with a confidence level and the matching evidence snippets. Evidence sources are ranked: structured API fields, then title and tags, then description regex. Conflicting signals produce `unknown`. `is_eligible_for_id` remains as a generated boolean (`status = 'eligible'`).
- **Consequences:** Decisions are auditable. Only clearly restricted postings are excluded by default; the default search view is `eligible + unknown`. Timezone overlap is stored as `timezone_hint` and never changes the status. Accuracy is measured on a labeled set, with `eligible` precision as the primary metric.

## ADR-006: Prefer false splits over false merges, and unknown over false drops

- **Status:** Accepted
- **Context:** A single missing valid job is worse than one extra row.
- **Decision:** Ambiguity resolves toward keeping data: `unknown` eligibility is kept, neutral job titles without stated years are kept, and dedup thresholds are conservative.
- **Consequences:** Some noise remains in results. This is accepted and monitored through the unknown rate and duplicate counts.

## ADR-007: Salary is optional enrichment, never a filter

- **Status:** Accepted
- **Context:** Most postings do not disclose salary. Requiring it would discard most of the data.
- **Decision:** Salary fields are nullable, with `salary_status` in `disclosed`, `partial`, `not_disclosed`, `unparsed`. `NULL` means unknown, never zero. Original text is kept in `salary_raw`. Undisclosed salary is omitted from the embedding text. Salary filtering in search keeps undisclosed jobs by default (`include_undisclosed = true`).
- **Consequences:** No job is dropped for missing salary. The parser is built late, supports common patterns only, and is conservative. Keyword matching uses `\b` word boundaries with a 30-character look-back so that "Corporate" does not trigger "rate".

## ADR-008: Role scope: Data Engineer and ETL Developer, junior level only

- **Status:** Accepted
- **Context:** The target is early-career candidates (under 3 years of experience) in data engineering.
- **Decision:** Titles are normalized and classified as `core` (Data Engineer, ETL Developer/Engineer), `adjacent` (Analytics Engineer, Data Warehouse Developer, Big Data Developer, Data Pipeline/Integration/Platform Engineer), or excluded (Data Scientist, Data Analyst, BI Analyst, ML Engineer, DBA, generic Software Engineer, Data Architect, management roles). Both `core` and `adjacent` are stored and labeled. Internships are dropped by default (configurable).
- **Consequences:** Results are focused. The keyword lists live in `resources/` so they can be tuned without code changes.

## ADR-009: Seniority rules: title keywords, years from description, strict 3+ cutoff

- **Status:** Accepted (2026-09-28)
- **Context:** Senior roles must be excluded, but keywords in descriptions ("senior stakeholders") are misleading.
- **Decision:**
  - Seniority keywords (senior, sr, lead, staff, principal, head, manager, director, architect, III, IV) are checked only in the **title**.
  - Junior keywords (junior, jr, entry level, associate, graduate, trainee) keep the job.
  - For neutral titles, required years are parsed from the description and the **largest lower bound** is used. A minimum of **3 or more years is dropped strictly**; `2-3 years` is kept because its lower bound is 2.
  - "Preferred", "nice to have", "a plus", and ceilings such as "up to 3 years" are not requirements. Spelled-out numbers ("three years") are parsed.
  - Neutral titles with no years stay as `unknown` level and are kept.
- **Consequences:** Predictable, testable behavior with no "stretch" tier. `MAX_YEARS_REQUIRED_EXCLUSIVE = 3` is configurable.

## ADR-010: Deduplicate by keeping the most complete record

- **Status:** Accepted (2026-09-28)
- **Context:** The same job often appears on several sources.
- **Decision:** Cluster duplicates using canonical URL, exact `company_norm + title_norm`, then fuzzy title match plus description similarity. Choose one winner per cluster and discard the others without merging fields. The winner is chosen by a deterministic total order: completeness score, source priority, most recent `posted_at`, then `job_id`. Description checks prevent merging same-title roles in different regions.
- **Consequences:** Simple and explainable. Field merging (for example taking salary from a losing record) is deferred; completeness weights already favor records with salary and clear eligibility. Losers are written to `rejected-data/` with `duplicate_of` for audit. Thresholds are *tunable*.

## ADR-011: Dedup runs after transform, before embedding, over batch plus existing window

- **Status:** Accepted
- **Context:** Dedup needs normalized fields, and embeddings cost compute. A more complete version of a job may arrive after an older version is stored.
- **Decision:** Cluster the new batch together with existing rows in the 7-day window, in memory. Replacing a stored row with a different winner deletes the old row and upserts the new one in one transaction.
- **Consequences:** No embedding cost for discarded records; data converges to the most complete version over time.

## ADR-012: Recency window of 7 days

- **Status:** Accepted
- **Context:** The project only cares about fresh postings.
- **Decision:** Drop postings older than 7 days at transform, filter by `posted_at >= now() - 7 days` in search, and remove expired rows at the end of each run.
- **Consequences:** The database stays small, which fits free tiers. Postings with a missing `posted_at` are treated as posted at extraction time (a documented assumption that should be reviewed once real data is seen).

## ADR-013: Embedding model `bge-small-en-v1.5` with a structured text template

- **Status:** Accepted
- **Context:** A free, local, small model is needed that works well for English retrieval.
- **Decision:** Use `BAAI/bge-small-en-v1.5` (384 dimensions) with a template of Title, Company, Remote Policy, Tech Stack, Salary (if disclosed), and Description. Queries use the retrieval instruction prefix; documents do not. The embedded text is stored for debugging.
- **Consequences:** No embedding API cost and a compact vector column. English-only; Indonesian-language postings will embed less well. Changing the model requires re-embedding (possible from the raw lake).

## ADR-014: Supabase PostgreSQL with pgvector and an in-database hybrid search function

- **Status:** Accepted
- **Context:** The agent needs SQL filters (eligibility, skills, salary, recency) and semantic ranking together.
- **Decision:** Store metadata and the vector in one `jobs` table, index the vector with HNSW (cosine), and expose a `search_jobs()` SQL function. Default eligibility levels are `{eligible, unknown}`.
- **Consequences:** One query serves the agent. Free-tier limits apply (storage, inactivity pause); a scheduled run keeps the project active. Because it is plain Postgres, the layer is portable to Lakebase.

## ADR-015: Idempotency by construction

- **Status:** Accepted
- **Context:** The pipeline runs on a schedule and must be safe to re-run.
- **Decision:** Deterministic `job_id`, upsert with `ON CONFLICT`, overwrite-by-partition R2 writes, deterministic dedup ordering, no overwriting of good files with empty results, and a GitHub Actions `concurrency` group with `cancel-in-progress: false`.
- **Consequences:** Re-running any day converges to the same state, verified by an integration test that runs the pipeline twice.

## ADR-016: Per-job transform isolation with a failure threshold

- **Status:** Accepted (threshold *tunable*)
- **Context:** One malformed job must not stop a run, but widespread failures signal a real problem.
- **Decision:** Wrap each job in `try/except`. Compute the error label only after `isinstance(job, dict)` so a `None` job cannot raise inside the handler. Log `X/Y job(s) failed transformation and were skipped` and add the skipped count to the Discord message. Treat a run as failed if more than about 30% of jobs fail.
- **Consequences:** Partial failures stay visible in monitoring rather than buried in detailed logs.

## ADR-017: Three-level Discord monitoring with exit codes

- **Status:** Accepted
- **Context:** Success, partial failure, and total failure need different reactions.
- **Decision:** Send success, warning, and failure messages from a single `RunSummary`. Exit code 1 only on total failure, so the GitHub Actions run turns red only when it should. Notification code never raises and uses a short timeout.
- **Consequences:** Monitoring can never take the pipeline down, and partial failures are still visible. Discord embeds use green, yellow, and red so urgency is readable without opening the message.

## ADR-018: Package as a Docker image; Chrome is optional

- **Status:** Accepted (Chrome default *tunable*); Selenium scope narrowed by ADR-022
- **Context:** The pipeline should run identically locally and in GitHub Actions. Chrome makes the image large and slow to build, and the Selenium scraper is a last-priority source.
- **Decision:** Provide a `Dockerfile` with an `INSTALL_CHROME` build argument (default `false`). Pre-download the embedding model at build time. GitHub Actions runs `docker build && docker run` instead of installing dependencies on the runner.
- **Consequences:** Faster default builds and a reproducible environment. Building with `--build-arg INSTALL_CHROME=true` enables the scraper when needed. The model cache is pinned with `HF_HOME` inside the image and `HF_HUB_OFFLINE=1` is set at runtime, so a missing model fails immediately instead of triggering a slow download.

## ADR-019: Resources separated from code

- **Status:** Accepted
- **Context:** Regex patterns, skill aliases, and country lists change often while rules are being tuned.
- **Decision:** Keep patterns and dictionaries in `src/rjp/resources/` (YAML and text files) and keep transform functions pure.
- **Consequences:** Rule changes are small, reviewable diffs, and tests can load the same files as production.

## ADR-020: Evaluation is part of the deliverable

- **Status:** Accepted
- **Context:** Claims such as "filters for Indonesia" are only credible with measurement.
- **Decision:** Maintain hand-labeled sets (eligibility about 100-150 rows, role about 100, dedup about 50 pairs including hard negatives) and a script that reports precision, recall, and confusion matrices. Key metrics: precision of `eligible`, recall of `restricted`, recall of relevant roles, precision of dedup merges, and the unknown-eligibility rate.
- **Consequences:** Rule changes are validated before merging, and the README can publish real numbers.

## ADR-021: Quota-aware sources with graceful degradation

- **Status:** Accepted (2026-09-28)
- **Context:** JSearch (RapidAPI) has a tight free-tier quota. A naive extractor would either exhaust it in a few runs or turn an HTTP 429 into a pipeline crash.
- **Decision:** Quota-limited extractors enforce a per-run request cap, can be limited to selected weekdays, and read remaining-quota headers when the provider exposes them. A source can end a run as `ok`, `skipped` (intentional: not scheduled, below reserve, or already extracted today according to the R2 run envelope), `degraded` (partial data kept after `PartialExtractionError`), or `failed`. Only the failure of all sources is fatal.
- **Consequences:** An exhausted quota produces a Discord warning, never a crash. Manual re-runs on the same day do not consume quota again. The extractor contract gains one exception type (`PartialExtractionError`) that carries the jobs collected before the failure. The exact cap and schedule are *tunable* and depend on the plan's real quota.

## ADR-022: Keep Selenium out of the default pipeline

- **Status:** Accepted (2026-09-28)
- **Context:** Installing Chrome and ChromeDriver in the Docker image on a free GitHub Actions runner adds build time and resource use, headless scrapers break often, and regional portals may restrict scraping in their terms.
- **Decision:** The default registry contains only clean API and feed sources: RemoteOK, Remotive, Himalayas, and quota-aware JSearch. `glints.py` moves to `extract/experimental/` and stays disabled unless `ENABLE_SELENIUM_SOURCES=true`. Selenium becomes an optional dependency (`requirements-optional.txt`), and `INSTALL_CHROME` stays `false` for scheduled runs. If a scraper is ever needed it runs locally or in a separate manual workflow, and only after checking the portal's terms.
- **Consequences:** Faster, smaller, more reliable scheduled runs. Less regional coverage of Indonesian portals, which is accepted for the MVP and can be revisited later without changing the pipeline, because extractors are pluggable.

## ADR-023: Off-peak schedule and silence treated as a signal

- **Status:** Accepted (2026-09-28)
- **Context:** GitHub delays or drops scheduled runs at peak times such as the top of the hour, and may disable scheduled workflows in inactive public repositories. A stopped schedule also lets the Supabase free-tier project become inactive.
- **Decision:** Schedule the cron at 02:30 UTC (09:30 WIB) instead of at the top of the hour. Treat the absence of Discord messages for more than two days as an alert to check the Actions tab, and set a personal calendar reminder (about every 45 days) to confirm the schedule is still enabled. Do not use automated dummy commits as a keepalive.
- **Consequences:** More reliable execution and a manual, low-cost safety net without extra infrastructure. If this proves insufficient, an external heartbeat monitor can be added later.

## ADR-025: Raw data lake on Cloudflare R2 instead of Google Cloud Storage

- **Status:** Accepted (2026-09-29)
- **Context:** Google Cloud Storage's free tier still sits behind a Google Cloud billing account, which requires a payment method. The developer's billing account was suspended due to an unrelated earlier project, blocking GCS setup entirely and making the raw-data layer dependent on something outside this project's control.
- **Decision:** Replace Google Cloud Storage with Cloudflare R2 as the raw data lake. R2 is S3-compatible, so the pipeline accesses it with the standard `boto3` client instead of a Google-specific SDK. The `load/gcs.py` module becomes `load/r2.py`; the partition layout (`raw-data/year=YYYY/month=MM/day=DD/jobs.json`), the run envelope, the overwrite-by-partition rule, and the rejected-records path are unchanged, since storage was already isolated in its own module (ADR-002).
- **Consequences:** No billing account or credit card is needed for the free tier (10 GB storage, no egress fees), and setup no longer depends on `gcloud` or a Google Cloud service account. `GOOGLE_APPLICATION_CREDENTIALS` and the `GCP_SA_KEY` GitHub secret are removed; an R2 API token (`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ACCOUNT_ID`, `R2_BUCKET`) is used instead. Because storage stayed isolated in its own module, the rest of the pipeline (transform, dedup, embed, serve) is unaffected. If a future need for GCS-specific features arises, the same module boundary allows switching back without touching other layers.

## ADR-024: Least-privilege database roles for the pipeline and the AI agent

- **Status:** Accepted (2026-09-28)
- **Context:** The AI agent runs hybrid search, possibly from another platform such as Databricks, and is a larger attack surface than a batch job. Supabase also exposes public tables through its REST API by default.
- **Decision:** Create `pipeline_writer` (read/write on `jobs`) and `agent_readonly` (select and `search_jobs()`, read-only transactions, statement timeout). Enable row-level security on `jobs` with explicit policies, and revoke access from `anon` and `authenticated`. Keep the admin credential on the developer's machine for migrations only. Role passwords are set manually and never committed.
- **Consequences:** A compromised or misbehaving agent cannot modify or delete data. Slightly more setup (`sql/006_roles.sql`, separate secrets), and the RLS policies must be kept in sync with new tables or columns.
