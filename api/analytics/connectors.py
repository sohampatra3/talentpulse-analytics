"""Workspace-scoped external connectors; only returned evidence is displayed."""
from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import socket
import ssl
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

import httpcore
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .providers import complete, resolve_provider, validate_model
from .workspaces import connector_config, create_workspace, remove_connector, require_workspace_token, safe_config, save_check, save_connector, workspace_connectors, workspace_identity

router = APIRouter(prefix="/api")
_oauth_cache: dict[str, tuple[float, str]] = {}
SETTINGS = {"adobe": {"auth_type", "company_id", "report_suite_id", "dimension_id", "metric_ids", "experiment_dimension_id", "scopes", "org_id", "transport", "mcp_endpoint"}, "powerbi": {"embed_url", "group_id"}, "mcp": {"endpoint", "auth_type", "auth_header", "tool_name", "tool_arguments"}, "ollama": {"model", "purpose", "search_model", "analyst_model", "ingestion_model"}, "openrouter": {"model", "purpose", "search_model", "analyst_model"}}
SECRET_FIELDS = {"adobe": {"client_id", "access_token", "client_secret"}, "powerbi": {"access_token"}, "mcp": {"token"}, "ollama": {"api_key"}, "openrouter": {"api_key"}}


class ConnectorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    settings: dict = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)
    clear_secrets: bool = False


class AdobeReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_date: date
    end_date: date
    dimension: str | None = Field(default=None, max_length=120)
    metrics: list[str] | None = Field(default=None, max_length=10)
    segment_id: str | None = Field(default=None, max_length=150)
    limit: int = Field(default=25, ge=1, le=100)
    page: int = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def dates(self):
        if self.end_date < self.start_date or (self.end_date - self.start_date).days > 366:
            raise ValueError("Choose an inclusive date window no longer than 367 days")
        return self


class MCPEnrichmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool_name: str | None = Field(default=None, max_length=120)
    arguments: dict = Field(default_factory=dict)


def validate_endpoint(endpoint: str) -> str:
    if not isinstance(endpoint, str) or len(endpoint) > 1000:
        raise HTTPException(422, "Enter a public HTTPS MCP endpoint")
    parsed = urlparse(endpoint)
    try:
        port = parsed.port
    except ValueError:
        raise HTTPException(422, "Invalid MCP endpoint port")
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.query or parsed.fragment or port not in (None, 443):
        raise HTTPException(422, "MCP endpoints must use public HTTPS on port 443, with credentials supplied in encrypted auth fields rather than the URL")
    if "." not in host or host.endswith((".local", ".localhost", ".internal", ".test", ".invalid")):
        raise HTTPException(422, "Local and internal MCP hosts are not supported")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise HTTPException(422, "Use a public DNS hostname rather than an IP address")
    if not re.fullmatch(r"[a-z0-9.-]+", host) or ".." in host:
        raise HTTPException(422, "Invalid public MCP hostname")
    return endpoint


async def public_addresses(host: str, port: int) -> list[str]:
    try:
        records = await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM), timeout=3)
    except (OSError, TimeoutError) as exc:
        raise httpcore.ConnectError("MCP public hostname could not be resolved") from exc
    addresses = list(dict.fromkeys(item[4][0] for item in records))
    if not addresses or any(not ipaddress.ip_address(value).is_global or ipaddress.ip_address(value).is_multicast or ipaddress.ip_address(value).is_reserved for value in addresses):
        raise httpcore.ConnectError("MCP DNS resolved to a private, reserved or non-public address")
    return addresses


class PublicNetworkBackend(httpcore.AsyncNetworkBackend):
    """Pin the actual socket to validated addresses, preventing DNS rebinding."""
    def __init__(self):
        self.delegate = httpcore.AnyIOBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if port != 443:
            raise httpcore.ConnectError("Only public HTTPS connections are allowed")
        addresses = await public_addresses(host, port)
        return await self.delegate.connect_tcp(addresses[0], port, timeout=timeout, local_address=local_address, socket_options=socket_options)

    async def connect_unix_socket(self, *args, **kwargs):
        raise httpcore.ConnectError("Unix sockets are not supported")

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


