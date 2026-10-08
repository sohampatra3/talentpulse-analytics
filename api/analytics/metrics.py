from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from .db import read_transaction, row, rows
from .filters import DIMENSIONS, Filters

METRICS = ("conversion_rate", "completion_rate", "job_view_rate", "error_rate", "avg_load_time_ms", "sessions")
STEPS = (
    ("search_performed", "Search started"),
    ("search_completed", "Search completed"),
    ("job_viewed", "Job viewed"),
    ("apply_clicked", "Apply clicked"),
    ("application_started", "Application started"),
    ("cv_uploaded", "CV uploaded"),
    ("application_submitted", "Application submitted"),
)
AGGREGATE_SQL = """
    COUNT(*)::bigint AS sessions,
    COUNT(*) FILTER (WHERE application_submitted)::bigint AS applications,
    COUNT(*) FILTER (WHERE job_viewed)::bigint AS job_views,
    COUNT(*) FILTER (WHERE application_started)::bigint AS application_starts,
    COUNT(*) FILTER (WHERE search_completed)::bigint AS completed_searches,
    COUNT(*) FILTER (WHERE application_error)::bigint AS errors,
    COALESCE(AVG(load_time_ms), 0) AS avg_load_time_ms,
    COALESCE(SUM(model_cost_usd), 0) AS model_cost_usd
"""


def percentage(numerator, denominator):
    return round(100 * numerator / denominator, 3) if denominator else 0.0


def complete_aggregate(item: dict) -> dict:
    item = dict(item)
    count = item.get("sessions", 0)
    item.update({
        "completion_rate": percentage(item.get("applications", 0), item.get("application_starts", 0)),
        "conversion_rate": percentage(item.get("applications", 0), count),
        "job_view_rate": percentage(item.get("job_views", 0), count),
        "error_rate": percentage(item.get("errors", 0), count),
        "latency_ms": round(float(item.get("avg_load_time_ms", 0)), 1),
        "searches": count,
    })
    item["avg_load_time_ms"] = item["latency_ms"]
    return item


def aggregate(filters: Filters) -> dict:
    where, params = filters.sql()
    return complete_aggregate(row(f"SELECT {AGGREGATE_SQL} FROM talentpulse.fact_sessions s WHERE {where}", params))


def meta(filters: Filters) -> dict:
    return {"synthetic": True, "source": "Neon · synthetic product telemetry", **filters.window(), "generated_at": datetime.now(timezone.utc).isoformat()}


def daily(filters: Filters) -> list[dict]:
    where, params = filters.sql()
    data = rows(f"SELECT s.date, {AGGREGATE_SQL} FROM talentpulse.fact_sessions s WHERE {where} GROUP BY s.date ORDER BY s.date", params)
    return [complete_aggregate(item) for item in data]


def segmented(filters: Filters, dimension: str, metric: str = "completion_rate") -> dict:
    if dimension not in DIMENSIONS or metric not in METRICS:
        raise ValueError("Choose an allowed dimension and metric")
    where, params = filters.sql()
    data = rows(f"SELECT s.{dimension} AS name, {AGGREGATE_SQL} FROM talentpulse.fact_sessions s WHERE {where} GROUP BY s.{dimension} ORDER BY sessions DESC", params)
    total = sum(item["sessions"] for item in data)
    result = []
    for item in data:
        item = complete_aggregate(item)
        item.update({"label": item["name"], "share": percentage(item["sessions"], total), "metric_value": item[metric], dimension: item["name"], "application_rate": item["conversion_rate"]})
        result.append(item)
    return {"meta": meta(filters), "dimension": dimension, "metric": metric, "rows": result, "dimensions": list(DIMENSIONS), "metrics": list(METRICS)}


