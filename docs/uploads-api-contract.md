# Private uploads API contract

Uploads are scoped to a browser workspace. `POST /api/workspaces` creates a random 256-bit token. Send it as `X-Workspace-Token` for every private request. Only its SHA-256 hash is stored in Neon. A dataset identifier does not grant access; another workspace cannot list, search, export, rank or analyze its rows. Losing the browser token loses access to those uploads.

## Ingestion and mapping

| Request | Response |
| --- | --- |
| `GET /api/uploads/schema` | `mapping_fields`, `kinds`, verified `model_choices`, file/row/column limits and template links |
| `POST /api/uploads` | Multipart `file`, optional `kind=auto`, JSON-string `mapping`, `ingestion_model`; returns dataset metadata directly |
| `GET /api/uploads?search=...` | `{datasets: [...], limits: ...}` scoped to the workspace |
| `GET /api/uploads/{dataset_id}` | Metadata and first 50 original rows as `preview` |
| `PATCH /api/uploads/{dataset_id}/mapping` | `{mapping: {canonical_field: source_column}, kind: "auto"}`; revalidates and replaces typed mappings atomically |
| `GET /api/uploads/{dataset_id}/search?q=...` | `{dataset_id, query, total, rows: [{row_number,data}], source}`; bounded text search, first 100 matches |
| `GET /api/uploads/{dataset_id}/export` | Authenticated original-row CSV; formula-like values escaped for spreadsheet safety |
| `DELETE /api/uploads/{dataset_id}` | Deletes the dataset, typed rows and its private live-search logs |

Metadata contains `dataset_id`, `id` (alias), `name`, `kind`, `columns`, `mapping`, `row_count`, `column_count`, `profile`, `date_range` (nullable), `filter_options`, `readiness`, `reasons`, `evidence_quality` and `semantic_metadata`. `profile` contains actual nonempty and distinct counts per source column. `readiness` describes available analysis types, not evidence of causality. `filter_options` contains actual mapped `markets`, `devices`, `user_types`, `job_categories`, `traffic_sources`, `experience_levels` and `variants`.

CSV must be UTF-8. XLSX must contain one values-only worksheet. Formulas, macros, external links, XML entities and unsafe compressed archives are rejected. Limits: 3 MB file, 10,000 rows, 20 columns, 4,000 characters per cell. Raw plus typed serialized payload is limited to 8 MB per dataset, 10 MB per workspace and 30 MB globally; 10 datasets per workspace and 100 globally. A transaction advisory lock prevents concurrent uploads/remappings from bypassing those quotas. Index and database overhead receive additional headroom; the quotas describe serialized payload, not exact physical database size.

Supported kinds are `auto`, `jobs`, `sessions`, `events`, `user_outcomes`, `experiment_summary`, `generic`. The schema endpoint is the authoritative mapping field allowlist. Canonical values are typed deterministically: booleans, nonnegative finite numeric values, whole sample/conversion counts and ISO dates/timestamps. Salary ranges, exposed conversion outcomes and mapped session funnels are validated.

Ollama ingestion defaults to verified `gemma4:31b`, with `gpt-oss:120b` selectable. Workspace credentials override server credentials. The model receives a bounded preview and column profile, and suggests a description, grain, dimensions and exact canonical-to-source mappings. Unsupported fields/columns are removed. Proposals never override parsing or mapping until the user submits a reviewed mapping. `semantic_metadata.mode="provider"` records the actual model, measured latency and provider-reported cost (nullable). If provider output is unavailable or invalid, mode is visibly `deterministic`; no provider success is fabricated.

## Analytics source selection

Existing endpoints accept `dataset_id` plus the workspace header: `/api/filters`, `/api/overview`, `/api/funnel`, `/api/segments`, `/api/experiments`, `/api/releases`, `/api/data-quality`, `/api/tracking-plan`, `/api/experiments/drivers`. The dedicated route `/api/uploads/{dataset_id}/analysis?view=overview|funnel|segments|experiments|releases|quality|tracking|filters` also accepts date, dimension and metric selection.