def public_transport():
    # httpx delegates to this httpcore pool. TLS SNI still uses the original
    # origin hostname; only the network backend pins the checked socket IP.
    transport = httpx.AsyncHTTPTransport(trust_env=False)
    transport._pool = httpcore.AsyncConnectionPool(ssl_context=ssl.create_default_context(), network_backend=PublicNetworkBackend(), max_connections=2, max_keepalive_connections=0)
    return transport


async def mcp_rpc(client: httpx.AsyncClient, endpoint: str, headers: dict, request_id: int, method: str, params: dict | None = None) -> tuple[dict, str | None]:
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
    async with asyncio.timeout(15):
        async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
            if response.status_code != 200:
                raise HTTPException(502, f"Remote MCP returned HTTP {response.status_code}; verify endpoint and authorization")
            session = response.headers.get("mcp-session-id")
            if "text/event-stream" in response.headers.get("content-type", ""):
                data_lines = []
                size = 0
                async for line in response.aiter_lines():
                    size += len(line)
                    if size > 1_000_000:
                        raise HTTPException(502, "Remote MCP response exceeded the connector limit")
                    if line.startswith("data:"):
                        data_lines.append(line[5:].strip())
                    elif not line and data_lines:
                        data = json.loads("\n".join(data_lines)); data_lines = []
                        if data.get("id") == request_id:
                            return data, session
                raise HTTPException(502, "Remote MCP did not return a matching JSON-RPC response")
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > 1_000_000:
                    raise HTTPException(502, "Remote MCP response exceeded the connector limit")
            data = json.loads(body)
            if not isinstance(data, dict) or data.get("id") != request_id:
                raise HTTPException(502, "Remote MCP returned an invalid JSON-RPC response")
            return data, session


def mcp_headers(config: dict) -> dict:
    settings, saved = config["settings"], config["secrets"]
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json", "MCP-Protocol-Version": "2025-06-18"}
    auth = settings.get("auth_type", "none")
    if auth != "none":
        token = saved.get("token")
        if not token:
            raise HTTPException(422, "Save this workspace's MCP authentication token first")
        if auth == "bearer":
            headers["Authorization"] = "Bearer " + token
        else:
            headers[settings.get("auth_header", "X-API-Key")] = token
    return headers


