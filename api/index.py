"""TalentPulse API: Python owns analytics, statistics and model adapters."""
from __future__ import annotations

import asyncio
import os
import threading
import time
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[1] / ".env.local")

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from api.analytics.db import DatabaseUnavailable, row
from api.analytics.experiment_api import experiment
from api.analytics.exports import csv_text, dataset_rows
from api.analytics.filters import Filters
from api.analytics.integrations import check_adobe, export_metadata, integrations
from api.analytics.investigation import evidence_context, investigate
from api.analytics.metrics import filter_options, funnel, overview, releases, segmented
from api.analytics.providers import PROVIDERS, UsageLimitExceeded, catalog_candidates, configured, consume_usage, log_search, model_id, models, rank
from api.analytics.quality import quality, tracking

app = FastAPI(title="TalentPulse Analytics Lab", version="1.0.0", description="An independent synthetic job-search product analytics portfolio lab. Analytics, inference and model adapters are implemented in Python.", docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)

_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = threading.Lock()


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
    return await call_next(request)


def cached(name: str, filters: Filters | None, operation, *args):
    key = name + ":" + (filters.model_dump_json() if filters else "") + ":" + str(args)
    now = time.monotonic()
    with _cache_lock:
        value = _cache.get(key)
        if value and now - value[0] < 60:
            return value[1]
    result = operation(filters, *args) if filters else operation(*args)
    with _cache_lock:
        if len(_cache) >= 64:
            del _cache[min(_cache, key=lambda item: _cache[item][0])]
        _cache[key] = (now, result)
    return result


@app.exception_handler(DatabaseUnavailable)
async def unavailable_handler(request: Request, exc: DatabaseUnavailable):
    return JSONResponse(status_code=503, content={"detail": str(exc), "code": "database_unavailable", "synthetic": True})


@app.exception_handler(UsageLimitExceeded)
async def limit_handler(request: Request, exc: UsageLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": str(exc), "code": "ai_usage_limit"}, headers={"Retry-After": "3600"})


def get_filters(start_date: date = Query(date(2026, 9, 7)), end_date: date = Query(date(2026, 10, 4)), market: str | None = None, device_type: str | None = None, user_type: str | None = None, job_category: str | None = None, traffic_source: str | None = None, experience_level: str | None = None, variant: str | None = None) -> Filters:
    try:
        return Filters(start_date=start_date, end_date=end_date, market=market, device_type=device_type, user_type=user_type, job_category=job_category, traffic_source=traffic_source, experience_level=experience_level, variant=variant)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="; ".join(error["msg"] for error in exc.errors())) from exc


@app.get("/api/health")
def health():
    result = row("SELECT current_database() AS database,EXISTS(SELECT 1 FROM talentpulse.seed_manifest) AS data_ready")
    return {"status": "ok", "database": "connected", "data_ready": result["data_ready"], "synthetic": True, "version": "1.0.0"}


@app.get("/api/filters")
def options():
    return cached("filters", None, filter_options)


@app.get("/api/overview")
def get_overview(filters: Filters = Depends(get_filters)):
    return cached("overview", filters, overview)


@app.get("/api/funnel")
def get_funnel(filters: Filters = Depends(get_filters)):
    return cached("funnel", filters, funnel)


@app.get("/api/segments")
def get_segments(dimension: str = "device_type", metric: str = "completion_rate", filters: Filters = Depends(get_filters)):
    try:
        return cached("segments", filters, segmented, dimension, metric)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/experiments")
def get_experiments(filters: Filters = Depends(get_filters)):
    return cached("experiments", filters, experiment)


@app.get("/api/releases")
def get_releases(filters: Filters = Depends(get_filters)):
    return cached("releases", filters, releases)


@app.get("/api/data-quality")
def get_quality(filters: Filters = Depends(get_filters)):
    return cached("quality", filters, quality)


@app.get("/api/tracking-plan")
def get_tracking(filters: Filters = Depends(get_filters)):
    return cached("tracking", filters, tracking)


@app.get("/api/integrations")
def get_integrations():
    return integrations()