@read_transaction
def overview(filters: Filters) -> dict:
    current = aggregate(filters)
    previous_filters = filters.previous()
    previous = aggregate(previous_filters)
    bounds = row("SELECT MIN(date) AS start_date,MAX(date) AS end_date FROM talentpulse.fact_sessions")
    previous_complete = bool(bounds.get("start_date") and bounds["start_date"] <= str(previous_filters.start_date) and bounds["end_date"] >= str(previous_filters.end_date))
    current_complete = bool(bounds.get("start_date") and bounds["start_date"] <= str(filters.start_date) and bounds["end_date"] >= str(filters.end_date))
    comparison_complete = previous_complete and current_complete
    where, params = filters.sql()
    if not any(getattr(filters, name) for name in ("user_type", "job_category", "experience_level")):
        # These dimensions are copied onto every synthetic event by the seed
        # ingestion contract. Counting their exact rows avoids a million-row join.
        event_where = ["e.date BETWEEN %s AND %s"]
        event_params = [filters.start_date, filters.end_date]
        for field, column in (("market", "market"), ("device_type", "device_type"), ("traffic_source", "traffic_source"), ("variant", "experiment_variant")):
            if getattr(filters, field):
                event_where.append(f"e.{column}=%s")
                event_params.append(getattr(filters, field))
        event_count = row("SELECT COUNT(*) AS n FROM talentpulse.fact_events e WHERE " + " AND ".join(event_where), event_params)["n"]
    else:
        event_count = row(f"SELECT COUNT(*) AS n FROM talentpulse.fact_events e JOIN talentpulse.fact_sessions s USING(session_id) WHERE {where}", params)["n"]
    definitions = (
        ("sessions", "Search sessions", "number", "Sessions that entered the job-search journey."),
        ("applications", "Completed applications", "number", "Applications submitted, attributed to the originating search session."),
        ("conversion_rate", "Search → application", "percent", "Completed applications divided by all search sessions."),
        ("completion_rate", "Application completion", "percent", "Completed applications divided by sessions that started an application."),
        ("avg_load_time_ms", "Mean search latency", "ms", "Average recorded result response time; this is not a percentile."),
        ("application_error_rate", "Application error rate", "percent", "Search sessions containing an application error divided by all sessions."),
    )
    current["application_error_rate"] = current["error_rate"]
    previous["application_error_rate"] = previous["error_rate"]
    kpis = []
    for key, label, unit, description in definitions:
        value, old = current[key], previous[key]
        delta = None if not comparison_complete or not previous["sessions"] else round(value - old, 3) if unit in ("percent", "ms") else round((value / old - 1) * 100, 2) if old else None
        kpis.append({"key": key, "label": label, "value": value, "unit": unit, "delta": delta, "previous_value": old if previous_complete else None, "description": description})
    devices = segmented(filters, "device_type")["rows"]
    markets = segmented(filters, "market")["rows"]
    insights = [{"title": "Synthetic portfolio data", "detail": "All telemetry is reproducible synthetic data. These patterns demonstrate analysis and do not describe StepStone's actual performance.", "severity": "info"}]
    if devices:
        strongest = max(devices, key=lambda item: item["conversion_rate"])
        weakest = min(devices, key=lambda item: item["conversion_rate"])
        insights.append({"title": "Device conversion gap", "detail": f"{strongest['name']} converts at {strongest['conversion_rate']:.2f}% versus {weakest['conversion_rate']:.2f}% for {weakest['name']}. Investigate funnel friction before attributing the gap to device.", "severity": "opportunity"})
    if comparison_complete and previous["sessions"]:
        change = current["conversion_rate"] - previous["conversion_rate"]
        insights.append({"title": "Comparable period", "detail": f"Search-to-application conversion changed {change:+.2f} percentage points against the previous {((filters.end_date - filters.start_date).days + 1)}-day period.", "severity": "positive" if change >= 0 else "attention"})
    dimension_where, dimension_params = filters.sql(include_dates=False)
    user_counts = row(f"SELECT COUNT(DISTINCT user_id) FILTER(WHERE date=%s) AS dau,COUNT(DISTINCT user_id) AS wau FROM talentpulse.fact_sessions s WHERE s.date BETWEEN %s AND %s AND {dimension_where}", (filters.end_date, filters.end_date - timedelta(days=6), filters.end_date, *dimension_params))
    product_metrics = {"dau": user_counts["dau"], "wau": user_counts["wau"], "searches": current["sessions"], "job_views": current["job_views"], "application_starts": current["application_starts"], "application_submits": current["applications"], "search_conversion_rate": current["conversion_rate"], "application_completion_rate": current["completion_rate"], "search_success_rate": percentage(current["completed_searches"], current["sessions"]), "definitions": {"dau": "Distinct active users on the selected end date", "wau": "Distinct active users in the seven days ending on the selected end date, independent of the start-date filter", "search_conversion_rate": "Applications submitted / all search sessions", "application_completion_rate": "Applications submitted / applications started", "search_success_rate": "Successful completed searches / all search sessions"}}
    return {"meta": {**meta(filters), "events": event_count, "sessions": current["sessions"], "previous_start_date": str(previous_filters.start_date), "previous_end_date": str(previous_filters.end_date), "comparison_available": comparison_complete and bool(previous["sessions"]), "comparison_note": "Equal-length, fully covered periods" if comparison_complete else "A selected or previous window extends beyond the dataset; comparisons are suppressed."}, "kpis": kpis, "product_metrics": product_metrics, "trend": daily(filters), "markets": markets, "devices": devices, "insights": insights}


