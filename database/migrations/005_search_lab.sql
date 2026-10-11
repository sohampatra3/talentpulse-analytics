-- Additive search-quality lab; historical facts are intentionally independent.
CREATE EXTENSION IF NOT EXISTS lakebase_vector CASCADE;
ALTER TABLE talentpulse.api_usage_daily ADD COLUMN IF NOT EXISTS reserved_usd numeric NOT NULL DEFAULT 0;
CREATE TABLE IF NOT EXISTS talentpulse.search_corpora (
 corpus_id text PRIMARY KEY, workspace_hash text REFERENCES talentpulse.lab_workspaces(workspace_hash),
 source text NOT NULL, version text NOT NULL, metadata jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS talentpulse.search_documents (
 corpus_id text NOT NULL REFERENCES talentpulse.search_corpora(corpus_id) ON DELETE CASCADE,
 job_id integer NOT NULL, metadata jsonb NOT NULL, body text NOT NULL, content_hash text NOT NULL,
 embedding vector(1536), embedding_model text,
 search_text tsvector GENERATED ALWAYS AS (to_tsvector('simple',body)) STORED,
 PRIMARY KEY(corpus_id,job_id)
);
CREATE INDEX IF NOT EXISTS search_documents_text ON talentpulse.search_documents USING gin(search_text);
CREATE INDEX IF NOT EXISTS search_documents_vector ON talentpulse.search_documents USING lakebase_ann(embedding vector_cosine_ops);
CREATE TABLE IF NOT EXISTS talentpulse.search_queries (
 query_id text PRIMARY KEY, query text NOT NULL, intent text NOT NULL, language text NOT NULL,
 split text NOT NULL, rubric jsonb NOT NULL, version text NOT NULL
);
CREATE TABLE IF NOT EXISTS talentpulse.search_reviews (
 workspace_hash text NOT NULL REFERENCES talentpulse.lab_workspaces(workspace_hash),
 corpus_id text NOT NULL, query_id text NOT NULL, job_id integer NOT NULL, content_hash text NOT NULL,
 grade integer NOT NULL CHECK(grade BETWEEN 0 AND 3), note text NOT NULL DEFAULT '', updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(workspace_hash,corpus_id,query_id,job_id)
);
CREATE TABLE IF NOT EXISTS talentpulse.search_evaluations (
 run_id uuid PRIMARY KEY, workspace_hash text NOT NULL REFERENCES talentpulse.lab_workspaces(workspace_hash),
 corpus_id text NOT NULL, config jsonb NOT NULL, candidates jsonb NOT NULL,
 baselines jsonb NOT NULL, status text NOT NULL DEFAULT 'paused', reserved_usd numeric NOT NULL DEFAULT 0,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS search_evaluations_workspace ON talentpulse.search_evaluations(workspace_hash,created_at DESC);
CREATE TABLE IF NOT EXISTS talentpulse.search_evaluation_cases (
 run_id uuid REFERENCES talentpulse.search_evaluations(run_id) ON DELETE CASCADE, ordinal integer NOT NULL,
 variant jsonb NOT NULL, status text NOT NULL DEFAULT 'pending', result jsonb,
 lease_id uuid, lease_until timestamptz, PRIMARY KEY(run_id,ordinal)
);
CREATE TABLE IF NOT EXISTS talentpulse.search_measurement_maps (
 workspace_hash text PRIMARY KEY REFERENCES talentpulse.lab_workspaces(workspace_hash),
 mapping jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE talentpulse.search_evaluation_cases ADD COLUMN IF NOT EXISTS attempts jsonb NOT NULL DEFAULT '[]';
CREATE OR REPLACE VIEW talentpulse.v_search_lab_results AS
 SELECT r.run_id,r.corpus_id,r.created_at,r.config->>'query' AS query,c.ordinal,
 c.variant->>'model' AS model,c.variant->>'evidence' AS evidence,c.status,
 (c.result->>'latency_ms')::double precision AS latency_ms,
 (c.result->>'cost_usd')::double precision AS cost_usd,c.result->'metrics' AS metrics
 FROM talentpulse.search_evaluations r JOIN talentpulse.search_evaluation_cases c USING(run_id)
 WHERE r.corpus_id='synthetic-jobs-v1' AND r.config->>'published'='true';
