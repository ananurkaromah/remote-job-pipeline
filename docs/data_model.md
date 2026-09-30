# Data Model

Full schema definitions live in `sql/002_jobs.sql` through `sql/006_roles.sql`; this
is a short reference to the columns and what each one means. See
`docs/architecture.md` section 4 and section 5 for the eligibility model and
idempotency guarantees these columns support.

## `jobs` table

| Column | Type | Meaning |
|---|---|---|
| `job_id` | `TEXT PK` | `sha256(source:external_id)`, or a canonical URL hash when no external id exists |
| `source` | `TEXT` | `remoteok` \| `remotive` \| `himalayas` \| `jsearch` |
| `origin_portal` | `TEXT` | The publisher behind an aggregator result (e.g. JSearch → `linkedin`) |
| `url` / `canonical_url` | `TEXT` | Original and tracking-stripped URL |
| `title` / `title_norm` | `TEXT` | Original and normalized title (used for dedup blocking) |
| `company` / `company_norm` | `TEXT` | Original and suffix-stripped company name |
| `description_clean` | `TEXT` | HTML-stripped, whitespace-normalized description |
| `posted_at` | `TIMESTAMPTZ` | Used for the 7-day recency window and retention |
| `eligibility_status` | `TEXT` | `eligible` \| `restricted` \| `unknown` (ADR-005) |
| `eligibility_confidence` | `TEXT` | `high` \| `medium` \| `low` |
| `eligibility_evidence` | `JSONB` | Matched phrases that produced the status |
| `timezone_hint` | `TEXT` | Overlap requirement text; never changes eligibility status |
| `role_match` | `TEXT` | `core` \| `adjacent` (rows with neither are not stored) |
| `seniority_level` | `TEXT` | `junior` \| `mid` \| `unknown` |
| `min_years_required` | `SMALLINT` | Largest lower-bound years requirement found, if any |
| `salary_status` | `TEXT` | `disclosed` \| `partial` \| `not_disclosed` \| `unparsed` (ADR-007) |
| `min_salary_usd` / `max_salary_usd` | `NUMERIC` | Nullable; NULL means unknown, never zero |
| `tech_stack` | `TEXT[]` | Normalized skill list |
| `completeness_score` | `SMALLINT` | Used by dedup to pick a winner (ADR-010) |
| `embedding` | `VECTOR(384)` | bge-small-en-v1.5 embedding |
| `embedding_text` | `TEXT` | Exact text that was embedded, for debugging |

## Relationships

There is a single table by design: metadata and the vector live together so
`search_jobs()` can filter and rank in one query, without a join. Raw,
unfiltered payloads live outside Postgres entirely, in Cloudflare R2
(`raw-data/year=/month=/day=/jobs.json`), so the database only ever holds
the current 7-day window of surviving jobs.

See `docs/architecture.md` section 4 for the full data flow and
`docs/decisions.md` ADR-005 through ADR-014 for why each column exists.
