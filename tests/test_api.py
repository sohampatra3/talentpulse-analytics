"""Protect analytics semantics, read-only boundaries and honest model output."""
import asyncio
from contextlib import contextmanager
from datetime import date

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.index import app
from api.analytics import investigation, metrics
from api.analytics.db import DatabaseUnavailable
from api.analytics.exports import csv_text
from api.analytics.filters import Filters
from api.analytics.integrations import integrations
from api.analytics.providers import ProviderFailure, extract_ranking, models


def test_live_logs_preserve_unknown_values_and_latency_components(monkeypatch):
    from api.analytics import providers
    calls = []
    class FakeConnection:
        def execute(self, sql, params):
            calls.append((sql, params))
    @contextmanager
    def fake_connection(readonly=True):
        yield FakeConnection()
    monkeypatch.setattr(providers, "connection", fake_connection)
    arm = {"id":"ollama","provider":"ollama","model":"gpt-oss:120b","status":"not_configured","latency_ms":None,"retrieval_latency_ms":1500,"inference_latency_ms":None,"cost_usd":None,"jobs":[]}
    providers.log_search("Product analyst", arm, "Germany")
    canonical = calls[0]
    compatibility = calls[1]
    assert "retrieval_latency_ms,inference_latency_ms" in canonical[0]
    assert canonical[1][7:11] == (None, 1500, None, None)
    assert compatibility[1][4:6] == (None, None)
    calls.clear()
    success = {**arm,"status":"success","latency_ms":4500,"inference_latency_ms":3000,"cost_usd":0.0033275}
    providers.log_search("Product analyst", success, "Germany")
    assert calls[0][1][7:11] == (4500,1500,3000,0.0033275)
    assert calls[1][1][4:6] == (4500,0.0033275)


def test_filters_are_parameterized_and_all_is_normalized():
    filters = Filters(market="All", device_type="mobile' OR TRUE--")
    where, params = filters.sql()
    assert "mobile" not in where
    assert "s.device_type = %s" in where
    assert params[-1] == "mobile' OR TRUE--"
    assert filters.market is None
    with pytest.raises(ValueError):
        filters.sql("untrusted_alias")


def test_filter_window_bounds():
    with pytest.raises(ValidationError):
        Filters(start_date="2026-10-04", end_date="2026-09-07")
    with pytest.raises(ValidationError):
        Filters(start_date="2024-01-01", end_date="2026-01-01")
    previous = Filters().previous()
    assert previous.start_date == date(2026, 8, 10)
    assert previous.end_date == date(2026, 9, 6)


def test_application_completion_has_application_start_denominator():
    item = metrics.complete_aggregate({"sessions": 100, "applications": 10, "application_starts": 20, "job_views": 50, "errors": 2, "avg_load_time_ms": 1250})
    assert item["conversion_rate"] == 10
    assert item["completion_rate"] == 50
    assert item["error_rate"] == 2
    empty = metrics.complete_aggregate({"sessions": 0})
    assert empty["conversion_rate"] == empty["completion_rate"] == 0


def test_overview_suppresses_deltas_without_previous_data(monkeypatch):
    current = metrics.complete_aggregate({"sessions": 100, "applications": 10, "application_starts": 20, "job_views": 50, "errors": 2, "completed_searches": 98, "avg_load_time_ms": 1250})
    empty = metrics.complete_aggregate({"sessions": 0, "applications": 0, "application_starts": 0, "job_views": 0, "errors": 0, "completed_searches": 0})
    monkeypatch.setattr(metrics, "aggregate", lambda filters: current if filters.end_date == date(2026, 10, 4) else empty)
    monkeypatch.setattr(metrics, "row", lambda sql, params=(): {"n": 300, "dau": 12, "wau": 60})
    monkeypatch.setattr(metrics, "segmented", lambda *args: {"rows": []})
    monkeypatch.setattr(metrics, "daily", lambda *args: [])
    result = metrics.overview.__wrapped__(Filters())
    assert all(kpi["delta"] is None for kpi in result["kpis"])
    assert result["product_metrics"]["application_completion_rate"] == 50


def test_release_intersects_device_filters_and_balances_windows(monkeypatch):
    monkeypatch.setattr(metrics, "rows", lambda sql: [{"release_id": "test", "release_name": "Mobile CV", "feature": "cv_upload", "release_date": "2026-09-18", "market": "Germany", "platform": "mobile"}])
    monkeypatch.setattr(metrics, "row", lambda sql: {"start_date": "2026-09-15", "end_date": "2026-09-30"})
    windows = []
    def aggregate(filters):
        windows.append(filters)
        return {"sessions": 100, "applications": 20, "application_starts": 40, "completion_rate": 50, "error_rate": 2, "latency_ms": 1000}
    monkeypatch.setattr(metrics, "aggregate", aggregate)
    assert metrics.releases.__wrapped__(Filters(device_type="desktop"))["releases"] == []
    result = metrics.releases.__wrapped__(Filters(device_type="mobile"))["releases"][0]
    assert result["window_days"] == 3
    assert windows[0].start_date == date(2026, 9, 15)
    assert windows[1].end_date == date(2026, 9, 20)
    assert windows[0].market == windows[1].market == "Germany"


