"""Translate user-grain statistical output into the dashboard contract."""
from __future__ import annotations

import os

from analytics.experiments import analyze_experiment

from .db import rows
from .filters import Filters

LABELS = {"control": ("Manual SQL search", "PostgreSQL", None), "gpt4o": ("GPT-4o recommendation", "OpenRouter", "openai/gpt-4o"), "ollama": ("GPT-OSS 120B recommendation", "Ollama Cloud", "gpt-oss:120b")}


def experiment(filters: Filters) -> dict:
    clauses = ["o.experiment_id = %s"]
    params: list = ["ai-ranking-v1"]
    applied = {}
    for name in ("market", "device_type", "user_type", "experience_level"):
        value = getattr(filters, name)
        if value:
            clauses.append(f"u.{name} = %s")
            params.append(value)
            applied[name] = value
    data = rows("""
        SELECT o.variant, COUNT(*)::integer AS assigned_users,
          COUNT(*) FILTER(WHERE o.exposed)::integer AS exposed_users,
          COUNT(*) FILTER(WHERE o.converted)::integer AS converted_users,
          COUNT(*) FILTER(WHERE o.job_engaged)::integer AS engaged_users,
          COALESCE(SUM(o.sessions),0)::integer AS sessions,
          COALESCE(SUM(o.errors),0)::integer AS errors,
          COALESCE(SUM(o.avg_load_time_ms * o.sessions)/NULLIF(SUM(o.sessions),0),0) AS avg_load_time_ms,
          COALESCE(SUM(o.model_cost_usd),0) AS model_cost_usd
        FROM talentpulse.fact_experiment_outcomes o
        JOIN talentpulse.dim_users u USING(user_id)
        WHERE """ + " AND ".join(clauses) + " GROUP BY o.variant ORDER BY o.variant", params)
    existing = {item["variant"]: item for item in data}
    data = [existing.get(variant, {"variant": variant, "assigned_users": 0, "exposed_users": 0, "converted_users": 0, "engaged_users": 0, "sessions": 0, "errors": 0, "avg_load_time_ms": 0, "model_cost_usd": 0}) for variant in LABELS]
    result = analyze_experiment(data)
    comparison_map = {item["variant"]: item for item in result["comparisons"]}
    arms = []
    for arm in result["variants"]:
        variant = arm["variant"]
        label, provider, model = LABELS[variant]
        comparison = comparison_map.get(variant, {})
        interval = comparison.get("simultaneous_confidence_interval_pp")
        arms.append({"arm": variant, "variant": variant, "label": label, "provider": provider, "model": model, "assigned_users": arm["assigned_users"], "exposed_users": arm["exposed_users"], "users": arm["exposed_users"], "applications": arm["converted_users"], "sessions": arm["sessions"], "conversion_rate": arm["conversion_rate"] * 100 if arm["conversion_rate"] is not None else None, "exposure_rate": arm["exposure_rate"] * 100 if arm["exposure_rate"] is not None else None, "lift_pct": comparison.get("relative_lift") * 100 if comparison.get("relative_lift") is not None else 0 if variant == "control" else None, "absolute_lift_pp": comparison.get("absolute_lift_pp", 0 if variant == "control" else None), "ci_low": interval[0] if interval else None, "ci_high": interval[1] if interval else None, "p_value": comparison.get("adjusted_p_value"), "significant": comparison.get("significant", False), "latency_ms": arm["avg_load_time_ms"], "cost_usd": arm["model_cost_usd"], "decision": comparison.get("decision", "Baseline")})
    result["arms"] = arms
    result["allocation"] = [{"name": arm["label"], "variant": arm["arm"], "users": arm["assigned_users"]} for arm in arms]
    result["filters_applied"] = applied
    if applied:
        result["limitations"].append("Filtered subgroup comparisons are exploratory. Holm adjusts the two treatments versus control within this view, not all possible subgroup selections; pre-register subgroup hypotheses before using them for a rollout decision.")
    result["ignored_filters"] = [name for name in ("job_category", "traffic_source", "variant") if getattr(filters, name)]
    result["filter_note"] = "The experiment always uses its predeclared 21 Sep–4 Oct window and user attributes. Session-dependent category/source filters are excluded to avoid conditioning on post-assignment behavior. Dashboard dates do not truncate experiment outcomes."
    # Keep statistical fractions explicitly labelled; convenience arms use percentages.
    result["rate_units"] = {"arms": "percent", "variants": "fraction", "comparisons": "fraction except *_pp", "guardrails": "fraction except *_ms and *_usd"}
    return result
