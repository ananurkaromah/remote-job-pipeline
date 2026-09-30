-- Hybrid search RPC: SQL filters (eligibility, skills, salary, recency) + cosine similarity.
-- Default eligibility_levels keeps 'eligible' and 'unknown', hides 'restricted' (ADR-005).
-- Salary filtering keeps undisclosed jobs by default (ADR-007) so missing salary never hides a job.
CREATE OR REPLACE FUNCTION search_jobs(
    query_embedding      VECTOR(384),
    eligibility_levels    TEXT[]  DEFAULT ARRAY['eligible', 'unknown'],
    required_skills       TEXT[]  DEFAULT '{}',
    min_salary            NUMERIC DEFAULT NULL,
    include_undisclosed   BOOLEAN DEFAULT TRUE,
    match_count           INT     DEFAULT 10
)
RETURNS TABLE (
    job_id TEXT, title TEXT, company TEXT, url TEXT, tech_stack TEXT[],
    eligibility_status TEXT, salary_status TEXT,
    min_salary_usd NUMERIC, max_salary_usd NUMERIC, similarity FLOAT
)
LANGUAGE sql STABLE AS $$
    SELECT j.job_id, j.title, j.company, j.url, j.tech_stack,
           j.eligibility_status, j.salary_status, j.min_salary_usd, j.max_salary_usd,
           1 - (j.embedding <=> query_embedding) AS similarity
    FROM jobs j
    WHERE j.eligibility_status = ANY(eligibility_levels)
      AND (required_skills = '{}' OR j.tech_stack @> required_skills)
      AND (
            min_salary IS NULL
         OR (include_undisclosed AND j.salary_status IN ('not_disclosed', 'unparsed'))
         OR COALESCE(j.max_salary_usd, j.min_salary_usd) >= min_salary
      )
    ORDER BY j.embedding <=> query_embedding
    LIMIT match_count;
$$;
