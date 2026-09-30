CREATE INDEX IF NOT EXISTS jobs_embedding_hnsw
    ON jobs USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS jobs_eligible_posted
    ON jobs (eligibility_status, posted_at DESC);

CREATE INDEX IF NOT EXISTS jobs_tech_gin
    ON jobs USING gin (tech_stack);

CREATE INDEX IF NOT EXISTS jobs_dedup_block
    ON jobs (company_norm, title_norm);
