# Native Power BI connection

Power BI requires your own Microsoft credentials, workspace permissions and, for secure embedding, the appropriate license and embed configuration. This repository provides native PostgreSQL import assets; it does not fabricate a connected Power BI report.

1. In Power BI Desktop, choose **Get data → PostgreSQL database**.
2. Enter the Neon direct hostname and `neondb`, enable encrypted SSL, and authenticate using a dedicated read-only database role. Keep the password in Power BI credentials, not in the query file.
3. Import `talentpulse.bi_daily_kpis`, `talentpulse.bi_funnel_segments`, and `talentpulse.bi_experiment_users` from `database/schema.sql`. Prefer daily and segment aggregates for refresh efficiency; use the experiment view for the fixed user-level population.
4. Use [query.pq](query.pq) as a parameterized Power Query starting point and [measures.dax](measures.dax) for the semantic model. Adjust the view name if your selected table uses a different aggregate grain.
5. Create pages for KPIs, funnel, segment comparison, experiment summary and release impact. Use the shared date table and consistent market/device slicers.
6. Publish into your Power BI workspace. Configure credentials and refresh there. Store a permitted report URL in the app or set `POWERBI_EMBED_URL`; private reports still require Microsoft authorization.

Recommended pages:

| Page | Visuals | Decision supported |
|---|---|---|
| Product health | KPI cards, daily trend, market table | Where did performance change? |
| Journey | Ordered funnel, device comparison | Where does friction occur? |
| Search experiment | Treatment rates, uncertainty, guardrails | Does the evidence support rollout? |
| Releases | Matched-period trends, error rates | What should we investigate? |

Experiment significance is computed by the Python statistical service. Import or export that result alongside the counts. A report URL is labelled configured when supplied. An authorized REST token can verify report discovery; opening a report still depends on Microsoft sign-in, viewer permissions and licensing. The dedicated Power BI tab keeps these checks separate and can open your connected report.

See [the full integration guide](../docs/integration-guide.md) for Microsoft Entra app registration, REST scopes, refresh, row-level security, secure embedding and troubleshooting.
