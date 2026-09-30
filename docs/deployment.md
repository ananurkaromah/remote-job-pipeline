# Deployment Guide

How to deploy `remote-job-pipeline` so that it runs unattended on GitHub Actions, writes raw data to Cloudflare R2, and serves the processed data from Supabase.

> Status: written ahead of implementation. Script and module names follow the repository layout in the README. Free-tier limits and console menus change over time, so verify anything marked *(verify)* against the provider's current documentation.
>
> **Why R2, not Google Cloud Storage:** GCS's free tier still requires a Google Cloud billing account with a payment method attached, and a billing account can be suspended for reasons unrelated to this project (see ADR-025), taking the pipeline down with it. Cloudflare R2 needs no billing account or credit card for its free tier and is S3-compatible, so the same `boto3` client and partition layout apply.

## 1. Overview

```text
GitHub Actions (cron, UTC)
   -> docker build && docker run
        -> APIs (RemoteOK, Remotive, ...)
        -> Cloudflare R2  (raw lake)
        -> Supabase PostgreSQL + pgvector  (serving)
        -> Discord webhook  (monitoring)
```

Deployment order matters: create the external services first, test locally, then configure GitHub.

| Step | What | Where |
|---|---|---|
| 1 | Supabase project and schema | Supabase |
| 2 | R2 bucket and API token | Cloudflare |
| 3 | Discord webhook | Discord |
| 4 | API keys | RapidAPI (if JSearch is enabled) |
| 5 | Local dry run | WSL / local machine |
| 6 | Secrets and workflow | GitHub |
| 7 | First run and verification | GitHub Actions |

## 2. Prerequisites