def funnel(filters: Filters) -> dict:
    where, params = filters.sql()
    fields = ", ".join(f"COUNT(*) FILTER (WHERE {key}) AS {key}" for key, _ in STEPS)
    data = row(f"SELECT {fields} FROM talentpulse.fact_sessions s WHERE {where}", params)
    first = data[STEPS[0][0]]
    steps = []
    previous = first
    for key, label in STEPS:
        count = data[key]
        steps.append({"key": key, "label": label, "count": count, "conversion_rate": percentage(count, first), "step_conversion_rate": percentage(count, previous), "drop_off": previous - count, "drop_off_rate": percentage(previous - count, previous)})
        previous = count
    largest = max(steps[1:], key=lambda step: step["drop_off_rate"])
    index = next(i for i, item in enumerate(steps) if item["key"] == largest["key"])
    biggest = {"from": steps[index - 1]["label"], "to": largest["label"], "count": largest["drop_off"], "rate": largest["drop_off_rate"]}
    return {"meta": meta(filters), "steps": steps, "overall_conversion_rate": percentage(previous, first), "biggest_drop": biggest, "insights": [{"title": "Largest proportional drop", "detail": f"{biggest['from']} → {biggest['to']} loses {biggest['rate']:.2f}% of sessions reaching the previous step. Prioritize segmentation of this step.", "severity": "attention"}]}


def filter_options() -> dict:
    values = row("SELECT MIN(date) AS start_date, MAX(date) AS end_date, " + ", ".join(f"ARRAY_AGG(DISTINCT {name} ORDER BY {name}) AS {name}" for name in DIMENSIONS) + " FROM talentpulse.fact_sessions")
    return {"markets": values["market"], "devices": values["device_type"], "user_types": values["user_type"], "job_categories": values["job_category"], "traffic_sources": values["traffic_source"], "experience_levels": values["experience_level"], "variants": values["variant"], "date_range": {"start_date": values["start_date"], "end_date": values["end_date"]}, "synthetic": True}


@read_transaction
def releases(filters: Filters) -> dict:
    release_rows = rows("SELECT * FROM talentpulse.dim_releases ORDER BY release_date DESC")
    data_window = row("SELECT MIN(date) AS start_date, MAX(date) AS end_date FROM talentpulse.fact_sessions")
    result = []
    for release in release_rows:
        release_date = date.fromisoformat(release["release_date"])
        if not filters.start_date <= release_date <= filters.end_date:
            continue
        release_market = release["market"] if release["market"].lower() not in ("all", "global") else None
        release_device = release["platform"] if release["platform"].lower() not in ("all", "global", "web") else None
        if (release_market and filters.market and release_market != filters.market) or (release_device and filters.device_type and release_device != filters.device_type):
            continue
        release_filters = filters.model_copy(update={"market": release_market or filters.market, "device_type": release_device or filters.device_type})
        window_days = min(7, (release_date - date.fromisoformat(data_window["start_date"])).days, (date.fromisoformat(data_window["end_date"]) - release_date).days + 1)
        if window_days < 1:
            continue
        start = release_date - timedelta(days=window_days)
        end = release_date + timedelta(days=window_days - 1)
        before_filters = release_filters.model_copy(update={"start_date": start, "end_date": release_date - timedelta(days=1)})
        after_filters = release_filters.model_copy(update={"start_date": release_date, "end_date": end})
        before, after = aggregate(before_filters), aggregate(after_filters)
        adequate = bool(before.get("application_starts") and after.get("application_starts"))
        sessions_adequate = bool(before["sessions"] and after["sessions"])
        impact = round(after["completion_rate"] - before["completion_rate"], 3) if adequate else None
        error_change = round(after.get("error_rate", 0) - before.get("error_rate", 0), 3) if sessions_adequate else None
        result.append({"id": release["release_id"], "name": release["release_name"], "feature": release["feature"], "release_date": release["release_date"], "market": release["market"], "platform": release["platform"], "before": before, "after": after, "impact_pp": impact, "impact_metric": "application_completion_rate", "error_change_pp": error_change, "relative_lift_pct": round(100 * impact / before["completion_rate"], 2) if adequate and before["completion_rate"] else None, "latency_change_ms": round(after["latency_ms"] - before["latency_ms"], 1) if sessions_adequate else None, "before_window": before_filters.window(), "after_window": after_filters.window(), "window_days": window_days, "confidence": "Observational association" if adequate else "Insufficient baseline", "interpretation": f"Application completion (submissions / starts) changed {impact:+.2f} percentage points. Seasonality, traffic mix and experiment exposure can confound this before/after comparison." if adequate else "At least one period has no application starts. An application-completion impact cannot be estimated for this selection."})
    return {"meta": meta(filters), "releases": result, "disclaimer": "Before/after comparisons show association. They are not causal release attribution; use randomized experiments for a causal claim."}


