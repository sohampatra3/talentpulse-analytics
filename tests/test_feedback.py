"""Private feedback bounds, ownership, workflow gates and safe spreadsheet export."""
from contextlib import contextmanager
import csv
import io
from uuid import UUID

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from api.analytics import feedback
from api.index import app


TOKEN = "a" * 64
IDENTITY = "owned-workspace-hash"
ITEM_ID = UUID("12345678-1234-1234-1234-123456789abc")
DATASET_ID = UUID("22345678-1234-1234-1234-123456789abc")
BRIEF = {
    "hypothesis": "Simplify mobile application fields to reduce abandonment.",
    "primary_metric": "Submitted applications / exposed candidates",
    "guardrail": "Application error rate and application quality",
    "success_criteria": "Pre-registered lift, fixed sample and unchanged guardrails",
    "next_step": "Review tracking coverage before running a candidate test.",
}


@pytest.fixture(autouse=True)
def no_real_database(monkeypatch):
    from api.analytics import db

    monkeypatch.setattr(
        db.psycopg,
        "connect",
        lambda *args, **kwargs: pytest.fail("Feedback unit tests must not contact Neon"),
    )


class Cursor:
    def __init__(self, result):
        self.result = result

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result


class ScriptedConnection:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        assert self.results, "Unexpected database operation"
        return Cursor(self.results.pop(0))


def install_connection(monkeypatch, results):
    conn = ScriptedConnection(results)

    @contextmanager
    def fake_connection(**kwargs):
        yield conn

    monkeypatch.setattr(feedback, "connection", fake_connection)
    monkeypatch.setattr(feedback, "workspace_identity", lambda token: IDENTITY)
    return conn


def create_body(**changes):
    return feedback.FeedbackCreate(
        **{"title": "Inspect mobile application friction", "observation": "Candidates abandon after the application form opens.", **changes}
    )


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/api/workspace/feedback", None),
        ("GET", "/api/workspace/feedback/export/csv", None),
        ("POST", "/api/workspace/feedback", {"title": "A signal", "observation": "A sufficiently detailed observation"}),
        ("PATCH", f"/api/workspace/feedback/{ITEM_ID}", {"status": "closed"}),
        ("DELETE", f"/api/workspace/feedback/{ITEM_ID}", None),
    ],
)
def test_all_feedback_endpoints_require_workspace_token(method, path, body):
    response = TestClient(app).request(method, path, json=body)
    assert response.status_code == 401


@pytest.mark.parametrize(
    "changes",
    [
        {"title": "ab"},
        {"title": " " * 10},
        {"title": "x" * 161},
        {"observation": "too short"},
        {"observation": "x" * 2001},
        {"hypothesis": "x" * 1001},
        {"primary_metric": "x" * 201},
        {"guardrail": "x" * 301},
        {"success_criteria": "x" * 501},
        {"next_step": "x" * 501},
        {"area": "unsupported"},
        {"source": "invented_source"},
        {"priority": "critical"},
        {"status": "closed"},
        {"workspace_hash": "someone-else"},
    ],
)
def test_feedback_creation_rejects_invalid_bounds_enums_and_untrusted_fields(changes):
    with pytest.raises(ValidationError):
        create_body(**changes)


def test_exact_text_bounds_are_accepted_and_whitespace_is_trimmed():
    body = create_body(
        title=" " + "x" * 160 + " ", observation="x" * 2000,
        hypothesis="x" * 1000, primary_metric="x" * 200, guardrail="x" * 300,
        success_criteria="x" * 500, next_step="x" * 500,
    )
    assert len(body.title) == 160
    assert body.context.dataset_name == "Synthetic product telemetry"


@pytest.mark.parametrize("context", [
    {"dataset_name": "x" * 201},
    {"market": "x" * 81},
    {"device": "x" * 81},
    {"user_type": "x" * 81},
    {"dataset_id": "another-owner"},
    {"start_date": "2026-02-29"},
    {"start_date": "2026-13-01"},
    {"end_date": "2026-10-32"},
    {"start_date": "2026-10-08", "end_date": "2026-10-01"},
    {"synthetic": False},
])
def test_context_rejects_unbounded_names_invalid_dates_reversed_windows_and_extra_fields(context):
    with pytest.raises(ValidationError):
        feedback.FeedbackContext(**context)