def test_overview_deltas_require_current_dataset_coverage(monkeypatch):
    current = metrics.complete_aggregate({"sessions": 100, "applications": 10, "application_starts": 20, "job_views": 50, "errors": 2, "completed_searches": 98, "avg_load_time_ms": 1250})
    monkeypatch.setattr(metrics, "aggregate", lambda filters: dict(current))
    monkeypatch.setattr(metrics, "row", lambda sql, params=(): {"start_date": "2026-08-10", "end_date": "2026-10-04", "n": 300, "dau": 12, "wau": 60})
    monkeypatch.setattr(metrics, "segmented", lambda *args: {"rows": []})
    monkeypatch.setattr(metrics, "daily", lambda *args: [])
    result = metrics.overview.__wrapped__(Filters(start_date="2026-09-20", end_date="2026-10-07"))
    assert result["meta"]["comparison_available"] is False
    assert all(kpi["delta"] is None for kpi in result["kpis"])


def test_experiment_evidence_preserves_unknown_zero_exposure_rate(monkeypatch):
    monkeypatch.setattr(investigation, "experiment", lambda filters: {"arms": [{"label": "Manual SQL", "exposed_users": 0, "conversion_rate": None, "latency_ms": 0, "cost_usd": 0}], "comparisons": [{"variant": "gpt4o", "absolute_lift_pp": None, "adjusted_p_value": None}], "srm": {}, "filter_note": "Fixed window"})
    result = investigation.evidence_context.__wrapped__("Compare AI search with manual search", Filters())
    assert result["chart"]["data"][0]["conversion_rate"] is None
    assert "no exposed users" in result["answer"]
    assert "insufficient sample" in result["answer"]


def test_completion_question_selects_completion_chart(monkeypatch):
    monkeypatch.setattr(investigation, "aggregate", lambda filters: {"sessions": 100, "applications": 10, "conversion_rate": 10, "completion_rate": 50, "latency_ms": 500})
    monkeypatch.setattr(investigation, "daily", lambda filters: [{"date": "2026-10-04", "conversion_rate": 10, "completion_rate": 50}])
    result = investigation.evidence_context.__wrapped__("Visualize daily application completion trends", Filters())
    assert result["chart"]["y_key"] == "completion_rate"


def test_rank_output_cannot_invent_jobs_or_duplicate_ids():
    candidates = [{"job_id": 1, "job_title": "Product Analyst"}, {"job_id": 2, "job_title": "Data Analyst"}]
    selected, _ = extract_ranking('{"ranked_job_ids":[999,true,2,2,1],"explanation":"Matched roles"}', candidates, 5)
    assert [job["job_id"] for job in selected] == [2, 1]
    with pytest.raises(ProviderFailure):
        extract_ranking('{"ranked_job_ids":[999]}', candidates, 5)


def test_csv_protects_formula_cells_and_preserves_numeric_values():
    text = csv_text([{"title": "=HYPERLINK(x)", "count": -2, "metadata": ["test"]}])
    assert "'=HYPERLINK(x)" in text
    assert ",-2," in text


def test_provider_metadata_does_not_expose_keys(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-value")
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    result = models()
    assert "private-test-value" not in str(result)
    assert result["providers"][0]["status"] == "configured"
    assert result["providers"][1]["status"] == "not_configured"
    assert next(item for item in integrations()["integrations"] if item["id"] == "adobe")["status"] in ("configured", "not_configured")


def test_provider_numeric_prose_is_discarded(monkeypatch):
    monkeypatch.setattr(investigation, "configured", lambda provider: True)
    async def fake_complete(*args, **kwargs):
        return {"content": "Conversion improved 90%, proving the model wins."}
    monkeypatch.setattr(investigation, "complete", fake_complete)
    selected = {"answer": "Observed conversion is 10%.", "evidence": [{"label": "conversion", "value": 10, "unit": "percent"}], "chart": None, "context": {}, "limitations": []}
    result = asyncio.run(investigation.investigate("Explain conversion", False, "openrouter", Filters(), selected))
    assert result["mode"] == "evidence"
    assert "90%" not in result["answer"]
    assert "10%" in result["answer"]
    assert result["interpretation"] is None


def test_missing_database_returns_503_without_fake_data(monkeypatch):
    import api.index as endpoint
    def unavailable(*args, **kwargs):
        raise DatabaseUnavailable("Database unavailable")
    monkeypatch.setattr(endpoint, "row", unavailable)
    response = TestClient(app).get("/api/health")
    assert response.status_code == 503
    assert response.json()["code"] == "database_unavailable"
    assert "kpis" not in response.json()


def test_mcp_read_tools_and_invalid_tool_boundaries():
    client = TestClient(app)
    response = client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = response.json()["result"]["tools"]
    assert {tool["name"] for tool in tools} == {"overview", "funnel", "segments", "experiments", "releases", "data_quality", "tracking_plan"}
    assert all(tool["annotations"]["readOnlyHint"] for tool in tools)
    rejected = client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "execute_sql", "arguments": {"sql": "DROP TABLE x"}}})
    assert rejected.json()["error"]["code"] == -32602
    assert client.get("/api/mcp").status_code == 405
    assert client.post("/api/mcp",headers={"MCP-Protocol-Version":"unrecognized"},json={"jsonrpc":"2.0","id":3,"method":"ping"}).status_code == 400
    assert client.post("/api/mcp",headers={"Origin":"https://untrusted.example"},json={"jsonrpc":"2.0","id":4,"method":"ping"}).status_code == 403


def test_invalid_metric_and_dates_return_validation_error():
    client = TestClient(app)
    response = client.get("/api/segments?dimension=untrusted_sql")
    assert response.status_code == 422
    response = client.get("/api/overview?start_date=2026-10-04&end_date=2026-09-07")
    assert response.status_code == 422
