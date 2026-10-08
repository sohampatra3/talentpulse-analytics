-- Tokens are 256-bit random bearer credentials; only their SHA-256 hashes persist.
CREATE TABLE IF NOT EXISTS talentpulse.lab_workspaces (
  workspace_hash text PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now()
);
