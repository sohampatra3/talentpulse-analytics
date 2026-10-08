# Private feedback and decisions

All routes use the existing `X-Workspace-Token`. Only SHA-256 workspace identities are stored; responses never return that hash. Records are private to the browser workspace, not a multi-user organization permission system.

- `GET /api/workspace/feedback`: newest-first items, limit 250.
- `POST /api/workspace/feedback`: create an observation and optional test brief.
- `PATCH /api/workspace/feedback/{uuid}`: save `status` and `next_step`.
- `DELETE /api/workspace/feedback/{uuid}`: remove an owned item.
- `GET /api/workspace/feedback/export/csv`: authorized CSV export, formula-prefixed cells escaped.

Create fields: title (3–160 characters), observation (10–2000), hypothesis (1000), primary_metric (200), guardrail (300), success_criteria (500), next_step (500); optional area, source and priority are allowlisted enums. Extra properties are rejected.

Context records the selected dataset name/id, date window, market, device and candidate type. Referenced uploaded datasets must belong to the workspace. Context is saved for interpretation; it does not automatically recompute analytics or prove an observation.

Stages are `new`, `investigating`, `experiment_ready`, `closed`. An experiment-ready record requires a hypothesis, primary metric, guardrail and success criterion. All stages and priorities are analyst judgments; closing an item does not imply a successful test.

Storage is bounded to 250 items per workspace and 2000 total for the public portfolio. An advisory transaction lock makes quota checks atomic across API instances. The additive schema is `database/migrations/004_feedback.sql`.

Use anonymized observations, avoiding candidate personal details. The app sends no feedback to an employer, HR contact or messaging service. Export and deletion are available from the private board.