@read_transaction
def job_role_drivers(filters: Filters, role: str | None = None) -> dict:
    where, params = filters.sql()
    options = rows(f"SELECT DISTINCT j.job_title FROM talentpulse.fact_sessions s JOIN talentpulse.dim_jobs j USING(job_id) WHERE {where} ORDER BY j.job_title", params)
    if role and role.lower() == "all":
        role = None
    if role:
        where += " AND j.job_title=%s"
        params = (*params, role)
    summary = row(f"SELECT {AGGREGATE_SQL},COUNT(DISTINCT s.user_id) AS unique_users FROM talentpulse.fact_sessions s JOIN talentpulse.dim_jobs j USING(job_id) WHERE {where}", params)
    arm_rows = rows(f"SELECT s.variant AS arm,{AGGREGATE_SQL} FROM talentpulse.fact_sessions s JOIN talentpulse.dim_jobs j USING(job_id) WHERE {where} GROUP BY s.variant ORDER BY s.variant", params)
    labels = {"control": "Manual SQL search", "gpt4o": "GPT-4o recommendation", "ollama": "GPT-OSS 120B recommendation"}
    arms = []
    for item in arm_rows:
        item = complete_aggregate(item)
        item.update(label=labels.get(item["arm"], item["arm"]), users=None, exposed_users=None, significant=False, p_value=None, lift_pct=None, ci_low=None, ci_high=None, decision="Descriptive role association", cost_usd=item["model_cost_usd"])
        arms.append(item)
    drivers = []
    for dimension in ("device_type", "market", "traffic_source", "experience_level", "job_category"):
        data = rows(f"SELECT s.{dimension} AS name,{AGGREGATE_SQL} FROM talentpulse.fact_sessions s JOIN talentpulse.dim_jobs j USING(job_id) WHERE {where} GROUP BY s.{dimension} ORDER BY sessions DESC", params)
        groups = [{**complete_aggregate(item), "label": item["name"], "metric_value": percentage(item["applications"], item["sessions"])} for item in data]
        drivers.append({"factor": dimension, "groups": groups, "interpretation": "Observed session-level association. Role choice and cohort mix can occur after assignment; this comparison does not identify a causal driver."})
    return {"meta": meta(filters), "role": role, "role_options": [item["job_title"] for item in options], "support": {"row_count": summary["sessions"], "session_count": summary["sessions"], "unique_users": summary["unique_users"], "grain": "sessions", "randomized_status": "role_selection_not_randomized", "denominator": "observed search sessions"}, "arms": arms, "drivers": drivers, "limitations": ["Role-specific conversion is descriptive and uses sessions, unlike the main experiment's fixed user-level outcome.", "Selection into a job role can be affected by treatment. No role-specific winner, significance, or causal explanation is inferred.", "All base telemetry is synthetic; it is not actual StepStone performance."], "suggested_experiment": "Pre-register role-relevance hypotheses at user assignment, with a declared conversion denominator and latency/error/cost guardrails."}
