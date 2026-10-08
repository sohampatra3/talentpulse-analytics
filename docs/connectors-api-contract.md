# Workspace, models and external evidence extension

## Workspace boundary

`POST /api/workspaces` with `{}` creates an isolated workspace and returns `{workspace_token,workspace_id,created_at}`. Keep only `workspace_token` in browser-local storage; send it in `X-Workspace-Token` on workspace, upload and source endpoints. Tokens are unguessable bearer credentials; the database stores only their SHA-256 hash. A missing/invalid token returns 401. Server encryption uses `APP_ENCRYPTION_KEY`; connector secrets are encrypted at rest and never echoed.

`GET /api/workspace/connectors` returns `{connectors:[{id,name,configured,status,settings,secrets_present:string[],last_tested_at,last_result}],workspace_id}`. No secrets appear in settings or last_result. Only this workspace's records are returned.

`PUT /api/workspace/connectors/{id}` accepts `{settings:object,secrets:object}`. Supported IDs: `adobe`, `powerbi`, `mcp`, `ollama`, `openrouter`. Empty secret values preserve the existing encrypted value; explicit `clear_secrets:true` removes saved secrets. Returns masked metadata `{connector:{...}}`.

`POST /api/workspace/connectors/{id}/check` returns `{status:'verified'|'configured'|'error'|'not_configured',verified:boolean,detail,checked_at,capabilities,details?}` and saves the safe result. Configuration alone is labelled `configured`; `verified` requires an actual provider/API/tool response.

`DELETE /api/workspace/connectors/{id}` removes only this workspace's connector configuration. It never alters shared deployment credentials.

## Connector fields

- Adobe settings: `auth_type:'bearer'|'oauth_client_credentials'`, `company_id`, `report_suite_id`, optional `dimension_id` (default `variables/daterangeday`), `metric_ids:string[]` (default visits/pageviews/uniquevisitors), optional `experiment_dimension_id`, `scopes` (OAuth scope string). Secrets: `client_id`, `access_token`, optional `client_secret`. REST endpoint is fixed to Adobe Analytics; custom destinations are not accepted.
- Power BI settings: `embed_url` (HTTPS app.powerbi.com only), optional `group_id`. Secrets: optional `access_token` for an actual REST report-list check. Without OAuth access token, a supplied embed URL is configuration only.
- MCP settings: `endpoint` (HTTPS public host, no IP literals/local/internal hosts), `auth_type:'none'|'bearer'|'api_key'`, optional `auth_header` (allowlisted `Authorization`, `X-API-Key`, `api-key`), optional `tool_name` and `tool_arguments` for an explicit read-only enrichment tool. Secrets: `token` for bearer/API-key auth. Check sends initialize/tools-list to the validated endpoint, with bounded requests and no redirects; private/reserved DNS destinations are rejected.
- Ollama/OpenRouter settings: `model`, `purpose:'search'|'analyst'|'ingestion'`. Secrets: optional `api_key` override for this workspace; otherwise available server credentials are used. Provider URLs are fixed.

## Model catalog and selection

`GET /api/ai/models` returns existing `providers` and `policy`, plus `catalog:[{provider,id,label,source,available,capabilities:string[]}]`, `catalog_status`, `defaults:{search:{openrouter,ollama},analyst:{provider,model},ingestion:{provider:'ollama',model:'gemma4:31b'}}`. Ollama catalog IDs come from actual `https://ollama.com/api/tags`. Gemma 4 31B is the verified Ollama Cloud interpretation of the requested Google Gemma 31B. Catalog fetch has a bounded timeout and cache; unavailable fetch is stated explicitly, with documented defaults labelled accordingly rather than claimed available.

`POST /api/search/compare` adds optional `models:{openrouter:string,ollama:string}` and optional `X-Workspace-Token`. Returned arm model identifies the actual request model. Manual SQL remains an independent arm. Live ranking and historical synthetic experiment metrics stay separate.

`POST /api/ai/investigate` adds optional `model:string` and optional `X-Workspace-Token`. When omitted, a saved workspace provider model or configured server default applies. The numeric finding still comes from deterministic aggregate queries; models only interpret actual evidence qualitatively.

## Actual Adobe evidence

`POST /api/workspace/adobe/report` requires the workspace token and saved Adobe connector. Body `{start_date,end_date,dimension?:string,metrics?:string[],segment_id?:string,limit?:number,page?:number}`. Dates are inclusive, converted to Adobe's exclusive end boundary. Returns `{source:'adobe_analytics',synthetic:false,status,report_suite_id,dimension,metrics,rows:[{item_id,label,values:{metric_id:number}}],totals:{metric_id:number},pagination:{page,total_pages,total_rows,last_page},chart:{type,title,x_key,y_keys,data},provenance:{endpoint,fetched_at,window},limitations:string[]}`. Values are direct Adobe response data; no significance or causal inference is invented. Error/missing credentials return explicit non-success status without fabricated rows.

`POST /api/workspace/mcp/enrich` calls only the configured tool declared read-only by the remote server. Body `{tool_name?:string,arguments?:object}`. Returns actual remote content and source metadata. This does not automatically merge unverified remote text into uploaded rows or experimental inference.

Adobe `transport:'mcp'` uses the documented `https://aa-mcp.adobe.io/mcp` endpoint with `org_id`, `company_id` and authorized OAuth headers. `POST /api/workspace/adobe/mcp/report` accepts the same report request and invokes Adobe's documented read-only `runReport`; it returns actual tool content and provenance rather than manufacturing chart rows when the remote payload is unstructured. REST and MCP connection checks are separate and their status requires the actual selected transport response.

`GET /api/experiments/drivers?role=Product%20Analyst&dataset_id=...` returns `{role,role_options,support:{row_count,session_count,unique_users,grain,randomized_status,denominator},arms,drivers:[{factor,groups,interpretation}],limitations,suggested_experiment}`. Omit `dataset_id` to inspect labelled synthetic session associations; include it and the workspace token for private uploaded evidence. Role selection is observational and does not declare an inferential winner.

`POST /api/ai/investigate` also accepts `role`; its quantitative finding and chart then use the corresponding actual role-driver evidence. A model may propose a hypothesis, but cannot create missing counts, significance, or causal explanations. `dataset_id` selects private uploaded evidence for analyst and search requests, with separate uploaded search logs and no foreign-key attribution to synthetic jobs.

## Loading/performance

`GET /api/health` is a fast process/configuration liveness response; `GET /api/health/database` performs the actual bounded DB check. Analytics requests use single-flight caching (one in-flight query per identical key), bounded database connect/statement timeouts and a shared read transaction. A provider or external connector failure does not replace analytics with demo values.