async def mcp_session(config: dict, tool_name: str | None = None, arguments: dict | None = None) -> dict:
    endpoint = validate_endpoint(config["settings"].get("endpoint", ""))
    headers = mcp_headers(config)
    headers.update(config.get("headers_override", {}))
    headers["Accept"] = "application/json, text/event-stream"
    headers["Content-Type"] = "application/json"
    try:
        async with httpx.AsyncClient(transport=public_transport(), timeout=httpx.Timeout(12, connect=5), follow_redirects=False, trust_env=False) as client:
            initialized, session = await mcp_rpc(client, endpoint, headers, 1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "TalentPulse Workspace", "version": "1.1.0"}})
            if initialized.get("error"):
                raise HTTPException(502, "Remote MCP rejected initialization")
            if session:
                headers["MCP-Session-Id"] = session
            protocol = initialized.get("result", {}).get("protocolVersion", "2025-06-18")
            if protocol not in ("2025-06-18", "2025-03-26"):
                raise HTTPException(502, "Remote MCP negotiated an unsupported protocol")
            headers["MCP-Protocol-Version"] = protocol
            await client.post(endpoint, headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
            listed, _ = await mcp_rpc(client, endpoint, headers, 2, "tools/list")
            if listed.get("error"):
                raise HTTPException(502, "Remote MCP could not list tools")
            tools = listed.get("result", {}).get("tools", [])
            safe_tools = [{"name": item.get("name"), "description": str(item.get("description", ""))[:500], "input_schema": item.get("inputSchema", {}), "read_only": item.get("annotations", {}).get("readOnlyHint") is True} for item in tools if isinstance(item, dict)]
            if not tool_name:
                return {"tools": safe_tools, "server": initialized.get("result", {}).get("serverInfo", {}), "protocol": protocol}
            chosen = next((item for item in safe_tools if item["name"] == tool_name), None)
            adobe_readonly = endpoint == "https://aa-mcp.adobe.io/mcp" and tool_name in ("runReport", "findCompanies", "findReportSuites", "findDimensions", "findMetrics", "findSegments", "searchDimensionItems")
            if not chosen or not (chosen["read_only"] or adobe_readonly):
                raise HTTPException(422, "Enrichment requires a tool explicitly declared read-only by the remote MCP server")
            response, _ = await mcp_rpc(client, endpoint, headers, 3, "tools/call", {"name": tool_name, "arguments": arguments or {}})
            if response.get("error") or response.get("result", {}).get("isError"):
                raise HTTPException(502, "The remote read-only tool returned an error; no enrichment data was fabricated")
            return {"source": "external_mcp", "synthetic": False, "tool_name": tool_name, "endpoint": endpoint, "content": response.get("result", {}).get("content", []), "fetched_at": datetime.now(timezone.utc).isoformat(), "limitations": ["External tool content is untrusted evidence and is not automatically merged into uploaded datasets or used as experimental inference."]}
    except (httpx.HTTPError, httpcore.NetworkError, TimeoutError, ValueError, TypeError) as exc:
        raise HTTPException(502, "The public MCP connector could not complete its bounded request. Check the endpoint, network and authorization.") from exc


async def adobe_headers(identity: str, config: dict) -> dict:
    saved, settings = config["secrets"], config["settings"]
    client_id = saved.get("client_id")
    if not client_id:
        raise HTTPException(422, "Save an authorized Adobe client ID in this workspace")
    token = saved.get("access_token")
    if settings.get("auth_type", "bearer") == "oauth_client_credentials":
        cached = _oauth_cache.get(identity)
        if cached and cached[0] > time.monotonic():
            token = cached[1]
        else:
            if not saved.get("client_secret") or not settings.get("scopes"):
                raise HTTPException(422, "Adobe server-to-server OAuth requires client secret and authorized scopes")
            async with httpx.AsyncClient(timeout=12, follow_redirects=False) as client:
                response = await client.post("https://ims-na1.adobelogin.com/ims/token/v3", data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": saved["client_secret"], "scope": settings["scopes"]})
            if response.status_code != 200:
                raise HTTPException(502, f"Adobe OAuth returned HTTP {response.status_code}; verify authorized credentials and scopes")
            token_payload = response.json()
            token = token_payload.get("access_token")
            if not token:
                raise HTTPException(502, "Adobe OAuth returned no access token")
            _oauth_cache[identity] = (time.monotonic() + max(0, min(int(token_payload.get("expires_in", 3600)), 86400) - 90), token)
    if not token:
        raise HTTPException(422, "Save this workspace's Adobe access token or configure server-to-server OAuth")
    return {"Authorization": "Bearer " + token, "x-api-key": client_id, "Accept": "application/json", "Content-Type": "application/json"}


def redact_result(value, config: dict):
    sensitive = [item for item in config.get("secrets", {}).values() if isinstance(item, str) and len(item) >= 4]
    sensitive += [str(item).removeprefix("Bearer ") for key, item in config.get("headers_override", {}).items() if key.lower() in ("authorization", "x-api-key")]
    if isinstance(value, str):
        for secret in sensitive:
            value = value.replace(secret, "[redacted]")
        return value
    if isinstance(value, dict):
        return {key: redact_result(item, config) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_result(item, config) for item in value]
    return value


async def adobe_mcp_config(identity: str, config: dict) -> dict:
    endpoint = config["settings"].get("mcp_endpoint") or "https://aa-mcp.adobe.io/mcp"
    if endpoint != "https://aa-mcp.adobe.io/mcp":
        raise HTTPException(422, "Adobe MCP uses the documented https://aa-mcp.adobe.io/mcp endpoint")
    headers = await adobe_headers(identity, config)
    org = config["settings"].get("org_id")
    company = config["settings"].get("company_id")
    if not isinstance(org, str) or not re.fullmatch(r"[A-Za-z0-9@._\-]{1,160}", org) or not isinstance(company, str) or not re.fullmatch(r"[A-Za-z0-9_\-]{1,100}", company):
        raise HTTPException(422, "Adobe MCP requires your authorized IMS organization ID and global company ID")
    headers.update({"x-gw-ims-org-id": org, "x-global-company-id": company})
    return {"settings": {"endpoint": endpoint, "auth_type": "none"}, "secrets": config["secrets"], "headers_override": headers}


def adobe_identifier(value, prefix: str | None = None):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_./:\-]{1,150}", value) or ".." in value or (prefix and not value.startswith(prefix)):
        raise HTTPException(422, "Choose a valid Adobe identifier from your authorized report suite")
    return value


async def adobe_report(identity: str, config: dict, body: AdobeReportRequest) -> dict:
    settings = config["settings"]
    company = settings.get("company_id", "")
    if not re.fullmatch(r"[A-Za-z0-9_\-]{1,100}", company):
        raise HTTPException(422, "Save your Adobe global company ID first")
    suite = adobe_identifier(settings.get("report_suite_id", ""))
    dimension = adobe_identifier(body.dimension or settings.get("dimension_id") or "variables/daterangeday", "variables/")
    metric_ids = body.metrics or settings.get("metric_ids") or ["metrics/visits", "metrics/pageviews", "metrics/uniquevisitors"]
    if not isinstance(metric_ids, list) or not 1 <= len(metric_ids) <= 10:
        raise HTTPException(422, "Select one to ten Adobe metrics")
    metric_ids = [adobe_identifier(value, "metrics/") for value in metric_ids]
    end_exclusive = body.end_date + timedelta(days=1)
    date_range = f"{body.start_date}T00:00:00.000/{end_exclusive}T00:00:00.000"
    global_filters = [{"type": "dateRange", "dateRange": date_range}]
    if body.segment_id:
        global_filters.append({"type": "segment", "segmentId": adobe_identifier(body.segment_id)})
    payload = {"rsid": suite, "globalFilters": global_filters, "metricContainer": {"metrics": [{"columnId": str(index), "id": metric} for index, metric in enumerate(metric_ids)]}, "dimension": dimension, "settings": {"limit": body.limit, "page": body.page, "dimensionSort": "asc"}}
    endpoint = f"https://analytics.adobe.io/api/{company}/reports"
    try:
        headers = await adobe_headers(identity, config)
        async with httpx.AsyncClient(timeout=18, follow_redirects=False) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
        if response.status_code != 200:
            raise HTTPException(502, f"Adobe report returned HTTP {response.status_code}; verify report-suite access and selected dimensions/metrics")
        result = response.json()
        if result.get("error") or result.get("errorCode"):
            raise HTTPException(502, "Adobe returned a report error; no report values were substituted")
        def actual_numbers(values):
            return {metric: value if isinstance(value, (int, float)) and not isinstance(value, bool) else None for metric, value in zip(metric_ids, values)}
        report_rows = [{"item_id": item.get("itemId"), "label": item.get("value"), "values": actual_numbers(item.get("data", []))} for item in result.get("rows", [])]
        chart_data = [{"label": item["label"], **item["values"]} for item in report_rows]
        return {"source": "adobe_analytics", "synthetic": False, "status": "verified", "report_suite_id": suite, "dimension": dimension, "metrics": metric_ids, "rows": report_rows, "totals": actual_numbers(result.get("summaryData", {}).get("totals", [])), "pagination": {"page": result.get("number", body.page), "total_pages": result.get("totalPages"), "total_rows": result.get("totalElements"), "last_page": result.get("lastPage")}, "chart": {"type": "line" if dimension == "variables/daterangeday" else "bar", "title": "Adobe Analytics · actual returned metrics", "x_key": "label", "y_keys": metric_ids, "data": chart_data}, "provenance": {"endpoint": endpoint, "fetched_at": datetime.now(timezone.utc).isoformat(), "window": {"start_date": str(body.start_date), "end_date": str(body.end_date)}, "timezone": "Adobe report-suite timezone"}, "limitations": ["These are actual authorized Adobe report values, separate from synthetic telemetry and uploaded datasets.", "Metric counts and segment differences do not establish randomized experimental significance or explain causality.", "Custom event/eVar mappings must correspond to your own report suite. No job-role or experiment attribution is invented."]}
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(502, "The authorized Adobe report could not be completed. No report data was fabricated.") from exc


def validate_settings(connector_id: str, body: ConnectorUpdate):
    if connector_id not in SETTINGS or set(body.settings) - SETTINGS.get(connector_id, set()) or set(body.secrets) - SECRET_FIELDS.get(connector_id, set()):
        raise HTTPException(422, "Unsupported connector or configuration fields")
    if len(json.dumps(body.settings)) > 20000 or any(len(value) > 16000 for value in body.secrets.values()):
        raise HTTPException(422, "Connector configuration is too large")
    if any("\r" in value or "\n" in value for value in body.secrets.values()):
        raise HTTPException(422, "Authentication fields cannot contain line breaks")
    if connector_id == "mcp":
        if body.settings.get("endpoint"):
            validate_endpoint(body.settings["endpoint"])
        if body.settings.get("auth_type", "none") not in ("none", "bearer", "api_key") or body.settings.get("auth_header", "X-API-Key") not in ("Authorization", "X-API-Key", "api-key"):
            raise HTTPException(422, "Choose supported MCP authentication fields")
        if body.settings.get("tool_arguments") is not None and not isinstance(body.settings["tool_arguments"], dict):
            raise HTTPException(422, "MCP tool arguments must be a JSON object")
    if connector_id == "adobe":
        if body.settings.get("auth_type", "bearer") not in ("bearer", "oauth_client_credentials") or body.settings.get("transport", "rest") not in ("rest", "mcp"):
            raise HTTPException(422, "Choose supported Adobe REST/MCP and OAuth authentication")
        if body.settings.get("mcp_endpoint"):
            if body.settings["mcp_endpoint"] != "https://aa-mcp.adobe.io/mcp":
                raise HTTPException(422, "Use the documented Adobe Analytics MCP endpoint")
        if body.settings.get("metric_ids") is not None:
            values = body.settings["metric_ids"]
            if not isinstance(values, list) or not 1 <= len(values) <= 10:
                raise HTTPException(422, "Choose one to ten Adobe metric IDs")
            for value in values:
                adobe_identifier(value, "metrics/")
        for field in ("company_id", "report_suite_id", "dimension_id", "experiment_dimension_id", "scopes", "org_id", "transport", "auth_type"):
            if field in body.settings and (not isinstance(body.settings[field], str) or "\r" in body.settings[field] or "\n" in body.settings[field]):
                raise HTTPException(422, "Adobe configuration fields must be single-line strings")
    if connector_id == "powerbi" and body.settings.get("embed_url"):
        url = urlparse(body.settings["embed_url"])
        if url.scheme != "https" or url.hostname not in ("app.powerbi.com", "app.powerbigov.us") or url.username or url.password:
            raise HTTPException(422, "Use an authorized HTTPS Power BI embed URL")
    if connector_id in ("ollama", "openrouter"):
        if body.settings.get("purpose", "search") not in ("search", "analyst", "ingestion"):
            raise HTTPException(422, "Unknown model purpose")
        for key, value in body.settings.items():
            if key.endswith("model"):
                try:
                    validate_model(connector_id, value)
                except ValueError as exc:
                    raise HTTPException(422, str(exc)) from exc


@router.post("/workspaces")
def workspace_create():
    return create_workspace()


@router.get("/workspace/connectors")
def connectors_list(token: str = Depends(require_workspace_token)):
    return workspace_connectors(token)


@router.put("/workspace/connectors/{connector_id}")
def connector_update(connector_id: str, body: ConnectorUpdate, token: str = Depends(require_workspace_token)):
    validate_settings(connector_id, body)
    identity = workspace_identity(token)
    _oauth_cache.pop(identity, None)
    return {"connector": save_connector(identity, connector_id, body.settings, body.secrets, body.clear_secrets)}


@router.delete("/workspace/connectors/{connector_id}")
def connector_delete(connector_id: str, token: str = Depends(require_workspace_token)):
    identity = workspace_identity(token)
    remove_connector(identity, connector_id)
    _oauth_cache.pop(identity, None)
    return {"deleted": True, "id": connector_id}


@router.post("/workspace/connectors/{connector_id}/check")
async def connector_check(connector_id: str, token: str = Depends(require_workspace_token)):
    identity = await asyncio.to_thread(workspace_identity, token)
    config = await asyncio.to_thread(connector_config, identity, connector_id)
    result = {"status": "not_configured", "verified": False, "detail": "Save this workspace's connector configuration first", "checked_at": datetime.now(timezone.utc).isoformat(), "capabilities": []}
    try:
        if connector_id == "adobe":
            if config["settings"].get("transport", "rest") == "mcp":
                remote = await adobe_mcp_config(identity, config)
                details = await mcp_session(remote)
                result.update(status="verified", verified=True, detail="The authorized Adobe Analytics MCP endpoint initialized and returned actual tools", capabilities=["Adobe MCP", "Read-only reports", "OAuth"], details=redact_result(details, remote))
                await asyncio.to_thread(save_check, identity, connector_id, result)
                return result
            headers = await adobe_headers(identity, config)
            async with httpx.AsyncClient(timeout=12, follow_redirects=False) as client:
                response = await client.get("https://analytics.adobe.io/discovery/me", headers=headers)
            if response.status_code != 200:
                raise HTTPException(502, f"Adobe discovery returned HTTP {response.status_code}")
            payload = response.json()
            companies = [{"company_id": company.get("globalCompanyId"), "company_name": company.get("companyName")} for org in payload.get("imsOrgs", []) for company in org.get("companies", [])]
            result.update(status="verified", verified=True, detail="Authorized Adobe Analytics discovery succeeded; report values require your own report suite and metric mappings", capabilities=["REST discovery", "Reports", "OAuth"], details={"companies": companies})
        elif connector_id == "mcp":
            details = await mcp_session(config)
            result.update(status="verified", verified=True, detail="The public MCP endpoint initialized and returned actual tools", capabilities=["MCP discovery", "Read-only enrichment"], details=details)
        elif connector_id == "powerbi":
            settings, saved = config["settings"], config["secrets"]
            if saved.get("access_token"):
                group = settings.get("group_id")
                if group and not re.fullmatch(r"[0-9a-fA-F-]{36}", group):
                    raise HTTPException(422, "Enter a valid Power BI group UUID")
                endpoint = f"https://api.powerbi.com/v1.0/myorg/groups/{group}/reports" if group else "https://api.powerbi.com/v1.0/myorg/reports"
                async with httpx.AsyncClient(timeout=12, follow_redirects=False) as client:
                    response = await client.get(endpoint, headers={"Authorization": "Bearer " + saved["access_token"]})
                if response.status_code != 200:
                    raise HTTPException(502, f"Power BI returned HTTP {response.status_code}")
                result.update(status="verified", verified=True, detail="Authorized Power BI report listing succeeded", capabilities=["REST report listing"], details={"reports": [{"id": item.get("id"), "name": item.get("name"), "web_url": item.get("webUrl")} for item in response.json().get("value", [])][:100]})
            elif settings.get("embed_url"):
                result.update(status="configured", detail="Embed URL is configured. Authentication and report availability have not been verified", capabilities=["Published report URL"])
        elif connector_id in ("ollama", "openrouter"):
            model, key = await asyncio.to_thread(resolve_provider, connector_id, token)
            if not key:
                raise HTTPException(422, "No workspace or server provider API key is configured")
            from .providers import consume_usage
            await asyncio.to_thread(consume_usage, "workspace:" + identity)
            response = await complete(connector_id, "Reply with a short plain confirmation; do not include credentials.", "Confirm that this cloud chat model can respond.", max_tokens=200, model=model, api_key=key)
            result.update(status="verified", verified=True, detail="The selected cloud model returned an actual response", capabilities=["Cloud inference"], details={"model": response["model"], "latency_ms": response["latency_ms"]})
    except HTTPException as exc:
        result.update(status="error", verified=False, detail=exc.detail)
    except (httpx.HTTPError, ValueError, TypeError, RuntimeError):
        result.update(status="error", verified=False, detail="The connector did not complete its bounded verification request; no connection was assumed")
    result = redact_result(result, config)
    await asyncio.to_thread(save_check, identity, connector_id, result)
    return result


@router.post("/workspace/adobe/report")
async def get_adobe_report(body: AdobeReportRequest, token: str = Depends(require_workspace_token)):
    identity = await asyncio.to_thread(workspace_identity, token)
    config = await asyncio.to_thread(connector_config, identity, "adobe")
    return await adobe_report(identity, config, body)


@router.post("/workspace/mcp/enrich")
async def mcp_enrich(body: MCPEnrichmentRequest, token: str = Depends(require_workspace_token)):
    identity = await asyncio.to_thread(workspace_identity, token)
    config = await asyncio.to_thread(connector_config, identity, "mcp")
    return redact_result(await mcp_session(config, body.tool_name or config["settings"].get("tool_name"), body.arguments or config["settings"].get("tool_arguments") or {}), config)


@router.post("/workspace/adobe/mcp/report")
async def get_adobe_mcp_report(body: AdobeReportRequest, token: str = Depends(require_workspace_token)):
    identity = await asyncio.to_thread(workspace_identity, token)
    config = await asyncio.to_thread(connector_config, identity, "adobe")
    remote = await adobe_mcp_config(identity, config)
    settings = config["settings"]
    suite = adobe_identifier(settings.get("report_suite_id", ""))
    dimension = adobe_identifier(body.dimension or settings.get("dimension_id") or "variables/daterangeday", "variables/")
    metrics = body.metrics or settings.get("metric_ids") or ["metrics/visits"]
    metrics = [adobe_identifier(item, "metrics/") for item in metrics]
    arguments = {"globalCompanyId": settings["company_id"], "reportSuiteId": suite, "dimensionId": dimension, "metricIds": ",".join(metrics), "startDate": str(body.start_date) + "T00:00:00", "endDate": str(body.end_date + timedelta(days=1)) + "T00:00:00", "limit": body.limit}
    if body.segment_id:
        arguments["segmentIds"] = adobe_identifier(body.segment_id)
    result = redact_result(await mcp_session(remote, "runReport", arguments), remote)
    result.update(source="adobe_analytics_mcp", report_suite_id=suite, dimension=dimension, metrics=metrics, provenance={"endpoint": remote["settings"]["endpoint"], "window": {"start_date": str(body.start_date), "end_date": str(body.end_date)}})
    return result