All rows come from the selected authorized dataset. Uploaded sources never merge synthetic historical outcomes. Unsupported analyses return `available=false`, a reason and empty data. Counts and rates require their mapped measures; missing or partial outcome coverage produces `null`, not an assumed zero. An unmapped date makes `meta.date_filter_applied=false` and exposes a date-filter note; it does not establish an observation window. Uploaded DAU/WAU require mapped identifiers and dates; WAU considers the trailing seven days independently of the selected start date and describes observed uploaded activity.

- **Jobs/generic:** supply counts, searchable rows and role/category breakdowns. No conversion, application funnel, user significance or behavioral guardrails are estimated from job inventory.
- **Sessions/events:** session conversion is submissions/all observed search sessions; completion is submissions/application starts. Funnel steps require observed mapped stage coverage and monotonic counts. Duplicate session rows or conflicting user/arm attribution are rejected during analysis. An absent event type is unavailable coverage, not a measured zero.
- **User outcomes:** distinct exposed users form the conversion denominator; repeated rows do not create additional users. Overview/segments use the same user denominator, without inventing session counts or latency. Missing identifiers/exposure/outcomes withhold affected rates.
- **Experiments:** complete unique user outcomes with explicit `randomized=true`, `assignment_unit=user`, mapped observation dates, a control arm and no arm crossover can receive proportions tests and Holm-adjusted treatment comparisons. Small binomial cells withhold normal inference. Randomization/window declarations remain unaudited. Planned allocation is unknown, so uploaded SRM is unavailable. Session/event datasets, explicit aggregate arm counts, unsupported provenance, duplicate outcomes and role/cohort filters remain descriptive. Role/category may be post-assignment; no causal role winner is declared.
- **Releases:** declared release markers permit observational seven-day before/after summaries; missing baselines/outcomes produce unavailable impact. These associations do not establish release causality.
- **Quality/tracking:** actual parsing, mapping, IDs and observed event counts are returned. No artificial aggregate quality score is created. `score=null` means no score is defined.

Top-level overview/segment/funnel chart rates are percentages. Experiment `arms` rates are percentages; `variants` and non-`*_pp` comparison values are fractions; `*_pp` fields are percentage points. Unmeasured latency/cost remains `null`. Source metadata declares `source_type="uploaded"`; `synthetic=null` means uploaded provenance is not independently known.

## Role drivers, AI and live search

`GET /api/experiments/drivers?dataset_id=...&role=...` returns actual `role_options`, `support`, descriptive `arms`, `drivers`, `measurement_readiness`, `evidence_quality`, `limitations` and a proposed experiment. Readiness entries `{label,value,status,detail}` report mapped coverage, actual identifier presence, conversion denominator, outcome coverage, randomization declaration and numeric evidence source. Driver differences are observed associations.

AI questions carry `dataset_id` and the workspace header. Numeric evidence/charts are calculated deterministically from stored typed rows; model prose cannot replace counts. Private catalogs yield supply/search evidence rather than invented conversion. Live comparison accepts a job dataset and ranks actual mapped candidates; private results use row-number identifiers and are recorded in `upload_search_runs`, never joined to synthetic job IDs or historical experiment outcomes.

## Templates and migrations

Public `GET /api/uploads/templates/{jobs|sessions|user_outcomes|experiment_summary}` downloads explicitly named synthetic example CSVs. Their data is illustrative, not a real model evaluation.

Apply ordered migrations `database/migrations/001_workspaces.sql`, `002_uploads.sql`, `003_connectors.sql`. Migration 002 is idempotent and backfills payload accounting for earlier validation uploads without changing their row contents. Validate against an isolated Neon branch before applying to the main database; do not reset the existing synthetic dataset.
