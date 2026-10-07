from __future__ import annotations

from .db import read_transaction, row, rows
from .filters import Filters
from .metrics import meta, percentage

TRACKING = (
    ("search_started", "User initiates a search", "Submitting a search query", "Search"),
    ("search_completed", "Search returns results", "Search API resolves successfully", "Search"),
    ("search_result_viewed", "Results enter the viewport", "Search results are rendered", "Search"),
    ("job_viewed", "User opens a job detail", "Job detail page is visible", "Discovery"),
    ("recommendation_viewed", "AI-ranked result is shown", "AI result card enters the viewport", "AI Search"),
    ("recommendation_clicked", "User opens an AI-ranked job", "AI result card click", "AI Search"),
    ("apply_clicked", "User intends to apply", "Apply CTA click", "Applications"),
    ("application_started", "Application form begins", "First application step loads", "Applications"),
    ("cv_uploaded", "User adds their CV", "Upload completes successfully", "Applications"),
    ("application_step_completed", "Application step validates", "Step completion is confirmed", "Applications"),
    ("application_submitted", "Application is accepted", "Server confirms application submission", "Applications"),
    ("application_error", "Application flow fails", "Application API returns a handled error", "Applications"),
)
COMMON = ["event_name", "occurred_at", "user_id", "session_id", "market", "device_type", "traffic_source", "page", "experiment_variant"]


def tracking(filters: Filters) -> dict:
    where, params = filters.sql()
    counts = rows(f"SELECT e.event_name, COUNT(*) AS volume FROM talentpulse.fact_events e JOIN talentpulse.fact_sessions s USING(session_id) WHERE {where} GROUP BY e.event_name", params)
    volumes = {item["event_name"]: item["volume"] for item in counts}
    return {"meta": meta(filters), "synthetic": True, "common_properties": COMMON, "events": [{"name": name, "description": description, "trigger": trigger, "required_properties": COMMON + (["job_id"] if name not in ("search_started", "search_completed", "search_result_viewed") else []) + (["error_code"] if name == "application_error" else []), "owner": owner, "status": "tracked" if volumes.get(name) else "no_events_in_window", "volume": volumes.get(name, 0)} for name, description, trigger, owner in TRACKING]}


@read_transaction
def quality(filters: Filters) -> dict:
    where, params = filters.sql()
    event_summary = row(f"""
        SELECT COUNT(*) AS events,
          COUNT(*) FILTER(WHERE e.event_name IS NULL OR e.session_id IS NULL OR e.user_id IS NULL OR e.occurred_at IS NULL OR e.market IS NULL OR e.market='' OR e.device_type IS NULL OR e.device_type='' OR e.traffic_source IS NULL OR e.traffic_source='' OR e.page IS NULL OR e.page='' OR e.experiment_variant IS NULL OR e.experiment_variant='' OR (e.job_id IS NULL AND e.event_name NOT IN ('search_started','search_completed','search_result_viewed'))) AS missing_required,
          COUNT(*) FILTER(WHERE e.event_name='application_error' AND (e.error_code IS NULL OR e.error_code='')) AS errors_without_code,
          COUNT(*) FILTER(WHERE e.event_name='application_submitted') AS submitted_events,
          COUNT(*) FILTER(WHERE e.occurred_at < s.occurred_at) AS early_events,
          COUNT(*) - COUNT(DISTINCT (e.session_id,e.event_seq)) AS duplicate_events,
          MIN(e.date) AS earliest_date, MAX(e.date) AS latest_date
        FROM talentpulse.fact_events e JOIN talentpulse.fact_sessions s USING(session_id) WHERE {where}
        """, params)
    session_summary = row(f"""
        SELECT COUNT(*) AS sessions, COUNT(*) FILTER(WHERE application_submitted) AS submitted_sessions,
          COUNT(*) FILTER(WHERE (job_viewed AND NOT search_completed) OR (apply_clicked AND NOT job_viewed) OR (application_started AND NOT apply_clicked) OR (cv_uploaded AND NOT application_started) OR (application_submitted AND NOT cv_uploaded)) AS invalid_funnel,
          COUNT(*) FILTER(WHERE load_time_ms < 0 OR model_cost_usd < 0) AS invalid_measurements
        FROM talentpulse.fact_sessions s WHERE {where}
        """, params)
    daily = rows(f"""SELECT e.date,COUNT(*) AS events,COUNT(DISTINCT e.session_id) AS sessions,
        COUNT(*) FILTER(WHERE e.market='' OR e.device_type='' OR e.traffic_source='' OR e.page='' OR e.experiment_variant='' OR (e.job_id IS NULL AND e.event_name NOT IN ('search_started','search_completed','search_result_viewed'))) AS missing_required,
        0::integer AS orphan_events
        FROM talentpulse.fact_events e JOIN talentpulse.fact_sessions s USING(session_id) WHERE {where}
        GROUP BY e.date ORDER BY e.date""", params)
    definitions = [
        ("required_properties", "Required event properties", event_summary["missing_required"], "Missing required identifiers or empty market, page, or variant values."),
        ("duplicates", "Duplicate event sequence", event_summary["duplicate_events"], "Repeated session_id + event_seq pairs. A database uniqueness constraint also prevents duplicates."),
        ("ordered_funnel", "Ordered funnel integrity", session_summary["invalid_funnel"], "Later funnel steps require earlier steps in the same search session."),
        ("event_chronology", "Session chronology", event_summary["early_events"], "Events cannot occur before their session start."),
        ("submission_reconciliation", "Submission reconciliation", abs(event_summary["submitted_events"] - session_summary["submitted_sessions"]), "Application-submitted event count matches completed session outcomes."),
        ("error_codes", "Error-code completeness", event_summary["errors_without_code"], "Application errors must include a diagnostic code."),
        ("valid_measurements", "Valid latency and cost", session_summary["invalid_measurements"], "Latency and cost must be non-negative."),
    ]
    checks = [{"key": key, "label": label, "status": "pass" if observed == 0 else "fail", "observed": observed, "threshold": 0, "unit": "records", "detail": detail} for key, label, observed, detail in definitions]
    if not event_summary["events"]:
        checks.append({"key": "coverage", "label": "Telemetry coverage", "status": "fail", "observed": 0, "threshold": 1, "unit": "events", "detail": "No events exist for this selection. Integrity cannot be established on an empty dataset."})
    return {"meta": meta(filters), "score": round(100 * sum(check["status"] == "pass" for check in checks) / len(checks), 1) if event_summary["events"] else 0, "status": "verified" if event_summary["events"] else "no_evidence", "checks": checks, "daily": daily, "event_volume": event_summary["events"], "session_volume": session_summary["sessions"], "coverage": {"earliest_date": event_summary["earliest_date"], "latest_date": event_summary["latest_date"]}, "note": "Checks cover the selected historical synthetic window. Referential integrity is enforced by PostgreSQL foreign keys; this is a reproducible lab, not a live production feed."}
