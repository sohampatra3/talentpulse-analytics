"""Private qualitative evidence; no fabricated priority scores or causal claims."""
from __future__ import annotations

import csv
import io
from datetime import date
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from psycopg.types.json import Jsonb

from .db import connection, serializable
from .workspaces import require_workspace_token, workspace_identity

router = APIRouter(prefix="/api/workspace/feedback", tags=["Private feedback and decisions"])
WORKSPACE_LIMIT = 250
GLOBAL_LIMIT = 2000
Status = Literal["new", "investigating", "experiment_ready", "closed"]


class FeedbackContext(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    dataset_id: UUID | None = None
    dataset_name: str = Field(default="Synthetic product telemetry", max_length=200)
    start_date: str = Field(default="", pattern=r"^(|\d{4}-\d{2}-\d{2})$")
    end_date: str = Field(default="", pattern=r"^(|\d{4}-\d{2}-\d{2})$")
    market: str = Field(default="all", max_length=80)
    device: str = Field(default="all", max_length=80)
    user_type: str = Field(default="all", max_length=80)

    @field_validator("start_date", "end_date")
    @classmethod
    def calendar_date(cls, value):
        if value:
            date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def date_window(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("Start date must precede or match the end date.")
        return self


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=3, max_length=160)
    observation: str = Field(min_length=10, max_length=2000)
    hypothesis: str = Field(default="", max_length=1000)
    primary_metric: str = Field(default="", max_length=200)
    guardrail: str = Field(default="", max_length=300)
    success_criteria: str = Field(default="", max_length=500)
    next_step: str = Field(default="", max_length=500)
    area: Literal["search", "application", "tracking", "ai", "reporting", "other"] = "search"
    source: Literal["analyst_observation", "candidate_feedback", "usability_test", "stakeholder_request"] = "analyst_observation"
    priority: Literal["low", "medium", "high"] = "medium"
    context: FeedbackContext = Field(default_factory=FeedbackContext)


class FeedbackUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Status
    next_step: str | None = Field(default=None, max_length=500)


def list_items(token: str) -> list[dict]:
    with connection() as conn:
        identity = workspace_identity(token)
        return serializable(conn.execute("SELECT id,title,observation,hypothesis,primary_metric,guardrail,success_criteria,next_step,area,source,priority,status,context,created_at,updated_at FROM talentpulse.feedback_items WHERE workspace_hash=%s ORDER BY created_at DESC LIMIT %s", (identity, WORKSPACE_LIMIT)).fetchall())


def create_item(token: str, body: FeedbackCreate) -> dict:
    with connection(readonly=False) as conn:
        identity = workspace_identity(token)
        if body.context.dataset_id:
            owned = conn.execute("SELECT dataset_id FROM talentpulse.upload_datasets WHERE workspace_hash=%s AND dataset_id=%s", (identity, str(body.context.dataset_id))).fetchone()
            if not owned:
                raise HTTPException(404, "This uploaded dataset is unavailable in your workspace.")
        # Serialize quota checks and inserts across instances, including the public demo.
        conn.execute("SELECT pg_advisory_xact_lock(187346, 4)")
        counts = conn.execute("SELECT COUNT(*) AS total,COUNT(*) FILTER (WHERE workspace_hash=%s) AS workspace FROM talentpulse.feedback_items", (identity,)).fetchone()
        if counts["workspace"] >= WORKSPACE_LIMIT or counts["total"] >= GLOBAL_LIMIT:
            raise HTTPException(429, "Feedback storage is full. Export and remove an item before adding more.")
        values = body.model_dump(exclude={"context"})
        result = conn.execute("INSERT INTO talentpulse.feedback_items(id,workspace_hash,title,observation,hypothesis,primary_metric,guardrail,success_criteria,next_step,area,source,priority,context) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id,title,observation,hypothesis,primary_metric,guardrail,success_criteria,next_step,area,source,priority,status,context,created_at,updated_at", (str(uuid4()), identity, values["title"], values["observation"], values["hypothesis"], values["primary_metric"], values["guardrail"], values["success_criteria"], values["next_step"], values["area"], values["source"], values["priority"], Jsonb(body.context.model_dump(mode="json")))).fetchone()
        return serializable(result)


def update_item(token: str, item_id: UUID, body: FeedbackUpdate) -> dict:
    with connection(readonly=False) as conn:
        identity = workspace_identity(token)
        existing = conn.execute("SELECT hypothesis,primary_metric,guardrail,success_criteria,next_step FROM talentpulse.feedback_items WHERE id=%s AND workspace_hash=%s FOR UPDATE", (str(item_id), identity)).fetchone()
        if not existing:
            raise HTTPException(404, "Feedback item not found in this workspace.")
        if body.status == "experiment_ready" and not all(existing.get(key) for key in ("hypothesis", "primary_metric", "guardrail", "success_criteria")):
            raise HTTPException(422, "An experiment-ready item needs a hypothesis, primary metric, guardrail and success criterion. Add a complete test brief as a new item.")
        next_step = existing["next_step"] if body.next_step is None else body.next_step
        result = conn.execute("UPDATE talentpulse.feedback_items SET status=%s,next_step=%s,updated_at=now() WHERE id=%s AND workspace_hash=%s RETURNING id,status,next_step,updated_at", (body.status, next_step, str(item_id), identity)).fetchone()
        return serializable(result)


@router.get("")
def get_feedback(token: str = Depends(require_workspace_token)):
    return {"items": list_items(token), "limit": WORKSPACE_LIMIT, "source": "Private workspace observations"}


@router.post("", status_code=201)
def post_feedback(body: FeedbackCreate, token: str = Depends(require_workspace_token)):
    return create_item(token, body)


@router.patch("/{item_id}")
def patch_feedback(item_id: UUID, body: FeedbackUpdate, token: str = Depends(require_workspace_token)):
    return update_item(token, item_id, body)


@router.delete("/{item_id}")
def delete_feedback(item_id: UUID, token: str = Depends(require_workspace_token)):
    with connection(readonly=False) as conn:
        identity = workspace_identity(token)
        result = conn.execute("DELETE FROM talentpulse.feedback_items WHERE id=%s AND workspace_hash=%s RETURNING id", (str(item_id), identity)).fetchone()
        if not result:
            raise HTTPException(404, "Feedback item not found in this workspace.")
    return {"deleted": True}


@router.get("/export/csv")
def export_feedback(token: str = Depends(require_workspace_token)):
    context_fields = ["dataset_name", "start_date", "end_date", "market", "device", "user_type"]
    fields = ["id", "title", "observation", "hypothesis", "primary_metric", "guardrail", "success_criteria", "next_step", "area", "source", "priority", "status", "created_at", "updated_at", *context_fields]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for item in list_items(token):
        item = {**item, **{key: item.get("context", {}).get(key, "") for key in context_fields}}
        # Prevent user-authored feedback becoming executable spreadsheet formulas.
        writer.writerow({key: "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value for key, value in item.items()})
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="talentpulse-feedback.csv"'})
