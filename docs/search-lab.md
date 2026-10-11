# Search lab: implementation and evidence contract

Next.js renders five lab sections; FastAPI owns retrieval, model calls, metrics, review and resumable execution; Neon stores catalog snapshots and results. The historical user-level experiment remains independent.

## Setup and resources

Run `scripts/setup_search_lab.py --check` to validate the additive migration in a rolled-back transaction. Run without `--check` to commit the migration and deterministic catalog. `--index` embeds missing documents in batches. Setup is idempotent; embedding writes require the same content hash.

Existing database and provider credentials are reused; keys never reach browser responses. Defaults: 20 provider requests per IP/day, 150 globally, $2/day shared OpenRouter reservation and $0.10 per comparison. Each actual provider request is counted, including embeddings and retries. Unknown Ollama billing remains unknown. `AI_DAILY_USD_LIMIT` changes the daily dollar ceiling.

## Comparison boundaries

- Retrieval-only: fixed catalog/query/filters; keyword, semantic or hybrid reciprocal rank fusion (k=60).
- Model ranking: fixed retrieved candidate IDs and structured job cards.
- Document RAG: fixed model/candidates, adding bounded job-document evidence.
- End-to-end pipeline: separate retrieval configurations; differences cannot be attributed to the model alone.

Model catalogs verify existence, not ranking performance. Responses are validated at runtime. Ollama Cloud schema enforcement is not assumed. Invalid IDs, duplicates and unsupported citations stay visible. Quotes must occur exactly in the evidence supplied to that model.

## APIs

Private endpoints require `X-Workspace-Token`. Paths below start with `/api/search/lab`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/manifest` | Corpus coverage, queries, public examples, measurement fields |
| POST | `/index` | At most 50 missing/changed documents |
| POST/GET | `/runs` | Create one-query comparison / private history |
| GET | `/runs/{id}` | Owned or explicitly published synthetic evidence |
| POST | `/runs/{id}/step` | One leased, bounded model configuration |
| POST | `/runs/{id}/cancel` | Stop future steps; an in-flight step may finish |
| POST | `/runs/{id}/resume` | Resume unfinished work explicitly |
| POST | `/runs/{id}/retry-failed` | Retry failed configurations; retain attempt evidence |
| POST | `/runs/{id}/review` | Grade tied to query and document hash |
| POST | `/runs/{id}/explain` | Qualitative interpretation; deterministic chart values |
| GET | `/summary` | Independent query comparison, grouped by corpus/configuration/label source |
| POST | `/power` | Fixed-horizon sample calculation, multiplicity correction |
| GET/PUT | `/measurement` | Private event/Adobe/ATS field meanings |
| POST | `/adobe` | Authorized mapped aggregate report |

Run inputs: query/query_id, optional uploaded dataset_id, retrieval, language, eligibility filters, candidate_count 10–40, result count 5–10, up to three model variants and cards/RAG evidence modes. Saved provenance includes prompt, corpus and embedding versions, settings, candidate IDs, timing and label source.

## Statistical interpretation

Synthetic rule scores are illustrative, not human ground truth. Uploaded catalogs have no automated relevance score. Reviewed scores require current judgments for the full comparison pool. Missing judgments are not zeros. Exploratory query-bootstrap intervals require five paired independent queries.

Generation cost excludes query embeddings and catalog indexing. Response time includes query embedding, retrieval and the model step. Small-sample p95 is descriptive. Retrieval-only rows do not claim isolated timing when stages were not measured separately.

Online conversion requires user assignment, eligibility, deduplicated confirmed outcomes and a fixed observation window. Adobe aggregates do not independently supply these identities. ATS data is required for employer usefulness. Role/traffic slices can be post-treatment selections; they motivate follow-up experiments rather than establish causal drivers.

## Isolation and BI

Uploaded snapshots and reviews are workspace-isolated before retrieval. Published examples must use the fictional public corpus. The Power BI search-lab view selects published synthetic records only; private data uses authenticated exports.

Reasoning models use a generation allowance of 3,072 tokens, including reasoning; other models use 750. Final answers are validated identically. Retries preserve earlier attempts and consume a separate request allowance. Quality aggregation uses the latest result per unique query text and matching configuration; it is not a cumulative provider reliability estimate.

Private job uploads can map descriptions, skills, working language, active status and expiry dates. Only mapped job fields enter retrieval evidence. Mapping changes create a new immutable catalog snapshot.