def test_context_accepts_empty_or_valid_inclusive_calendar_window():
    empty = feedback.FeedbackContext()
    assert empty.model_dump(mode="json")["start_date"] == ""
    valid = feedback.FeedbackContext(start_date="2028-02-29", end_date="2028-02-29")
    assert valid.model_dump(mode="json")["start_date"] == "2028-02-29"


@pytest.mark.parametrize("counts", [
    {"workspace": feedback.WORKSPACE_LIMIT, "total": feedback.WORKSPACE_LIMIT},
    {"workspace": 0, "total": feedback.GLOBAL_LIMIT},
])
def test_storage_limits_are_checked_under_transaction_lock_before_insert(monkeypatch, counts):
    conn = install_connection(monkeypatch, [None, counts])
    with pytest.raises(HTTPException) as exc:
        feedback.create_item(TOKEN, create_body())
    assert exc.value.status_code == 429
    assert "pg_advisory_xact_lock" in conn.calls[0][0]
    assert conn.calls[1][1] == (IDENTITY,)
    assert all("INSERT" not in sql for sql, _ in conn.calls)


def test_creation_below_both_quotas_keeps_workspace_identity_server_owned(monkeypatch):
    conn = install_connection(monkeypatch, [None, {"workspace": feedback.WORKSPACE_LIMIT - 1, "total": feedback.GLOBAL_LIMIT - 1}, {"id": str(ITEM_ID), "status": "new"}])
    result = feedback.create_item(TOKEN, create_body())
    assert result["status"] == "new"
    assert "INSERT INTO talentpulse.feedback_items" in conn.calls[2][0]
    assert conn.calls[2][1][1] == IDENTITY
    assert TOKEN not in repr(conn.calls)


def test_unowned_uploaded_context_is_rejected_before_storage_changes(monkeypatch):
    conn = install_connection(monkeypatch, [None])
    with pytest.raises(HTTPException) as exc:
        feedback.create_item(TOKEN, create_body(context={"dataset_id": str(DATASET_ID)}))
    assert exc.value.status_code == 404
    assert len(conn.calls) == 1
    sql, params = conn.calls[0]
    assert "workspace_hash=%s AND dataset_id=%s" in sql
    assert params == (IDENTITY, str(DATASET_ID))


def test_feedback_list_query_cannot_read_another_workspace(monkeypatch):
    conn = install_connection(monkeypatch, [[{"id": str(ITEM_ID), "title": "Owned signal"}]])
    assert feedback.list_items(TOKEN)[0]["title"] == "Owned signal"
    sql, params = conn.calls[0]
    assert "WHERE workspace_hash=%s" in sql
    assert params == (IDENTITY, feedback.WORKSPACE_LIMIT)


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_foreign_item_returns_not_found_with_owner_scoped_query(monkeypatch, operation):
    conn = install_connection(monkeypatch, [None])
    with pytest.raises(HTTPException) as exc:
        if operation == "update":
            feedback.update_item(TOKEN, ITEM_ID, feedback.FeedbackUpdate(status="closed"))
        else:
            feedback.delete_feedback(ITEM_ID, TOKEN)
    assert exc.value.status_code == 404
    assert len(conn.calls) == 1
    sql, params = conn.calls[0]
    assert "WHERE id=%s AND workspace_hash=%s" in sql
    assert params == (str(ITEM_ID), IDENTITY)


@pytest.mark.parametrize("missing", ["hypothesis", "primary_metric", "guardrail", "success_criteria"])
def test_experiment_ready_requires_every_test_brief_field(monkeypatch, missing):
    conn = install_connection(monkeypatch, [{**BRIEF, missing: ""}])
    with pytest.raises(HTTPException) as exc:
        feedback.update_item(TOKEN, ITEM_ID, feedback.FeedbackUpdate(status="experiment_ready"))
    assert exc.value.status_code == 422
    assert all(not sql.startswith("UPDATE") for sql, _ in conn.calls)


