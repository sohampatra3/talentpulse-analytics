# TalentPulse API contract

All routes are same-origin `/api/*`, backed by Python/FastAPI and PostgreSQL. The dashboard uses explicitly labelled synthetic product telemetry. An unavailable database yields HTTP 503, never fabricated results.

## Shared filters

GET analytics routes accept `start_date` (default `2026-09-07`), `end_date` (default `2026-10-04`), `market`, `device_type`, `user_type`, `job_category`, `traffic_source`, `experience_level`, and `variant`. Omit dimensions or use `All` to include all. Dates are inclusive. Dashboard rates are percentages (0–100), latency is milliseconds, cost is USD. `delta` on rate KPIs is percentage points; count KPI delta is relative percent; latency delta is milliseconds. Missing previous-period data gives `delta:null`.

`conversion_rate` = submitted applications / all search sessions; `completion_rate` = submitted applications / sessions that started an application. They have different denominators. The five overview KPI families become six displayed cards because both rates are shown.

`GET /api/filters` → `{markets:string[],devices:string[],user_types:string[],job_categories:string[],traffic_sources:string[],experience_levels:string[],variants:string[],date_range:{start_date,end_date},synthetic:true}`.

## Analytics

`GET /api/health` → `{status, database, synthetic:true, version}`. Checks a real database read.

`GET /api/overview` → `{meta:{synthetic:true,start_date,end_date,source,events,sessions,generated_at,previous_start_date,previous_end_date},kpis:[{key,label,value,unit,delta,previous_value,description}],product_metrics:{dau,wau,searches,job_views,application_starts,application_submits,search_conversion_rate,application_completion_rate,search_success_rate,definitions},trend:[{date,searches,sessions,applications,application_starts,conversion_rate,completion_rate,latency_ms}],markets:[{market,name,searches,sessions,applications,application_rate,completion_rate,share}],devices:[{device_type,name,...same fields}],insights:[{title,detail,severity}]}`. KPI keys: sessions, applications, conversion_rate, completion_rate, avg_load_time_ms, application_error_rate. `application_rate` aliases search conversion.

`GET /api/funnel` → `{meta,steps:[{key,label,count,conversion_rate,step_conversion_rate,drop_off,drop_off_rate}],overall_conversion_rate,biggest_drop:{from,to,count,rate},insights:[{title,detail,severity}]}`. Steps: search_performed (all initiated searches), search_completed, job_viewed, apply_clicked, application_started, cv_uploaded, application_submitted. Counts are sessions, not distinct users.

`GET /api/segments?dimension=device_type&metric=completion_rate` → `{meta,dimension,metric,rows:[{name,label,sessions,applications,conversion_rate,completion_rate,job_view_rate,error_rate,avg_load_time_ms,metric_value,share}],dimensions:string[],metrics:string[]}`. Dimensions include device_type, market, user_type, job_category, traffic_source, experience_level, variant. Metrics include conversion_rate, completion_rate, job_view_rate, error_rate, avg_load_time_ms, sessions.

`GET /api/experiments` → `{primary_metric,assignment_unit:'user',analysis_unit:'user',window_start:'2026-09-21',window_end:'2026-10-04',arms:[{arm,variant,label,provider,model,assigned_users,exposed_users,users,applications,sessions,conversion_rate,exposure_rate,lift_pct,absolute_lift_pp,ci_low,ci_high,p_value,significant,latency_ms,cost_usd,decision}],variants,comparisons,srm,guardrails,allocation,filters_applied,ignored_filters,filter_note,limitations,rate_units}`. **Arms rates are percentages**, raw statistical `variants`/`comparisons` rates are fractions with explicit `rate_units`. `users`/`denominator` are exposed users; `applications` is users with at least one submission, not number of submitted applications. Arm `p_value` is Holm adjusted; intervals are simultaneous treatment-v-control lift intervals in percentage points. SRM tests assigned-user allocation. Experiments always use their predeclared window; market/device/user_type/experience user filters apply, while session-dependent category/source and variant filters are disclosed as excluded to avoid post-assignment selection.