- GitHub account and the repository (public or private)
- Cloudflare account (free; no credit card required for R2's free tier) *(verify)*
- Supabase account
- Discord server where you can create a webhook
- Local tools: Python 3.12, Docker, `git`, `boto3`, and the GitHub CLI (`gh`)

## 3. Supabase (database)

1. Create a new Supabase project. Choose a region close to where the pipeline runs and save the database password.
2. Enable `pgvector` (Dashboard: Database, Extensions, `vector`). The migration in `sql/001_extensions.sql` also runs `CREATE EXTENSION IF NOT EXISTS vector;`.
3. Get the **Postgres connection string** (Dashboard: Connect). GitHub-hosted runners are IPv4-only, and Supabase's direct connection is IPv6 by default on the free tier, so use the **pooler (Supavisor) connection string** in the workflow *(verify)*. Session mode is the safest choice for the upsert and transaction logic.
4. Apply the migrations in order:

```bash
export SUPABASE_DB_URL="postgresql://postgres.<project-ref>:<password>@<pooler-host>:5432/postgres"
python scripts/apply_sql.py        # runs sql/001 ... 005 in order
```

5. Verify:

```sql
SELECT extname FROM pg_extension WHERE extname = 'vector';
SELECT count(*) FROM jobs;          -- expect 0 on a fresh database
```

6. Create least-privilege roles for the pipeline and for the AI agent (see **Database roles** below). The agent must never use the pipeline's write credentials.

> **MVP note:** role separation is deferred until an AI agent actually needs read access to this database. Until then, `SUPABASE_DB_URL` in `.env` and in the GitHub secret uses the **admin (`postgres`) connection string** directly. This is acceptable because, at this stage, nothing but the pipeline itself touches the database. Before connecting any AI agent, dashboard, or downstream app to `search_jobs()`, come back to this section and create `pipeline_writer` / `agent_readonly` first — do not hand the agent the admin string "temporarily".

**Free-tier notes** *(verify)*: storage is limited (around 500 MB) and inactive projects can be paused. A scheduled daily run keeps the project active. The 7-day retention keeps the table small.

### Database roles (least privilege)

Do not run the pipeline or the AI agent with the project's admin (`postgres`) credentials. Create two limited roles in `sql/006_roles.sql`. The file contains **no passwords**.

```sql
CREATE ROLE pipeline_writer LOGIN;
CREATE ROLE agent_readonly  LOGIN;

-- Supabase exposes public tables through its REST API by default (verify).
-- Lock the table down, then grant access explicitly.
REVOKE ALL ON jobs FROM PUBLIC, anon, authenticated;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

GRANT USAGE ON SCHEMA public TO pipeline_writer, agent_readonly;
GRANT SELECT, INSERT, UPDATE, DELETE ON jobs TO pipeline_writer;   -- DELETE: retention and dedup
GRANT SELECT ON jobs TO agent_readonly;
GRANT EXECUTE ON FUNCTION search_jobs TO agent_readonly;

-- With RLS enabled, roles need explicit policies or they see zero rows
CREATE POLICY pipeline_all ON jobs FOR ALL    TO pipeline_writer USING (true) WITH CHECK (true);
CREATE POLICY agent_select ON jobs FOR SELECT TO agent_readonly  USING (true);

-- Guard rails for the agent
ALTER ROLE agent_readonly SET default_transaction_read_only = on;
ALTER ROLE agent_readonly SET statement_timeout = '10s';
```

If the `vector` extension lives in a schema other than `public` (for example `extensions`), also grant `USAGE` on that schema to both roles so the vector operators resolve *(verify)*.

Set passwords manually and never commit them:

```sql
ALTER ROLE pipeline_writer PASSWORD '<generated-password>';
ALTER ROLE agent_readonly  PASSWORD '<generated-password>';
```

How each credential is used:

| Credential | Used by | Stored in |
|---|---|---|
| Admin (`postgres`) connection string | `scripts/apply_sql.py` migrations, run by you | Your local machine only, **not** in GitHub secrets |
| `pipeline_writer` | The pipeline container | GitHub secret `SUPABASE_DB_URL` |
| `agent_readonly` | The AI agent or downstream app | The agent's own secret store (for example a Databricks secret scope), never in this repository |

With the pooler, the username usually carries the project reference (for example `agent_readonly.<project-ref>`) *(verify the exact format in the Supabase dashboard)*.

Verify the separation, connected as `agent_readonly`:

```sql
SELECT count(*) FROM jobs;   -- works
DELETE FROM jobs;            -- must fail with "permission denied"
```

Also confirm the REST API cannot read the table with the public anon key.


## 4. Cloudflare R2 (raw lake)

R2 is Cloudflare's S3-compatible object storage. Its free tier (10 GB storage, no egress fees) needs **no billing account and no credit card**, which is why it replaces Google Cloud Storage here (ADR-025).

### Create the bucket

1. Log in to the Cloudflare dashboard and open **R2 Object Storage**. Enabling R2 for the account may ask for a one-time identity check, but does not require adding a payment method for usage within the free tier *(verify, since Cloudflare's onboarding flow can change)*.
2. Create a bucket, for example `rjp-raw-<your-suffix>`. R2 buckets are not tied to a specific region the way GCS buckets are *(verify current behavior)*.
3. Leave public access disabled. The bucket is only read and written by the pipeline through the API, never served directly to browsers.
4. Optional lifecycle rule: under the bucket's **Settings → Object lifecycle rules**, add a rule to delete objects older than, for example, 90 days, to bound storage growth from `raw-data/`.

### Create an API token scoped to this bucket

1. In R2, go to **Manage R2 API Tokens** and create a new token.
2. Choose **Create Account API Token**, not a User API token. An account token stays valid regardless of your personal login status; a user token becomes inactive if that Cloudflare user is ever removed, which would silently break the scheduled pipeline *(verify this distinction against Cloudflare's current documentation, since token management UIs change)*.
3. Set permissions to **Object Read & Write**, and scope it to the single bucket created above rather than to all buckets on the account.
4. Copy the three values shown once: **Access Key ID**, **Secret Access Key**, and the account's **R2 endpoint** (of the form `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`). Store them as GitHub secrets in section 10; they cannot be viewed again after this screen closes, only regenerated.

### Credentials for GitHub Actions

Unlike GCS, there is only one path here, and it needs no key file:

```bash
gh secret set R2_ACCOUNT_ID
gh secret set R2_ACCESS_KEY_ID
gh secret set R2_SECRET_ACCESS_KEY
gh secret set R2_BUCKET
```

The pipeline's `load/r2.py` uses these with the standard `boto3` S3 client (see section 9's `requirements.txt`), pointed at the R2 endpoint:

```python
import boto3

client = boto3.client(
    "s3",
    endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name="auto",
)
```

No JSON key file is written to disk, so there is nothing to `rm` after use and nothing to mount into the container. Rotate the token periodically from the same dashboard screen (revoke the old one after the new one is confirmed working).

## 5. Discord webhook

1. In your Discord server: Server Settings, Integrations, Webhooks, New Webhook.
2. Choose the channel for pipeline notifications and copy the webhook URL.
3. Treat the URL as a secret. Anyone with it can post to the channel.

Quick test:

```bash
curl -H "Content-Type: application/json" \
  -d '{"content": "remote-job-pipeline: webhook test"}' "$DISCORD_WEBHOOK_URL"
```

## 6. API keys

- **RemoteOK, Remotive, Himalayas:** no key needed for the public endpoints. Check each site's terms and attribution requirements.
- **JSearch (RapidAPI):** create a RapidAPI account, subscribe to the free plan, and copy the key. The free quota is small *(verify the current limit on your plan)*, so JSearch is quota-aware (see `docs/architecture.md`, section 3.2.1). Set `JSEARCH_MAX_REQUESTS_PER_RUN`, `JSEARCH_RUN_DAYS`, and `JSEARCH_QUOTA_RESERVE` so that the monthly total stays below your plan's quota. When the quota runs out, the run continues with the other sources and sends a Discord warning instead of failing. Re-running the workflow on the same day does not call JSearch again if today's data is already in the raw lake.

## 7. Environment variables

`.env.example`:

```dotenv
# Sources
RAPIDAPI_KEY=

# Storage (Cloudflare R2, S3-compatible; no billing account needed)
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=

# Serving (pipeline_writer role; never the admin or agent credential)
SUPABASE_DB_URL=

# Monitoring
DISCORD_WEBHOOK_URL=

# Behavior
WINDOW_DAYS=7
TRANSFORM_FAILURE_THRESHOLD=0.30

# Quota-aware sources — plan: 200 requests/month, 1000 requests/hour rate limit
JSEARCH_MAX_REQUESTS_PER_RUN=3       # 3 queries/run stays well within the monthly quota
JSEARCH_RUN_DAYS=MON,THU             # days JSearch is called; otherwise it is skipped
JSEARCH_QUOTA_RESERVE=10             # stop calling when remaining quota falls below this

# Selenium is out of the default pipeline
ENABLE_SELENIUM_SOURCES=false
INSTALL_CHROME=false
```

Copy it to `.env` for local runs. `.env` must be listed in `.gitignore` and `.dockerignore`.

## 8. Local verification (before GitHub)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

make lint test                                # ruff + pytest
python scripts/run_local.py --dry-run         # extract + transform, no writes
python scripts/run_local.py                   # full run against real services
```

Then confirm the container behaves the same as the local run. No key file to mount: R2 credentials are plain environment variables.

```bash
docker build -t rjp .
docker run --rm --env-file .env rjp
```

**Offline model check:** confirm the model really is inside the image and no download happens at runtime (adjust the cache variable if your installed `sentence-transformers` version uses a different one *(verify)*):

```bash
docker run --rm --network none rjp python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5'); print('model loaded offline')"
```

**Idempotency check (mandatory before scheduling):** run the pipeline twice and confirm the row count and content in `jobs` do not change.

```sql
SELECT count(*), max(last_seen_at) FROM jobs;   -- run before and after the second run
```

## 9. Dockerfile notes

```dockerfile
FROM python:3.12-slim
ARG INSTALL_CHROME=false

RUN if [ "$INSTALL_CHROME" = "true" ]; then \
      apt-get update && apt-get install -y --no-install-recommends chromium chromium-driver \
      && rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app
COPY requirements.txt .
# CPU-only PyTorch keeps the image much smaller than the default CUDA build
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

# Bake the embedding model into a fixed cache directory inside the image
ENV HF_HOME=/app/.cache/huggingface
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

# Fail the build if the model was not saved to the cache directory
RUN python -c "import pathlib; p = pathlib.Path('/app/.cache/huggingface'); assert any(p.rglob('*bge-small-en-v1.5*')), 'embedding model missing from image cache'"

# At runtime never download: fail loudly if the model is missing from the image
ENV HF_HUB_OFFLINE=1

COPY src/ ./src/
ENV PYTHONPATH=/app/src
CMD ["python", "-m", "rjp.main"]
```

Scheduled runs use the default build without Chrome. Selenium sources are out of the default pipeline (ADR-022). If you ever run an experimental scraper, do it locally or in a separate manual workflow: `docker build --build-arg INSTALL_CHROME=true -t rjp .`

## 10. GitHub Actions

### Secrets

```bash
gh secret set RAPIDAPI_KEY
gh secret set SUPABASE_DB_URL
gh secret set R2_ACCOUNT_ID
gh secret set R2_ACCESS_KEY_ID
gh secret set R2_SECRET_ACCESS_KEY
gh secret set R2_BUCKET
gh secret set DISCORD_WEBHOOK_URL
```

### `.github/workflows/pipeline.yml`

```yaml
name: pipeline

on:
  schedule:
    - cron: "30 2 * * *"      # daily at 02:30 UTC (09:30 WIB), off the top of the hour
  workflow_dispatch:

concurrency:
  group: pipeline
  cancel-in-progress: false   # never run two pipelines in parallel

permissions:
  contents: read

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4

      - name: Build image
        run: docker build -t rjp .

      - name: Run pipeline
        env:
          RAPIDAPI_KEY: ${{ secrets.RAPIDAPI_KEY }}
          SUPABASE_DB_URL: ${{ secrets.SUPABASE_DB_URL }}
          R2_ACCOUNT_ID: ${{ secrets.R2_ACCOUNT_ID }}
          R2_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}
          R2_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}
          R2_BUCKET: ${{ secrets.R2_BUCKET }}
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
        run: |
          docker run --rm \
            -e RAPIDAPI_KEY -e SUPABASE_DB_URL -e DISCORD_WEBHOOK_URL \
            -e R2_ACCOUNT_ID -e R2_ACCESS_KEY_ID -e R2_SECRET_ACCESS_KEY -e R2_BUCKET \
            rjp
