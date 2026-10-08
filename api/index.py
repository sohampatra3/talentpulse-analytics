"""TalentPulse API: Python owns analytics, statistics and model adapters."""
from __future__ import annotations

import asyncio
import os
import threading
import time
import hashlib
from datetime import date
from contextlib import nullcontext
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[1] / ".env.local")

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from api.analytics.db import DatabaseUnavailable, connection, row
from api.analytics.experiment_api import experiment
from api.analytics.exports import csv_text, dataset_rows
from api.analytics.filters import Filters
from api.analytics.integrations import check_adobe, export_metadata, integrations
from api.analytics.investigation import evidence_context, investigate
from api.analytics.metrics import filter_options, funnel, overview, releases, segmented, job_role_drivers
from api.analytics.providers import PROVIDERS, UsageLimitExceeded, catalog_candidates, configured, consume_usage, log_search, model_id, models, rank, resolve_provider
from api.analytics.quality import quality, tracking
from api.analytics.connectors import router as connectors_router
from api.analytics.workspaces import workspace_identity, connector_config
from api.analytics.upload_router import router as uploads_router
from api.analytics.uploads import UploadError

app = FastAPI(title="TalentPulse Analytics Lab", version="1.1.0", description="An independent job-search product analytics portfolio lab with explicitly synthetic history and private uploaded evidence. Analytics, inference and model adapters are implemented in Python.", docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
app.include_router(connectors_router)
app.include_router(uploads_router)

_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = threading.Lock()
_inflight: dict[str, threading.Event] = {}
_cache_failures: dict[str, tuple[float, Exception]] = {}
_dataset_revisions: dict[tuple[str, str], int] = {}


def invalidate_dataset_cache(workspace_hash: str, dataset_id: str):
    prefix = "upload:" + workspace_hash + ":" + dataset_id + ":"
    with _cache_lock:
        key = (workspace_hash, dataset_id)
        _dataset_revisions[key] = _dataset_revisions.get(key, 0) + 1
        for store in (_cache, _cache_failures):
            for cache_key in list(store):
                if cache_key.startswith(prefix):
                    del store[cache_key]


def dataset_cache_name(identity: str, dataset_id: str, kind: str, metadata: dict | None = None):
    import json
    persisted_revision = hashlib.sha256(json.dumps({key: (metadata or {}).get(key) for key in ("kind", "mapping", "metadata", "row_count")}, sort_keys=True, default=str).encode()).hexdigest()[:20]
    with _cache_lock:
        revision = _dataset_revisions.get((identity, dataset_id), 0)
    return "upload:" + identity + ":" + dataset_id + ":" + persisted_revision + ":" + str(revision) + ":" + kind


@app.middleware("http")
async def validate_mcp_transport(request: Request, call_next):
    if request.url.path == "/api/mcp":
        protocol = request.headers.get("mcp-protocol-version")
        if protocol and protocol not in ("2025-06-18", "2025-03-26"):
            return JSONResponse(status_code=400, content={"detail": "Unsupported MCP protocol version"})
        origin = request.headers.get("origin")
        if origin:
            allowed = {str(request.base_url).rstrip("/")}
            forwarded_host = request.headers.get("x-forwarded-host")
            if forwarded_host:
                allowed.add(f"{request.headers.get('x-forwarded-proto', request.url.scheme)}://{forwarded_host}")
            allowed.update(value.strip().rstrip("/") for value in os.getenv("MCP_ALLOWED_ORIGINS", "").split(",") if value.strip())
            if os.getenv("VERCEL_URL"):
                allowed.add("https://" + os.environ["VERCEL_URL"])
            if origin.rstrip("/") not in allowed:
                return JSONResponse(status_code=403, content={"detail": "Origin is not allowed for this MCP endpoint"})
    response = await call_next(request)
    if request.headers.get("x-workspace-token"):
        response.headers["Cache-Control"] = "private, no-store"
    return response


def cached(name: str, filters: Filters | None, operation, *args):
    key = name + ":" + (filters.model_dump_json() if filters else "") + ":" + str(args)
    now = time.monotonic()
    with _cache_lock:
        value = _cache.get(key)
        if value and now - value[0] < 60:
            return value[1]
        failure = _cache_failures.get(key)
        if failure and now - failure[0] < 3:
            raise failure[1]
        event = _inflight.get(key)
        owner = event is None
        if owner:
            event = threading.Event()
            _inflight[key] = event
    if not owner:
        if not event.wait(timeout=35):
            raise DatabaseUnavailable("This analytics selection is still loading. Retry shortly.")
        with _cache_lock:
            value = _cache.get(key)
            failure = _cache_failures.get(key)
        if value:
            return value[1]
        if failure:
            raise failure[1]
        raise DatabaseUnavailable("The analytical request did not complete. Retry shortly.")
    try:
        result = operation(filters, *args) if filters else operation(*args)
        with _cache_lock:
            if len(_cache) >= 64:
                del _cache[min(_cache, key=lambda item: _cache[item][0])]
            _cache[key] = (time.monotonic(), result)
            _cache_failures.pop(key, None)
        return result
    except Exception as exc:
        with _cache_lock:
            if len(_cache_failures) >= 64:
                _cache_failures.clear()
            _cache_failures[key] = (time.monotonic(), exc)
        raise
    finally:
        with _cache_lock:
            _inflight.pop(key, None)
            event.set()


def source_analysis(kind: str, filters: Filters, request: Request, dataset_id: str | None, operation, *args):
    if not dataset_id:
        return cached(kind, filters, operation, *args)
    if not __import__("re").fullmatch(r"[0-9a-f-]{36}", dataset_id):
        raise HTTPException(422, "Choose a valid uploaded dataset")
    token = request.headers.get("x-workspace-token")
    from api.analytics.upload_analysis import analyze_dataset
    from api.analytics.uploads import get_dataset, UploadError
    try:
        with connection():
            identity = workspace_identity(token)
            dataset_metadata = get_dataset(dataset_id, token)
    except UploadError as exc:
        raise HTTPException(422, str(exc)) from exc
    # The token authorizes before cache lookup and never appears in the key.
    name = dataset_cache_name(identity, dataset_id, kind, dataset_metadata)
    def operation_uploaded(selection, *values):
        from api.analytics.uploads import UploadError
        try:
            return analyze_dataset(kind, dataset_id, token, selection, *values)
        except UploadError as exc:
            raise HTTPException(422, str(exc)) from exc
    return cached(name, filters, operation_uploaded, *args)


@app.exception_handler(DatabaseUnavailable)
async def unavailable_handler(request: Request, exc: DatabaseUnavailable):
    return JSONResponse(status_code=503, content={"detail": str(exc), "code": "database_unavailable", "synthetic": True})


@app.exception_handler(UsageLimitExceeded)
async def limit_handler(request: Request, exc: UsageLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": str(exc), "code": "ai_usage_limit"}, headers={"Retry-After": "3600"})


@app.exception_handler(UploadError)
async def upload_error_handler(request: Request, exc: UploadError):
    return JSONResponse(status_code=422, content={"detail": str(exc), "code": "uploaded_evidence_unavailable"})


def get_filters(start_date: date = Query(date(2026, 9, 7)), end_date: date = Query(date(2026, 10, 4)), market: str | None = None, device_type: str | None = None, user_type: str | None = None, job_category: str | None = None, traffic_source: str | None = None, experience_level: str | None = None, variant: str | None = None) -> Filters:
    try:
        return Filters(start_date=start_date, end_date=end_date, market=market, device_type=device_type, user_type=user_type, job_category=job_category, traffic_source=traffic_source, experience_level=experience_level, variant=variant)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="; ".join(error["msg"] for error in exc.errors())) from exc


@app.get("/api/health")
def health():
    return {"status": "alive", "database": "configured" if os.getenv("DATABASE_URL") else "not_configured", "database_verified": False, "synthetic": True, "version": "1.1.0", "database_check_url": "/api/health/database"}


@app.get("/api/health/database")
def database_health():
    result = row("SELECT current_database() AS database,EXISTS(SELECT 1 FROM talentpulse.seed_manifest) AS data_ready")
    return {"status": "ok", "database": "connected", "data_ready": result["data_ready"], "synthetic": True, "version": "1.0.0"}


@app.get("/api/filters")
def options(request: Request, dataset_id: str | None = None):
    if dataset_id:
        return source_analysis("filters", Filters(), request, dataset_id, filter_options)
    return cached("filters", None, filter_options)


@app.get("/api/overview")
def get_overview(request: Request, dataset_id: str | None = None, filters: Filters = Depends(get_filters)):
    return source_analysis("overview", filters, request, dataset_id, overview)


@app.get("/api/funnel")
def get_funnel(request: Request, dataset_id: str | None = None, filters: Filters = Depends(get_filters)):
    return source_analysis("funnel", filters, request, dataset_id, funnel)


@app.get("/api/segments")
def get_segments(request: Request, dimension: str = "device_type", metric: str = "completion_rate", dataset_id: str | None = None, filters: Filters = Depends(get_filters)):
    try:
        return source_analysis("segments", filters, request, dataset_id, segmented, dimension, metric)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/experiments")
def get_experiments(request: Request, dataset_id: str | None = None, filters: Filters = Depends(get_filters)):
    return source_analysis("experiments", filters, request, dataset_id, experiment)


@app.get("/api/releases")
def get_releases(request: Request, dataset_id: str | None = None, filters: Filters = Depends(get_filters)):
    return source_analysis("releases", filters, request, dataset_id, releases)


@app.get("/api/experiments/drivers")
def get_role_drivers(request: Request, role: str | None = Query(default=None, max_length=120), dataset_id: str | None = None, filters: Filters = Depends(get_filters)):
    if not dataset_id:
        return cached("role_drivers", filters, job_role_drivers, role)
    token = request.headers.get("x-workspace-token")
    from api.analytics.upload_analysis import role_drivers
    from api.analytics.uploads import UploadError, get_dataset
    try:
        with connection():
            identity = workspace_identity(token)
            metadata = get_dataset(dataset_id, token)
    except UploadError as exc:
        raise HTTPException(422, str(exc)) from exc
    def uploaded_role(selection, selected_role):
        try:
            return role_drivers(dataset_id, token, selected_role, selection)
        except UploadError as exc:
            raise HTTPException(422, str(exc)) from exc
    return cached(dataset_cache_name(identity, dataset_id, "drivers", metadata), filters, uploaded_role, role)


@app.get("/api/data-quality")
def get_quality(request: Request, dataset_id: str | None = None, filters: Filters = Depends(get_filters)):
    return source_analysis("quality", filters, request, dataset_id, quality)


@app.get("/api/tracking-plan")
def get_tracking(request: Request, dataset_id: str | None = None, filters: Filters = Depends(get_filters)):
    return source_analysis("tracking", filters, request, dataset_id, tracking)


@app.get("/api/integrations")
def get_integrations():
    return integrations()


@app.post("/api/integrations/adobe/check")
async def adobe_check():
    return await check_adobe()


@app.get("/api/ai/models")
def get_models(request: Request):
    result = models()
    token = request.headers.get("x-workspace-token")
    if token:
        with connection():
            identity = workspace_identity(token)
            result["workspace_id"] = identity[:12]
            for provider in result["providers"]:
                config = connector_config(identity, provider["id"])
                settings, saved = config["settings"], config["secrets"]
                provider["configured"] = bool(saved.get("api_key") or configured(provider["id"]))
                provider["credential_source"] = "workspace" if saved.get("api_key") else "deployment" if configured(provider["id"]) else "none"
                provider["status"] = config["last_status"] if config["last_status"] in ("verified", "error") else "configured" if provider["configured"] else "not_configured"
                for purpose in ("search", "analyst", "ingestion"):
                    selected = settings.get(purpose + "_model") or (settings.get("model") if settings.get("purpose", "search") == purpose else None)
                    if selected:
                        if purpose == "search":
                            result["defaults"][purpose][provider["id"]] = selected
                            provider["model"] = selected
                        elif purpose != "ingestion" or provider["id"] == "ollama":
                            result["defaults"][purpose] = {"provider": provider["id"], "model": selected}
    return result


@app.get("/api/export/metadata")
def metadata():
    return export_metadata()


@app.get("/api/export/{dataset}")
def export(dataset: str, filters: Filters = Depends(get_filters)):
    if dataset not in ("sessions", "daily", "experiments", "jobs", "tracking"):
        raise HTTPException(status_code=404, detail="Unknown export. Choose sessions, daily, experiments, jobs or tracking.")
    content = csv_text(dataset_rows(dataset, filters))
    return Response(content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="talentpulse-{dataset}-{filters.start_date}-{filters.end_date}.csv"', "Cache-Control": "no-store", **({"X-Export-Row-Limit": "10000", "X-Export-Scope": "capped-sample"} if dataset in ("sessions", "jobs") else {})})


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=240)
    market: str | None = Field(default=None, max_length=80)
    job_category: str | None = Field(default=None, max_length=80)
    limit: int = Field(default=5, ge=1, le=10)
    dataset_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    models: dict[Literal["openrouter", "ollama"], str] = Field(default_factory=dict)


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=800)
    visualize: bool = True
    provider: Literal["openrouter", "ollama"] = "openrouter"
    filters: Filters = Field(default_factory=Filters)
    model: str | None = Field(default=None, max_length=160)
    dataset_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    role: str | None = Field(default=None, max_length=120)