`GET /api/releases` → `{meta,releases:[{id,name,feature,release_date,market,platform,before:{sessions,applications,application_starts,conversion_rate,completion_rate,error_rate,latency_ms},after:{...},impact_pp,impact_metric:'application_completion_rate',relative_lift_pct,latency_change_ms,window_days,before_window:{start_date,end_date},after_window:{start_date,end_date},confidence,interpretation}],disclaimer}`. Periods have the same available number of days, up to seven each. Release market/device intersect analyst filters, so desktop selections exclude mobile-only releases. Effects are observational before/after associations, not causal effects.

`GET /api/data-quality` → `{meta,score,checks:[{key,label,status,observed,threshold,unit,detail}],daily:[{date,events,sessions,missing_required,orphan_events}],event_volume,session_volume}`.

`GET /api/tracking-plan` → `{events:[{name,description,trigger,required_properties:string[],owner,status,volume}],common_properties:string[],synthetic:true}`.

## Search lab

`GET /api/ai/models` → `{providers:[{id,label,model,configured,status,description}],policy:{per_ip_daily_limit,global_daily_limit,max_query_length},synthetic_catalog:true}`. This reports configured credentials; a provider's live connection is verified on a successful request.

`POST /api/search/compare` body `{query:string,market?:string,job_category?:string,limit?:number}` → `{query,synthetic_catalog:true,catalog_size,arms:[{id,label,provider,model,status,latency_ms,retrieval_latency_ms,inference_latency_ms,jobs:[{job_id,job_title,job_category,market,location,salary_min,salary_max,remote_type,experience_level,posted_date}],explanation,cost_usd,error?}],measurement_note}`. Manual search runs real parameterized SQL; available AI providers rank the same database candidate set. Successful total latency includes common candidate retrieval plus provider inference, excludes logging/bookkeeping, and exposes both components. Unsuccessful/unconfigured total latency is null. Missing Ollama returns `not_configured`, never silently uses another provider. Canonical live search records/results are separate from synthetic experiment outcomes; missing provider cost remains null.

## Analyst assistant

`POST /api/ai/investigate` body `{question:string,visualize?:boolean,provider?:'openrouter'|'ollama',filters?:{...shared filters}}` → `{answer,investigation:{finding,evidence,affected_segments,hypothesis,confidence,next_step,suggested_experiment},interpretation,mode:'provider'|'evidence',provider,model,synthetic:true,evidence:[{label,value,unit}],chart:{type:'line'|'bar',title,x_key,y_key,data:object[]}|null,suggested_questions:string[],limitations:string[]}`. SQL, quantitative findings and chart numeric data are selected deterministically by the backend. The provider may add only a qualitative hypothesis/next experiment; numeral-containing provider prose is discarded. The model receives only aggregate evidence and cannot execute generated SQL.

## Connections and export

`GET /api/integrations` → `{integrations:[{id,name,type,status,configured,description,required_env:string[],capabilities:string[],setup_url,details?}],exports:[{id,label,url}],mcp:{endpoint,transport,tools:string[]},synthetic:true}`. Unconfigured Adobe/Power BI are explicitly `not_configured`; no OAuth connection is invented.

`POST /api/integrations/adobe/check` performs a real read-only Adobe Analytics companies request when ADOBE_CLIENT_ID and ADOBE_ACCESS_TOKEN are configured.

`GET /api/export/{dataset}` downloads CSV. Allowlisted datasets: sessions (max 10,000 rows), daily, experiments, jobs (max 10,000 rows), tracking. Capped samples include X-Export-Row-Limit and X-Export-Scope response headers. Use an authorized PostgreSQL connection for full data. Also `GET /api/export/metadata` returns Power BI connection instructions and read-only SQL templates without credentials.

`POST /api/mcp` provides read-only JSON-RPC MCP tools using stateless Streamable HTTP with JSON responses (protocol 2025-06-18 or 2025-03-26). initialize, tools/list, tools/call support overview, funnel, segments, experiments, releases, data_quality, tracking_plan. GET returns 405 (no separate SSE stream), with endpoint documentation. Origin and MCP-Protocol-Version headers are validated; optional MCP_ALLOWED_ORIGINS config permits additional approved browser origins. No write or arbitrary-SQL tool is exposed.
