# Databricks / AI Agent Roadmap

Once the pipeline runs reliably and `search_jobs()` returns good results,
there are three ways to connect an AI agent (see `docs/architecture.md`
section 11):

1. **Agent calls `search_jobs()` on Supabase as a tool.** No pipeline
   changes. Fastest path: a Mosaic AI Agent Framework tool definition that
   calls the Supabase REST/RPC endpoint. Requires the `agent_readonly` role
   (ADR-024) to be created first — do not connect an agent with the admin
   credential used during the MVP phase.

2. **Raw lake into Delta tables + Databricks Vector Search.** R2's raw JSON
   is loaded into Delta tables (Auto Loader), building a medallion
   (bronze/silver/gold) layout, with a Vector Search index over the gold
   table. More Databricks-native, more relevant for a data engineering
   portfolio, more setup.

3. **Serving layer moved to Lakebase (Postgres + pgvector).** The schema in
   `sql/002_jobs.sql` is largely portable since Lakebase is Postgres-
   compatible. This is the path most aligned with the
   `ai-job-hunting-copilot` capstone project.

Because `load/` is isolated from `transform/` and `embed/` (ADR-002,
ADR-025), any of these three paths can be adopted without changing the
extraction or filtering logic.

## Before connecting any agent

- Apply `sql/006_roles.sql` and switch `SUPABASE_DB_URL` for the pipeline to
  `pipeline_writer`; give the agent only `agent_readonly` (ADR-024).
- Confirm the public REST API cannot read `jobs` with the anonymous key
  (row-level security should already block this once `006_roles.sql` is
  applied).
- Decide on `eligibility_levels` defaults for the agent's queries — the
  pipeline's own default is `{eligible, unknown}`.
