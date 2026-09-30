-- Final jobs table, consolidating every design decision in docs/decisions.md.
CREATE TABLE IF NOT EXISTS jobs (
    job_id              TEXT PRIMARY KEY,           -- sha256(source:external_id or canonical url)
    source              TEXT NOT NULL,              -- remoteok | remotive | himalayas | jsearch
    origin_portal       TEXT,                       -- publisher behind an aggregator (e.g. jsearch -> linkedin)
    external_id         TEXT,
    url                 TEXT NOT NULL,
    is_direct_apply_url BOOLEAN NOT NULL DEFAULT FALSE,
    title               TEXT NOT NULL,
    company             TEXT,
    company_norm        TEXT,
    title_norm          TEXT,
    description_clean   TEXT,
    posted_at           TIMESTAMPTZ NOT NULL,

    -- location / eligibility (ADR-005, tri-state, never a hard drop for 'unknown')
    location_raw            TEXT,
    eligibility_status       TEXT NOT NULL DEFAULT 'unknown'
        CHECK (eligibility_status IN ('eligible', 'restricted', 'unknown')),
    eligibility_confidence   TEXT NOT NULL DEFAULT 'low'
        CHECK (eligibility_confidence IN ('high', 'medium', 'low')),
    eligibility_evidence      JSONB NOT NULL DEFAULT '[]',
    timezone_hint             TEXT,
    is_eligible_for_id        BOOLEAN GENERATED ALWAYS AS (eligibility_status = 'eligible') STORED,

    -- role / seniority (ADR-008, ADR-009: strict 3+ years cutoff, no stretch tier)
    role_match           TEXT CHECK (role_match IN ('core', 'adjacent')),
    seniority_level       TEXT NOT NULL DEFAULT 'unknown'
        CHECK (seniority_level IN ('junior', 'mid', 'unknown')),
    min_years_required    SMALLINT,
    role_evidence          JSONB NOT NULL DEFAULT '[]',

    -- salary (ADR-007: optional enrichment, never a filter)
    salary_status   TEXT NOT NULL DEFAULT 'not_disclosed'
        CHECK (salary_status IN ('disclosed', 'partial', 'not_disclosed', 'unparsed')),
    min_salary_usd  NUMERIC(12, 2),
    max_salary_usd  NUMERIC(12, 2),
    salary_period   TEXT CHECK (salary_period IN ('yearly', 'monthly', 'hourly')),
    salary_raw      TEXT,

    -- skills
    tech_stack TEXT[] NOT NULL DEFAULT '{}',

    -- dedup (ADR-010)
    completeness_score SMALLINT,

    -- vector (ADR-013)
    embedding      VECTOR(384),
    embedding_text TEXT,

    -- housekeeping
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
