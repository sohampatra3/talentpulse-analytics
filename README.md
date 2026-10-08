# TalentPulse · Product Analytics Lab

An independent portfolio project for product analysts in a European job marketplace. Observe a KPI, investigate the funnel, locate a segment, assess a release, evaluate an experiment, and turn evidence into a product recommendation.

[Open the live workspace](https://talentpulse-analytics.vercel.app) · [Source on GitHub](https://github.com/sohampatra3/talentpulse-analytics) · [Five-minute demo](docs/demo-walkthrough.md) · [Referral and portfolio strategy](public/portfolio-strategy.md)

Created by **Soham Patra**.

All historical marketplace behavior is **reproducible synthetic data**, not StepStone data. The simulated model arms illustrate an analytical method; their lift is not evidence that a real model improves a real marketplace. The live search comparison records actual provider calls separately.

## Stack and architecture

Next.js / React / TypeScript / Tailwind / Recharts → FastAPI / Pydantic → parameterized PostgreSQL + Python analytics → Neon. OpenRouter and Ollama Cloud interpret structured evidence and rerank a bounded shortlist of real database job IDs. Power BI connects directly to curated PostgreSQL views. Adobe Analytics has a provider boundary for credentials-backed REST reports. A read-only MCP endpoint exposes the same analytics services.

```mermaid
flowchart LR
  UI[Analyst workspace] --> API[FastAPI]
  API --> SQL[SQL + Python analytics]
  SQL --> Neon[(Neon PostgreSQL)]
  API --> AI[OpenRouter / Ollama Cloud]
  Neon --> BI[Power BI views]
  MCP[MCP tools] --> API
  Adobe[Adobe Analytics adapter] --> API
```

## Workspace

- **Overview:** KPIs, period comparison, daily trends, market and device performance.
- **Search experiments:** three-arm user-level analysis with confidence intervals, multiple-comparison correction, sample-ratio checks and operational guardrails; separate live manual/GPT-4o/GPT-OSS 120B comparison.
- **Funnel & segments:** ordered session funnel, transition drop-off, segmentation and consistent filters.
- **Release impact:** matched before/after windows and affected segments. Observational differences are hypotheses, not causal estimates.
- **AI analyst:** evidence-backed interpretation, a chart draft using queried numbers, and an exportable recommendation.
- **Power BI:** dedicated secure report setup, authorized REST discovery, report links, opt-in embedding and permission/refresh guidance.
- **Adobe Analytics:** dedicated REST/MCP authentication setup, actual report queries, selectable-metric charts and response provenance.
- **Feedback & decisions:** private Neon-backed observations, test briefs, decision stages and CSV export with saved dataset context.
- **Data & connections:** quality checks, tracking dictionary, Neon, OpenRouter, Ollama, Adobe and Power BI setup.

Light, dark, warm amber and Frosted themes are available, with a 17px default font and translucent glass panels. Interactive charts switch area/line views, compare distinctly colored experiment arms and animate AI visualization drafts. Motion respects reduced-motion preferences. Requests have bounded timeouts, retry controls and cached results so navigation remains available during refreshes.

Every page includes a private CSV/XLSX dataset library. Google Gemma 4 31B can propose semantic descriptions and column mappings; validated fields determine which analyses are available. A job catalog supports discovery, while conversion comparisons require behavioral outcomes and denominators. Uploaded results retain their own source labels and never mix silently with the synthetic demonstration.

## Run locally

Requires Node.js 22+ and Python 3.12+.

```bash
npm ci
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Set the database and provider credentials in .env.
.venv/bin/python scripts/seed.py
.venv/bin/python scripts/migrate.py
.venv/bin/uvicorn api.index:app --host 127.0.0.1 --port 8000
# In a second terminal:
npm run dev
```

Open http://localhost:3000. FastAPI OpenAPI documentation is available at the configured docs route. Analytics stay in Python; React formats and renders API results.

## Database and reproducibility

`database/schema.sql` owns the `talentpulse` schema. The generator seeds a fixed eight-week window ending 4 October 2026, with 50,000 users, 100,000 jobs, 350,000 sessions and 2,510,875 ordered product events. It injects modeled mobile upload failures, new-user friction, market differences, a temporary release regression and a recommendation treatment effect. The UI discovers these patterns through queries.

The seed skips an already completed dataset. It commits bounded batches to support small Neon compute instances and writes its completion manifest after reconciliation. An interrupted initial load must be explicitly rebuilt with `--reset`. That reset affects only this application's schema; never point a reset at an unrelated production database. Use a direct Neon connection for migrations and seeding and a pooled connection for serverless requests.

Read [analytical methodology](docs/methodology.md), [demonstration walkthrough](docs/demo-walkthrough.md), [Power BI setup](powerbi/README.md), [full Adobe/Power BI connection guide](docs/integration-guide.md), and the backend API contract for metric definitions and practical limitations.

## Providers and credentials

- OpenRouter: `OPENROUTER_API_KEY`, default `OPENROUTER_MODEL=openai/gpt-4o`.
- Ollama Cloud: `OLLAMA_API_KEY`, default `OLLAMA_MODEL=gpt-oss:120b`. No local model download is required.
- Upload interpretation: `OLLAMA_INGEST_MODEL=gemma4:31b`. The UI can select supported cloud models returned by the provider catalog.
- Workspace credential encryption: generate a Fernet key for `APP_ENCRYPTION_KEY`; keep the same encrypted setting across deployments so saved connections remain readable.
- Power BI: native PostgreSQL connection plus your Microsoft account and workspace. Optional `POWERBI_EMBED_URL` enables an existing report.
- Adobe Analytics: your organization's OAuth credentials and report suite, when available. Synthetic Neon data works independently.

Shared provider keys are server-only. Personal connector credentials submitted through the workspace form are encrypted on the server and returned only as presence indicators. The browser stores a random private workspace token; the database stores only its hash. Preserve that token to retain access to your uploads and settings. Never commit `.env`, put keys in `NEXT_PUBLIC_*`, or include credentials in exported reports. Missing provider credentials leave the evidence mode and SQL analytics available. Public demo AI usage is bounded.

Adobe supports authorized REST reports and its official MCP endpoint, with bearer or server-to-server OAuth configuration. A connection is marked verified only after a real request succeeds. Power BI supports an authorized embed URL and optional REST report discovery. External MCP enrichment accepts public HTTPS endpoints and read-only tools. These connections need credentials from your own organization.

Uploads are limited to 3 MB, 10,000 rows and 20 columns per file. XLSX files must contain one values-only worksheet. Private uploaded data is searchable in Neon, and mapping/readiness checks explain missing fields before a funnel or experiment is calculated. Role-level comparisons are exploratory and adjusted across the displayed family; observational outcomes do not establish a causal model effect.

## Verify

```bash
npm run typecheck
npm run build
.venv/bin/python -m pytest tests -q
```

Tests cover important statistical and analytical boundaries. End-to-end validation also checks the real database, API contracts, UI filters, provider statuses and deployment routes.

Run `.venv/bin/python scripts/verify_dataset.py` to reconcile counts, funnel ordering, event attribution, experiment timing and binary user outcomes against the seed manifest. The verifier writes a local result under the ignored `artifacts` directory.

## Deploy

The repository includes Vercel configuration for Next.js and a Python FastAPI function. Configure encrypted environment variables before production deployment. The database is independently managed by Neon in Frankfurt. GitHub contains source and reproducibility instructions, not database passwords or provider credentials.

For an existing database, test the additive SQL files in `database/migrations` on an isolated Neon branch, then run `scripts/migrate.py` against the main direct connection. The extension preserves the seeded marketplace tables. Read the [upload contract](docs/uploads-api-contract.md), [workspace connector contract](docs/connectors-api-contract.md), [private feedback contract](docs/feedback-api-contract.md) and [public StepStone research](docs/stepstone-research.md) for integration details and the evidence behind the investigation ideas.

This lab is independent of and not endorsed by StepStone. It demonstrates SQL, Python, tracking design, product KPIs, funnel analysis, segmentation, release assessment, experiment statistics and grounded AI communication. It does not claim to describe internal StepStone systems or known company problems.
