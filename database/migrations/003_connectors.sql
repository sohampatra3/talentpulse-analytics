-- Private workspace credentials never update shared deployment configuration.
CREATE TABLE IF NOT EXISTS talentpulse.connector_configs (
  workspace_hash text NOT NULL REFERENCES talentpulse.lab_workspaces(workspace_hash) ON DELETE CASCADE,
  connector_id text NOT NULL CHECK(connector_id IN ('adobe','powerbi','mcp','ollama','openrouter')),
  settings jsonb NOT NULL DEFAULT '{}'::jsonb,
  encrypted_secrets text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  last_tested_at timestamptz,
  last_status text NOT NULL DEFAULT 'configured',
  last_result jsonb,
  PRIMARY KEY(workspace_hash,connector_id)
);