def test_complete_brief_can_advance_with_owner_scoped_update(monkeypatch):
    conn = install_connection(monkeypatch, [BRIEF, {"id": str(ITEM_ID), "status": "experiment_ready", "next_step": "Run the registered test"}])
    result = feedback.update_item(TOKEN, ITEM_ID, feedback.FeedbackUpdate(status="experiment_ready", next_step="Run the registered test"))
    assert result["status"] == "experiment_ready"
    assert "FOR UPDATE" in conn.calls[0][0]
    assert "WHERE id=%s AND workspace_hash=%s" in conn.calls[1][0]
    assert conn.calls[1][1] == ("experiment_ready", "Run the registered test", str(ITEM_ID), IDENTITY)


def test_status_only_patch_preserves_existing_next_action(monkeypatch):
    conn = install_connection(monkeypatch, [BRIEF, {"status": "investigating", "next_step": BRIEF["next_step"]}])
    feedback.update_item(TOKEN, ITEM_ID, feedback.FeedbackUpdate(status="investigating"))
    query, params = conn.calls[1]
    assert params[1] == BRIEF["next_step"] or (params[1] is None and "COALESCE" in query.upper())
    assert params[-2:] == (str(ITEM_ID), IDENTITY)


def test_explicit_empty_action_can_clear_the_saved_action(monkeypatch):
    conn = install_connection(monkeypatch, [BRIEF, {"status": "investigating", "next_step": ""}])
    feedback.update_item(TOKEN, ITEM_ID, feedback.FeedbackUpdate(status="investigating", next_step=""))
    assert conn.calls[1][1][1] == ""


@pytest.mark.parametrize("status", ["new", "investigating", "closed"])
def test_non_ready_stages_allow_incomplete_briefs(monkeypatch, status):
    conn = install_connection(monkeypatch, [{"hypothesis": "", "primary_metric": "", "guardrail": "", "success_criteria": "", "next_step": ""}, {"status": status}])
    assert feedback.update_item(TOKEN, ITEM_ID, feedback.FeedbackUpdate(status=status))["status"] == status
    assert len(conn.calls) == 2


@pytest.mark.parametrize("value", ["=SUM(1,2)", "+command", "-command", "@command", "  =formula", "\t=tab-prefixed", "\r\n=multiline-prefixed"])
def test_csv_neutralizes_formula_prefixes_and_preserves_plain_feedback(monkeypatch, value):
    monkeypatch.setattr(feedback, "list_items", lambda token: [{"id": str(ITEM_ID), "title": value, "observation": "A plain quoted observation, with comma", "hypothesis": "=HYPERLINK(\"https://example.com\")", "status": "new"}])
    response = feedback.export_feedback(TOKEN)
    exported = list(csv.DictReader(io.StringIO(response.body.decode())))
    assert exported[0]["title"] == "'" + value
    assert exported[0]["hypothesis"].startswith("'=")
    assert exported[0]["observation"] == "A plain quoted observation, with comma"
    assert "text/csv" in response.headers["content-type"]
    assert "talentpulse-feedback.csv" in response.headers["content-disposition"]


def test_csv_export_uses_only_authenticated_workspace_items(monkeypatch):
    conn = install_connection(monkeypatch, [[{"id": str(ITEM_ID), "title": "Owned observation", "status": "new"}]])
    exported = list(csv.DictReader(io.StringIO(feedback.export_feedback(TOKEN).body.decode())))
    assert exported[0]["id"] == str(ITEM_ID)
    assert conn.calls[0][1] == (IDENTITY, feedback.WORKSPACE_LIMIT)


@pytest.mark.parametrize("change", [{"status": "inconclusive"}, {"status": "closed", "next_step": "x" * 501}, {"status": "closed", "title": "unexpected edit"}])
def test_feedback_update_rejects_unsupported_status_unbounded_action_and_extra_fields(change):
    with pytest.raises(ValidationError):
        feedback.FeedbackUpdate(**change)