def client_address(request: Request):
    return request.headers.get("x-vercel-forwarded-for", request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")).split(",")[0].strip()


@app.post("/api/search/compare")
async def compare(body: SearchRequest, request: Request):
    started = time.perf_counter()
    token = request.headers.get("x-workspace-token")
    try:
        def resolve_options():
            with connection() if token else nullcontext():
                return {provider: resolve_provider(provider, token, body.models.get(provider), "search") for provider in PROVIDERS}
        provider_options = await asyncio.to_thread(resolve_options)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    retrieval_started = time.perf_counter()
    if body.dataset_id:
        await asyncio.to_thread(workspace_identity, token)
        from api.analytics.upload_analysis import uploaded_job_candidates
        from api.analytics.uploads import UploadError
        try:
            candidates, total, fallback = await asyncio.to_thread(uploaded_job_candidates, body.dataset_id, token, body.query.strip(), body.market, body.job_category)
        except UploadError as exc:
            raise HTTPException(422, str(exc)) from exc
    else:
        candidates, total, fallback = await asyncio.to_thread(catalog_candidates, body.query.strip(), body.market, body.job_category)
    retrieval_ms = round((time.perf_counter() - retrieval_started) * 1000)
    manual = {"id": "control", "label": "Manual SQL search", "provider": "postgresql", "model": None, "status": "success", "latency_ms": retrieval_ms, "retrieval_latency_ms": retrieval_ms, "inference_latency_ms": 0, "cost_usd": 0, "jobs": candidates[:body.limit], "explanation": "Parameterized full-text and keyword search over the synthetic Neon job catalog, ordered by lexical relevance and recency." if not fallback else "No lexical matches were found in this selection. These are the most recent catalog jobs, provided as an explicitly labelled fallback."}
    limit_message = None
    if candidates and any(option[1] for option in provider_options.values()):
        try:
            await asyncio.to_thread(consume_usage, client_address(request))
        except UsageLimitExceeded as exc:
            limit_message = str(exc)
    if limit_message:
        ai = [{"id": "gpt4o" if provider == "openrouter" else "ollama", "label": provider_options[provider][0], "provider": provider, "model": provider_options[provider][0], "status": "rate_limited" if provider_options[provider][1] else "not_configured", "jobs": [], "latency_ms": 0, "cost_usd": None, "explanation": limit_message if provider_options[provider][1] else "Provider API key is not configured."} for provider in PROVIDERS]
    elif not candidates:
        ai = [{"id": "gpt4o" if provider == "openrouter" else "ollama", "label": provider_options[provider][0], "provider": provider, "model": provider_options[provider][0], "status": "no_candidates", "jobs": [], "latency_ms": 0, "cost_usd": None, "explanation": "No jobs exist for these filters; no provider inference was requested."} for provider in PROVIDERS]
    else:
        ai = await asyncio.gather(*(rank(provider, body.query.strip(), candidates, body.limit, model=provider_options[provider][0], api_key=provider_options[provider][1]) for provider in PROVIDERS))
    for arm in ai:
        inference_ms = arm["latency_ms"] if arm["status"] in ("success", "error") else None
        arm["retrieval_latency_ms"] = retrieval_ms
        arm["inference_latency_ms"] = inference_ms
        arm["latency_ms"] = retrieval_ms + inference_ms if arm["status"] == "success" else None
    arms = [manual, *ai]
    logging_status = "recorded"
    for arm in arms:
        try:
            if body.dataset_id:
                from api.analytics.uploads import log_uploaded_search
                await asyncio.to_thread(log_uploaded_search, body.dataset_id, token, body.query.strip(), arm)
            else:
                await asyncio.to_thread(log_search, body.query.strip(), arm, body.market)
        except DatabaseUnavailable:
            logging_status = "unavailable"
    if body.dataset_id:
        for arm in arms:
            if arm["id"] == "control":
                arm["label"] = "Manual uploaded-catalog search"
                arm["explanation"] = "Lexical matching over authorized mapped rows in this private uploaded job catalog." if not fallback else "No lexical matches were found. These are explicitly labelled fallback rows from the same uploaded catalog."
    return {"query": body.query.strip(), "synthetic_catalog": not bool(body.dataset_id), "source": "uploaded_dataset" if body.dataset_id else "synthetic_neon", "dataset_id": body.dataset_id, "catalog_size": total, "candidate_count": len(candidates), "arms": arms, "logging_status": logging_status, "measurement_note": "Successful-arm latency is shared candidate retrieval plus provider inference, including their network time. Retrieval and inference components are also shown; configuration, rate-limit bookkeeping and telemetry logging are excluded. Null latency means no valid ranking was completed. Cost is reported only when the provider returns it; null means unavailable. Live requests are recorded separately from synthetic historical experiments. These rankings do not update or validate synthetic model-conversion assumptions."}


@app.post("/api/ai/investigate")
async def investigate_question(body: InvestigationRequest, request: Request):
    token = request.headers.get("x-workspace-token")
    try:
        selected_model, selected_key = await asyncio.to_thread(resolve_provider, body.provider, token, body.model, "analyst")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if body.role:
        if body.dataset_id:
            await asyncio.to_thread(workspace_identity, token)
            from api.analytics.upload_analysis import role_drivers
            driver_context = await asyncio.to_thread(role_drivers, body.dataset_id, token, None if body.role.lower() == "all" else body.role, body.filters)
        else:
            driver_context = await asyncio.to_thread(job_role_drivers, body.filters, body.role)
        support = driver_context["support"]
        arms = driver_context["arms"]
        chart_rows = [{"variant": arm["label"], "conversion_rate": arm.get("conversion_rate"), "sessions": arm.get("sessions")} for arm in arms]
        finding = f"For {body.role}, the available evidence contains {support['row_count']:,} records. "
        if support.get("session_count") is not None:
            finding += f"There are {support['session_count']:,} observed search sessions. "
        else:
            finding += "A search-session denominator is unavailable for this upload. "
        finding += "; ".join(f"{arm['label']}: {arm['conversion_rate']:.2f}% observed conversion" if arm.get("conversion_rate") is not None else f"{arm['label']}: conversion unavailable" for arm in arms)
        finding += ". Role and cohort breakdowns are observational; these data cannot establish a role-specific winner or causal explanation."
        selected = {"answer": finding, "evidence": [{"label": "Observed role sessions", "value": support["session_count"], "unit": "sessions"}, {"label": "Role records", "value": support["row_count"], "unit": "rows"}], "chart": {"type": "bar", "title": "Observed role conversion · no causal attribution", "x_key": "variant", "y_key": "conversion_rate", "data": chart_rows}, "context": driver_context, "limitations": driver_context["limitations"], "synthetic": not bool(body.dataset_id)}
    elif body.dataset_id:
        await asyncio.to_thread(workspace_identity, token)
        from api.analytics.upload_analysis import uploaded_evidence
        selected = await asyncio.to_thread(uploaded_evidence, body.dataset_id, token, body.question, body.filters)
        selected["synthetic"] = False
    else:
        selected = await asyncio.to_thread(evidence_context, body.question, body.filters)
    allow_inference = True
    if selected_key:
        try:
            await asyncio.to_thread(consume_usage, client_address(request))
        except UsageLimitExceeded as exc:
            selected["limitations"].append(str(exc) + " The quantitative answer remains available in evidence mode.")
            allow_inference = False
    return await investigate(body.question, body.visualize, body.provider, body.filters, selected, allow_inference, model=selected_model, api_key=selected_key)


MCP_TOOLS = {"overview": overview, "funnel": funnel, "experiments": experiment, "releases": releases, "data_quality": quality, "tracking_plan": tracking}
MCP_FILTER_SCHEMA = {"type": "object", "properties": {"start_date": {"type": "string", "format": "date"}, "end_date": {"type": "string", "format": "date"}, **{name: {"type": "string"} for name in ("market", "device_type", "user_type", "job_category", "traffic_source", "experience_level", "variant")}}, "additionalProperties": False}


@app.get("/api/mcp")
def mcp_documentation():
    return JSONResponse(status_code=405, headers={"Allow": "POST"}, content={"name": "TalentPulse read-only analytics MCP", "endpoint": "/api/mcp", "method": "POST", "transport": "Streamable HTTP, stateless JSON responses; this server does not offer a separate SSE stream", "protocol_versions": ["2025-06-18", "2025-03-26"], "tools": [*MCP_TOOLS, "segments"], "synthetic": True})


@app.post("/api/mcp")
def mcp_call(payload: dict):
    request_id = payload.get("id")
    method = payload.get("method")
    if payload.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32600, "message": "Invalid JSON-RPC request"}}
    if request_id is None and (isinstance(method, str) and method.startswith("notifications/") or "result" in payload or "error" in payload):
        return Response(status_code=202)
    params = payload.get("params") or {}
    if not isinstance(params, dict):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "params must be an object"}}
    result = None
    try:
        if method == "initialize":
            requested = params.get("protocolVersion")
            protocol = requested if requested in ("2025-06-18", "2025-03-26") else "2025-06-18"
            result = {"protocolVersion": protocol, "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "TalentPulse", "version": "1.0.0"}, "instructions": "Read-only aggregate analytics of an explicitly synthetic portfolio dataset. No arbitrary SQL or write tools."}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": [{"name": name, "description": f"Read synthetic {name.replace('_', ' ')} aggregate evidence. Fixed experiment window applies to experiments.", "inputSchema": MCP_FILTER_SCHEMA, "annotations": {"readOnlyHint": True, "destructiveHint": False}} for name in MCP_TOOLS] + [{"name": "segments", "description": "Read synthetic analytics by an allowlisted dimension and metric", "inputSchema": {**MCP_FILTER_SCHEMA, "properties": {**MCP_FILTER_SCHEMA["properties"], "dimension": {"type": "string"}, "metric": {"type": "string"}}}, "annotations": {"readOnlyHint": True, "destructiveHint": False}}]}
        elif method == "tools/call":
            import json
            arguments = dict(params.get("arguments") or {})
            name = params.get("name")
            if name == "segments":
                dimension, metric = arguments.pop("dimension", "device_type"), arguments.pop("metric", "completion_rate")
                evidence = cached("segments", Filters(**arguments), segmented, dimension, metric)
            elif name in MCP_TOOLS:
                evidence = cached(name, Filters(**arguments), MCP_TOOLS[name])
            else:
                raise ValueError("Unknown read-only analytics tool")
            result = {"content": [{"type": "text", "text": json.dumps(evidence, ensure_ascii=False)}], "isError": False}
        else:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except (ValueError, ValidationError, TypeError) as exc:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "Invalid tool arguments or unknown tool"}}
    except DatabaseUnavailable as exc:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": str(exc)}}