@app.post("/api/integrations/adobe/check")
async def adobe_check():
    return await check_adobe()


@app.get("/api/ai/models")
def get_models():
    return models()


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


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=800)
    visualize: bool = True
    provider: Literal["openrouter", "ollama"] = "openrouter"
    filters: Filters = Field(default_factory=Filters)


def client_address(request: Request):
    return request.headers.get("x-vercel-forwarded-for", request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")).split(",")[0].strip()


@app.post("/api/search/compare")
async def compare(body: SearchRequest, request: Request):
    started = time.perf_counter()
    candidates, total, fallback = await asyncio.to_thread(catalog_candidates, body.query.strip(), body.market, body.job_category)
    retrieval_ms = round((time.perf_counter() - started) * 1000)
    manual = {"id": "control", "label": "Manual SQL search", "provider": "postgresql", "model": None, "status": "success", "latency_ms": retrieval_ms, "retrieval_latency_ms": retrieval_ms, "inference_latency_ms": 0, "cost_usd": 0, "jobs": candidates[:body.limit], "explanation": "Parameterized full-text and keyword search over the synthetic Neon job catalog, ordered by lexical relevance and recency." if not fallback else "No lexical matches were found in this selection. These are the most recent catalog jobs, provided as an explicitly labelled fallback."}
    limit_message = None
    if candidates and any(configured(provider) for provider in PROVIDERS):
        try:
            await asyncio.to_thread(consume_usage, client_address(request))
        except UsageLimitExceeded as exc:
            limit_message = str(exc)
    if limit_message:
        ai = [{"id": "gpt4o" if provider == "openrouter" else "ollama", "label": model_id(provider), "provider": provider, "model": model_id(provider), "status": "rate_limited" if configured(provider) else "not_configured", "jobs": [], "latency_ms": 0, "cost_usd": None, "explanation": limit_message if configured(provider) else "Provider API key is not configured."} for provider in PROVIDERS]
    elif not candidates:
        ai = [{"id": "gpt4o" if provider == "openrouter" else "ollama", "label": model_id(provider), "provider": provider, "model": model_id(provider), "status": "no_candidates", "jobs": [], "latency_ms": 0, "cost_usd": None, "explanation": "No jobs exist for these filters; no provider inference was requested."} for provider in PROVIDERS]
    else:
        ai = await asyncio.gather(*(rank(provider, body.query.strip(), candidates, body.limit) for provider in PROVIDERS))
    for arm in ai:
        inference_ms = arm["latency_ms"] if arm["status"] in ("success", "error") else None
        arm["retrieval_latency_ms"] = retrieval_ms
        arm["inference_latency_ms"] = inference_ms
        arm["latency_ms"] = retrieval_ms + inference_ms if arm["status"] == "success" else None
    arms = [manual, *ai]
    logging_status = "recorded"
    for arm in arms:
        try:
            await asyncio.to_thread(log_search, body.query.strip(), arm, body.market)
        except DatabaseUnavailable:
            logging_status = "unavailable"
    return {"query": body.query.strip(), "synthetic_catalog": True, "catalog_size": total, "candidate_count": len(candidates), "arms": arms, "logging_status": logging_status, "measurement_note": "Successful-arm latency is shared SQL candidate retrieval plus provider inference, including their network time. Retrieval and inference components are also shown; rate-limit bookkeeping and telemetry logging are excluded. Null latency means no valid ranking was completed. Cost is reported only when the provider returns it; null means unavailable. Live requests are recorded separately from the synthetic historical experiment. These rankings do not update or validate synthetic model-conversion assumptions."}


@app.post("/api/ai/investigate")
async def investigate_question(body: InvestigationRequest, request: Request):
    selected = await asyncio.to_thread(evidence_context, body.question, body.filters)
    allow_inference = True
    if configured(body.provider):
        try:
            await asyncio.to_thread(consume_usage, client_address(request))
        except UsageLimitExceeded as exc:
            selected["limitations"].append(str(exc) + " The quantitative answer remains available in evidence mode.")
            allow_inference = False
    return await investigate(body.question, body.visualize, body.provider, body.filters, selected, allow_inference)


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
