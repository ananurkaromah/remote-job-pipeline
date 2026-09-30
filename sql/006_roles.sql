-- Least-privilege database roles (ADR-024). NO PASSWORDS in this file --
-- set them manually after running this migration:
--   ALTER ROLE pipeline_writer PASSWORD '<generated-password>';
--   ALTER ROLE agent_readonly  PASSWORD '<generated-password>';
--
-- MVP NOTE: for the current MVP stage, the pipeline connects with the admin
-- (postgres) credential and this migration has not been applied yet
-- (deliberately deferred, see docs/deployment.md section 3). Apply this
-- before connecting any AI agent or downstream app to search_jobs().

CREATE ROLE pipeline_writer LOGIN;
CREATE ROLE agent_readonly  LOGIN;

REVOKE ALL ON jobs FROM PUBLIC, anon, authenticated;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

GRANT USAGE ON SCHEMA public TO pipeline_writer, agent_readonly;
GRANT SELECT, INSERT, UPDATE, DELETE ON jobs TO pipeline_writer;
GRANT SELECT ON jobs TO agent_readonly;
GRANT EXECUTE ON FUNCTION search_jobs TO agent_readonly;

CREATE POLICY pipeline_all ON jobs FOR ALL    TO pipeline_writer USING (true) WITH CHECK (true);
CREATE POLICY agent_select ON jobs FOR SELECT TO agent_readonly  USING (true);

ALTER ROLE agent_readonly SET default_transaction_read_only = on;
ALTER ROLE agent_readonly SET statement_timeout = '10s';
