# remote-job-pipeline

An automated ETL pipeline that collects **remote Data Engineer / ETL Developer**
job postings, filters them for candidates who can realistically apply **from
Indonesia** at an **early-career level (under 3 years of experience)**, and
serves them for semantic + filtered search by an AI agent.

```text
GitHub Actions (cron) → APIs (RemoteOK, Remotive, Himalayas, JSearch)
   → Cloudflare R2 (raw lake) → transform + dedup → embed (bge-small-en-v1.5)
   → Supabase (PostgreSQL + pgvector) → search_jobs() hybrid search
   → Discord (monitoring)
```

Full design rationale lives in [`docs/architecture.md`](docs/architecture.md)
and [`docs/decisions.md`](docs/decisions.md) (25 ADRs). Deployment steps are
in [`docs/deployment.md`](docs/deployment.md).

## Why this exists

Most "remote job aggregator" side projects stop at "fetch an API and show a
list". This one exists to show the parts of data engineering that portfolio
tutorials usually skip:

- **A real, narrow filtering problem** — most remote postings that say
  "Remote" do not actually specify whether Indonesia-based candidates can
  apply. The eligibility classifier (`transform/eligibility.py`) is a
  tri-state, evidence-backed decision (`eligible` / `restricted` /
  `unknown`), not a guess.
- **An explicit failure contract** — extractors raise instead of silently
  returning nothing; a quota-limited source (JSearch) degrades gracefully
  instead of taking the whole run down.
- **Idempotency by construction** — deterministic job IDs, upserts, and a
  deterministic dedup winner mean re-running the pipeline never duplicates
  or corrupts data.
- **Measured, not assumed, accuracy** — `scripts/evaluate.py` reports
  precision/recall against hand-labeled examples in `tests/labeled/`.

## Quickstart

```bash
git clone <this-repo>
cd remote-job-pipeline
cp .env.example .env      # fill in your own credentials, see docs/deployment.md
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

make lint test             # ruff + 60 unit tests
make dry-run                # extract + transform locally, no writes
python scripts/evaluate.py eligibility
python scripts/evaluate.py role
```

Full setup (Supabase, Cloudflare R2, RapidAPI, Discord, GitHub Actions) is
in [`docs/deployment.md`](docs/deployment.md).

## How a job is decided

```text
raw posting
  → recency filter (last 7 days)
  → role filter        (core: Data Engineer/ETL Developer, or adjacent; else dropped)
  → seniority filter    (senior titles dropped; 3+ years required dropped, no exceptions)
  → eligibility filter  (eligible/restricted/unknown — unknown is KEPT, not dropped)
  → salary parsing       (optional enrichment only, never a filter)
  → tech stack extraction
  → dedup                (keep the most complete record across sources)
  → embed + store
```

A posting is only ever dropped for being **too old**, **not a Data
Engineering role**, **senior / requiring 3+ years**, or **a losing
duplicate**. It is never dropped for missing salary or for ambiguous
location wording — see `docs/decisions.md` ADR-006.

## Project layout

```text
src/rjp/
├── main.py              orchestrator: guard clauses, exit codes
├── config.py            all environment variables, read once
├── exceptions.py        ExtractionError / PartialExtractionError contract
├── models.py            SourceResult, RunSummary, EligibilityResult, RoleDecision
├── extract/             RemoteOK, Remotive, Himalayas, JSearch (quota-aware)
│   └── experimental/    Glints (Selenium) — disabled by default, ADR-022
├── transform/           cleaning, normalization, role/seniority, eligibility,
│                        salary, tech stack, dedup — all pure functions
├── embed/               bge-small-en-v1.5 template + encoder
├── load/                Cloudflare R2 (raw lake) + Supabase (serving)
├── monitoring/          Discord notifications (green/yellow/red embeds)
├── utils/               HTTP retry, quota budgeting, logging, FX rates
└── resources/           editable YAML/text pattern dictionaries

sql/            6 migrations: extensions, schema, indexes, search RPC, retention, roles
scripts/        apply_sql, run_local, reprocess_from_r2, evaluate, sample_search
tests/          60 unit tests + 1 integration test (idempotency, opt-in)
docs/           architecture, 25 ADRs, deployment guide, data model, evaluation
```

## Testing

```bash
pytest tests/unit -q               # 60 tests, pure logic, no network or credentials needed
RUN_INTEGRATION_TESTS=1 pytest tests/integration -q   # needs live Supabase/R2/RapidAPI credentials
```

Coverage highlights: strict seniority cutoff edge cases (`"2-3 years"` kept,
`"3+ years"` dropped, spelled-out numbers, ceilings vs. minimums), the
`\b`-bounded salary keyword matching (`"Corporate"` never triggers
`"rate"`), eligibility conflict/negation handling, deterministic dedup
winner selection, and the per-job transform safety guard (a `None` or
malformed job never crashes the run).

## Key design decisions

See [`docs/decisions.md`](docs/decisions.md) for the full list. A few worth
highlighting:

- **ADR-005/006** — eligibility is tri-state; ambiguity resolves to
  `unknown`, which is *kept*, never dropped.
- **ADR-009** — seniority cutoff is strict: any stated requirement of 3+
  years drops the posting, with no "stretch" tier.
- **ADR-010** — duplicates across sources are resolved by keeping the
  single most complete record, chosen by a deterministic order (so re-runs
  never flip the winner).
- **ADR-021/022** — JSearch's tight free quota degrades gracefully instead
  of crashing the pipeline; Selenium-based scraping is out of the default,
  scheduled run.
- **ADR-025** — the raw lake runs on Cloudflare R2, not Google Cloud
  Storage, specifically to avoid a dependency on a Google Cloud billing
  account (a real constraint hit while building this).

## Status

MVP stage: the pipeline connects to Supabase with the admin credential
rather than the least-privilege `pipeline_writer` / `agent_readonly` roles
in `sql/006_roles.sql` (ADR-024). Apply that migration and switch
credentials **before** connecting any AI agent — see
[`docs/databricks_roadmap.md`](docs/databricks_roadmap.md).

## License

MIT — see [`LICENSE`](LICENSE).
