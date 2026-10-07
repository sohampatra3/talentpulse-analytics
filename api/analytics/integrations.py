from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx

from .providers import models


def integrations() -> dict:
    adobe = all(os.getenv(key) for key in ("ADOBE_CLIENT_ID", "ADOBE_ACCESS_TOKEN"))
    powerbi_embed = os.getenv("POWERBI_EMBED_URL", "")
    powerbi = bool(powerbi_embed and urlparse(powerbi_embed).hostname in ("app.powerbi.com", "app.powerbigov.us"))
    providers = models()["providers"]
    items = [
        {"id": "neon", "name": "Neon PostgreSQL", "type": "database", "configured": bool(os.getenv("DATABASE_URL")), "status": "configured" if os.getenv("DATABASE_URL") else "not_configured", "description": "The dashboard queries real PostgreSQL tables containing labelled synthetic telemetry. Health checks verify a live database read.", "required_env": ["DATABASE_URL"], "capabilities": ["Parameterized SQL", "Synthetic events", "Read-only BI views", "CSV export"], "setup_url": "https://neon.com/docs/connect/connect-from-any-app"},
        {"id": "adobe", "name": "Adobe Analytics", "type": "analytics", "configured": adobe, "status": "configured" if adobe else "not_configured", "description": "Optional Adobe Analytics 2.0 REST adapter. Supply your own authorized OAuth token and client ID, then verify the connection with a read-only discovery request.", "required_env": ["ADOBE_CLIENT_ID", "ADOBE_ACCESS_TOKEN", "ADOBE_COMPANY_ID", "ADOBE_REPORT_SUITE_ID"], "capabilities": ["Company discovery", "Report-suite configuration", "OAuth bearer authentication"], "setup_url": "https://developer.adobe.com/analytics-apis/docs/2.0/", "details": {"company_id": os.getenv("ADOBE_COMPANY_ID") or None, "report_suite_id": os.getenv("ADOBE_REPORT_SUITE_ID") or None, "check_endpoint": "/api/integrations/adobe/check"}},
        {"id": "powerbi", "name": "Microsoft Power BI", "type": "business_intelligence", "configured": powerbi, "status": "configured" if powerbi else "not_configured", "description": "Connect Power BI Desktop to the Neon PostgreSQL BI views using your own read-only database account. An optional Power BI embed URL opens a published report; embedded reports follow Microsoft's own access rules.", "required_env": ["POWERBI_EMBED_URL (optional)"], "capabilities": ["PostgreSQL connector", "BI views", "CSV import", "Published report URL"], "setup_url": "https://learn.microsoft.com/en-us/power-query/connectors/postgresql", "details": {"embed_url": powerbi_embed if powerbi else None, "metadata_url": "/api/export/metadata"}},
        {"id": "mcp", "name": "Read-only analytics MCP", "type": "mcp", "configured": True, "status": "available", "description": "A runnable JSON-RPC MCP endpoint for aggregate analytics. It exposes allowlisted read tools; credentials and arbitrary SQL are never exposed.", "required_env": [], "capabilities": ["Overview", "Funnel", "Segments", "Experiments", "Releases", "Data quality", "Tracking plan"], "setup_url": "https://modelcontextprotocol.io/specification/2025-06-18/basic/transports", "details": {"endpoint": "/api/mcp"}},
    ]
    for provider in providers:
        items.append({**provider, "name": provider["label"], "type": "model_provider", "required_env": ["OPENROUTER_API_KEY" if provider["id"] == "openrouter" else "OLLAMA_API_KEY"], "capabilities": ["Live candidate ranking", "Evidence-grounded analyst explanations"], "setup_url": "https://openrouter.ai/docs/quickstart" if provider["id"] == "openrouter" else "https://docs.ollama.com/cloud"})
    return {"integrations": items, "exports": [{"id": dataset, "label": label, "url": f"/api/export/{dataset}"} for dataset, label in (("daily", "Daily KPI data"), ("experiments", "Experiment summary"), ("sessions", "Session sample · up to 10,000"), ("jobs", "Synthetic job sample · up to 10,000"), ("tracking", "Tracking specification"))], "mcp": {"endpoint": "/api/mcp", "transport": "Streamable HTTP · JSON responses · stateless", "tools": ["overview", "funnel", "segments", "experiments", "releases", "data_quality", "tracking_plan"]}, "synthetic": True}


async def check_adobe() -> dict:
    client_id, access_token = os.getenv("ADOBE_CLIENT_ID"), os.getenv("ADOBE_ACCESS_TOKEN")
    if not client_id or not access_token:
        return {"status": "not_configured", "connected": False, "detail": "Configure ADOBE_CLIENT_ID and ADOBE_ACCESS_TOKEN on the server before checking an authorized Adobe account."}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get("https://analytics.adobe.io/discovery/me", headers={"Authorization": f"Bearer {access_token}", "x-api-key": client_id, "Accept": "application/json"})
        if response.status_code != 200:
            return {"status": "error", "connected": False, "detail": f"Adobe returned HTTP {response.status_code}. Refresh the OAuth token and confirm the API project permissions."}
        payload = response.json()
        companies = [{"company_name": company.get("companyName"), "company_id": company.get("globalCompanyId")} for company in payload.get("imsOrgs", []) for company in company.get("companies", [])]
        return {"status": "connected", "connected": True, "companies": companies, "detail": "Live read-only Adobe Analytics discovery succeeded. Production Adobe data is not mixed into this synthetic lab."}
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        return {"status": "error", "connected": False, "detail": "Adobe discovery could not be completed. Retry or check authorized OAuth configuration."}


def export_metadata() -> dict:
    parsed = urlparse(os.getenv("DATABASE_URL", ""))
    return {"synthetic": True, "postgresql": {"server": parsed.hostname, "database": parsed.path.strip("/") or None, "ssl": "required", "authentication": "Use your own dedicated read-only PostgreSQL user; credentials are never returned by this API."}, "views": ["talentpulse.powerbi_daily_kpis", "talentpulse.powerbi_experiment_users", "talentpulse.powerbi_funnel_segments"], "sql_templates": {"daily": "SELECT * FROM talentpulse.powerbi_daily_kpis ORDER BY date,market;", "experiments": "SELECT variant,COUNT(*) AS assigned_users,COUNT(*) FILTER(WHERE exposed) AS exposed_users,COUNT(*) FILTER(WHERE converted) AS converted_users FROM talentpulse.powerbi_experiment_users GROUP BY variant;", "funnel": "SELECT * FROM talentpulse.powerbi_funnel_segments ORDER BY date,market;"}, "powerbi": {"steps": ["In Power BI Desktop, choose Get Data → PostgreSQL database.", "Enter the server and database shown above, using an authorized read-only database account and SSL.", "Select the talentpulse.powerbi_* views, then import the supplied DAX measures from the repository."], "rate_note": "The database BI views expose fractional rates (0–1); format as percentage in Power BI. Dashboard JSON rates are percentages (0–100)."}, "csv": {"max_session_rows": 10000, "max_job_rows": 10000, "formula_injection_protection": True, "note": "Session and job CSV downloads are capped samples to stay within hosted response limits. Use the authorized PostgreSQL connection for full data."}}
