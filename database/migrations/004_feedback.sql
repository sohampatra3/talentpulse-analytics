-- Private qualitative evidence and decision trail, isolated by the existing workspace token.
CREATE TABLE IF NOT EXISTS talentpulse.feedback_items (
  id uuid PRIMARY KEY,
  workspace_hash text NOT NULL REFERENCES talentpulse.lab_workspaces(workspace_hash),
  title text NOT NULL CHECK (length(title) BETWEEN 3 AND 160),
  observation text NOT NULL CHECK (length(observation) BETWEEN 10 AND 2000),
  hypothesis text NOT NULL DEFAULT '',
  primary_metric text NOT NULL DEFAULT '',
  guardrail text NOT NULL DEFAULT '',
  success_criteria text NOT NULL DEFAULT '',
  next_step text NOT NULL DEFAULT '',
  area text NOT NULL,
  source text NOT NULL,
  priority text NOT NULL CHECK (priority IN ('low','medium','high')),
  status text NOT NULL DEFAULT 'new' CHECK (status IN ('new','investigating','experiment_ready','closed')),
  context jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS feedback_workspace_created ON talentpulse.feedback_items(workspace_hash,created_at DESC);