```

No credential file is written or cleaned up: R2 access is plain environment variables, unlike the GCS service account key this replaces.

Points to note:

- `concurrency` protects idempotency by preventing overlapping runs.
- The container's exit code decides the job status: `0` for success or warning, `1` only for total failure.
- The cron time is in **UTC**. The schedule deliberately avoids the top of the hour: GitHub queues many scheduled workflows at :00 and may delay or drop runs during peak load, and public APIs are more likely to have short maintenance windows or traffic spikes around the start of the UTC day *(verify each source's own guidance)*. 02:30 UTC is 09:30 in Indonesia (WIB). Expect some delay even so.
- GitHub may disable scheduled workflows in a public repository after a period without repository activity (currently 60 days) *(verify)*. Re-enable it in the Actions tab or trigger `workflow_dispatch`.
- Building the image on every run costs a few minutes. If that becomes a problem, build once and push to GitHub Container Registry, or use Docker layer caching.

### CI workflow (`ci.yml`)

Run `ruff` and `pytest` on pull requests and pushes, without any secrets.

## 11. First run and verification checklist

Trigger the workflow manually (Actions tab, Run workflow), then check:

- [ ] The Actions run finished with the expected status; the log shows one line per source (`source=... ok jobs=N`).
- [ ] R2 contains `raw-data/year=YYYY/month=MM/day=DD/jobs.json` with a run envelope listing each source's status.
- [ ] `rejected-data/.../rejected.json` exists and contains reason codes (role, seniority, duplicate).
- [ ] Supabase `jobs` has rows and no duplicate `job_id`.
- [ ] A Discord message arrived with counts and any warnings.
- [ ] Running the workflow a second time leaves the database unchanged.
- [ ] Hybrid search works:

```sql
SELECT title, company, eligibility_status, similarity
FROM search_jobs(
  (SELECT embedding FROM jobs LIMIT 1),   -- sample vector for a smoke test
  true, '{}', NULL, true, 5
);
```

## 12. Operations

**Daily:** read the Discord message. Investigate any warning, especially repeated "0 jobs, verify this is expected" messages. Embed colors show urgency at a glance: green for success, yellow for warning or degraded, red for failure.

**Silence is a signal.** If no Discord message has arrived for more than two days, check the Actions tab first. Scheduled workflows in a public repository can be disabled after a period without repository activity (currently 60 days) *(verify)*, and if the schedule stops, the Supabase project can also become inactive and be paused, so both symptoms share one cause. Do not rely on memory alone:

- Set a **personal calendar reminder** roughly every 45 days to open the Actions tab and confirm the schedule is still enabled. If GitHub disabled it, re-enable the workflow there and trigger `workflow_dispatch` once to confirm it runs.
- Real repository activity (commits, merged pull requests) also counts as activity. Avoid automated dummy commits just to keep the schedule alive, because they add noise to the history.
- Treat a missing Discord message as a failure of the monitoring itself, not as "no news".

**Weekly:** review the unknown-eligibility rate, salary-disclosure rate per source, and duplicates removed per source.

**Changing rules:** update the patterns in `src/rjp/resources/`, run `scripts/evaluate.py` against the labeled sets, then reprocess from the raw lake:

```bash
python scripts/reprocess_from_r2.py --date 2026-09-29
```

**Rotating secrets:** update the GitHub secret and the provider-side credential together (Supabase password, R2 API token, RapidAPI key, Discord webhook).

**Rollback:** revert the commit and rerun the workflow. Because writes are idempotent and raw data is kept unfiltered, reprocessing restores the previous behavior without new API calls.

## 13. Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `source=jsearch FAILED reason=quota` | RapidAPI free quota exhausted | Reduce queries per run or lower the schedule frequency |
| `source=... FAILED reason=parse` | Source changed its response format | Update the extractor and add a fixture from the new payload |
| `source=... FAILED reason=auth` | Wrong or expired API key | Rotate the secret |
| Database connection error on the runner | Direct (IPv6) Supabase connection used | Switch to the pooler connection string *(verify)* |
| R2 `403` / `AccessDenied` | API token lacks permission or is scoped to the wrong bucket | Re-check the token's permissions and bucket scope in the R2 dashboard |
| Repeated "0 jobs, verify this is expected" | Sources returning nothing, or filters too strict | Inspect `rejected.json` reason counts and the raw payload |
| Many "skipped due to transform errors" | Source format drift | Inspect the logged job labels; add a fixture and fix the parser |
| Image build is slow or huge | Chrome installed, or CUDA build of PyTorch | Keep `INSTALL_CHROME=false`; use the CPU-only PyTorch index |
| Scheduled runs stopped | Workflow disabled after repository inactivity | Re-enable in the Actions tab |
| Supabase project unreachable | Project paused for inactivity | Restore it from the dashboard and confirm the schedule is running |

## 14. Cost and limits summary *(verify all before relying on them)*

| Service | Free-tier constraint to watch |
|---|---|
| GitHub Actions | Free minutes per month; the daily run should fit comfortably. Public repositories have generous limits |
| Cloudflare R2 | 10 GB storage free; watch the Class A/B operation counts if usage grows *(verify current limits)* |
| Supabase | Storage cap and pause-on-inactivity |
| RapidAPI JSearch | Small monthly request quota |
| Discord | No cost |

## 15. Next step: AI agent

Once the pipeline runs reliably, the agent can consume the data through `search_jobs()`. See `docs/databricks_roadmap.md` for the three options (Supabase as a tool, Delta plus Vector Search, or Lakebase).
