CREATE TABLE IF NOT EXISTS talentpulse.upload_datasets (
 dataset_id uuid PRIMARY KEY, workspace_hash text NOT NULL,
 name text NOT NULL,kind text NOT NULL,columns jsonb NOT NULL,mapping jsonb NOT NULL,
 metadata jsonb NOT NULL DEFAULT '{}'::jsonb,row_count integer NOT NULL,column_count integer NOT NULL,
 file_sha256 text NOT NULL,payload_bytes bigint NOT NULL DEFAULT 0,created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE talentpulse.upload_datasets ADD COLUMN IF NOT EXISTS payload_bytes bigint NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS upload_dataset_workspace ON talentpulse.upload_datasets(workspace_hash,created_at);
CREATE TABLE IF NOT EXISTS talentpulse.upload_rows (
 dataset_id uuid NOT NULL REFERENCES talentpulse.upload_datasets(dataset_id) ON DELETE CASCADE,
 row_number integer NOT NULL,row_data jsonb NOT NULL,normalized_data jsonb NOT NULL,
 search_document tsvector GENERATED ALWAYS AS (to_tsvector('simple',row_data::text)) STORED,
 PRIMARY KEY(dataset_id,row_number)
);
CREATE INDEX IF NOT EXISTS upload_rows_search ON talentpulse.upload_rows USING gin(search_document);
-- Earlier validation uploads predate byte accounting. Backfill without altering rows.
UPDATE talentpulse.upload_datasets d SET payload_bytes=x.bytes
FROM (SELECT dataset_id,sum(octet_length(row_data::text)+octet_length(normalized_data::text)) AS bytes FROM talentpulse.upload_rows GROUP BY dataset_id) x
WHERE d.dataset_id=x.dataset_id AND d.payload_bytes=0;
CREATE TABLE IF NOT EXISTS talentpulse.upload_search_runs (
 run_id uuid PRIMARY KEY,workspace_hash text NOT NULL,
 dataset_id uuid NOT NULL REFERENCES talentpulse.upload_datasets(dataset_id) ON DELETE CASCADE,
 created_at timestamptz NOT NULL DEFAULT now(),query text NOT NULL,provider text NOT NULL,model text,
 status text NOT NULL,latency_ms integer,cost_usd numeric(12,6),job_ids jsonb NOT NULL,
 retrieval_latency_ms integer,inference_latency_ms integer
);
