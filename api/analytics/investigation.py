from __future__ import annotations

import json
import re

from .experiment_api import experiment
from .db import read_transaction
from .filters import Filters
from .metrics import aggregate, daily, funnel, segmented
from .providers import ProviderFailure, complete, configured, model_id


@read_transaction
def evidence_context(question: str, filters: Filters) -> dict:
    text = question.lower()
    window = f"{filters.start_date} to {filters.end_date}"
    limits = ["All behavioral evidence is synthetic, stored in Neon, and is not StepStone production data.", "Recommendations are hypotheses; observational differences do not establish causality."]
    if any(term in text for term in ("experiment", "model", "gpt", "ollama", "ranking", "a/b", "ab test")) or ("ai search" in text and "manual" in text):
        result = experiment(filters)
        data = [{"variant": arm["label"], "users": arm["exposed_users"], "conversion_rate": arm["conversion_rate"], "latency_ms": arm["latency_ms"], "cost_usd": arm["cost_usd"]} for arm in result["arms"]]
        evidence = [{"label": item["variant"] + " · exposed users", "value": item["users"], "unit": "users"} for item in data] + [{"label": item["variant"] + " · user conversion", "value": item["conversion_rate"], "unit": "percent"} for item in data]
        comparisons = result["comparisons"]
        answer = "For the predeclared 21 Sep–4 Oct user-randomized experiment, " + "; ".join(f"{item['variant']} converts at {item['conversion_rate']:.2f}% among {item['users']:,} exposed users" if item["conversion_rate"] is not None else f"{item['variant']} has no exposed users; conversion is unavailable" for item in data) + ". "
        answer += " ".join(f"{item['variant']} has {item['absolute_lift_pp']:+.2f} pp lift versus control (Holm-adjusted p={item['adjusted_p_value']:.4g}; {item['decision']})." if item["adjusted_p_value"] is not None else f"{item['variant']} has insufficient sample for statistical inference." for item in comparisons)
        answer += " Balance uplift against latency and model cost; the synthetic outcomes do not measure actual model quality."
        chart = {"type": "bar", "title": "Experiment · user conversion (%)", "x_key": "variant", "y_key": "conversion_rate", "data": data}
        limits.append(result["filter_note"])
        context = {"arms": result["arms"], "comparisons": comparisons, "srm": result["srm"], "filter_note": result["filter_note"]}
    elif any(term in text for term in ("funnel", "drop", "journey", "step")):
        result = funnel(filters)
        data = [{"step": item["label"], "sessions": item["count"], "step_conversion_rate": item["step_conversion_rate"]} for item in result["steps"]]
        evidence = [{"label": item["step"], "value": item["sessions"], "unit": "sessions"} for item in data]
        biggest = result["biggest_drop"]
        answer = f"From {window}, {result['steps'][0]['count']:,} sessions started a search and {result['steps'][-1]['count']:,} submitted an application ({result['overall_conversion_rate']:.2f}% of initiated searches). The largest proportional drop is {biggest['from']} → {biggest['to']}: {biggest['count']:,} sessions, or {biggest['rate']:.2f}%. Compare devices and returning versus new users at that step, then test one friction-reduction hypothesis."
        chart = {"type": "bar", "title": "Search-to-application funnel", "x_key": "step", "y_key": "sessions", "data": data}
        context = result
    elif any(term in text for term in ("device", "mobile", "desktop", "tablet", "market", "country", "germany", "austria", "belgium", "netherlands", "segment", "latency", "slow")) or re.search(r"\buk\b|united kingdom", text):
        dimension = "market" if any(term in text for term in ("market", "country", "germany", "austria", "belgium", "netherlands")) or re.search(r"\buk\b|united kingdom", text) else "device_type"
        metric = "avg_load_time_ms" if any(term in text for term in ("latency", "slow", "speed", "response")) else "completion_rate" if any(term in text for term in ("cv", "completion", "mobile", "upload")) else "conversion_rate"
        result = segmented(filters, dimension, metric)
        data = [{"segment": item["name"], metric: item[metric], "sessions": item["sessions"], "application_starts": item["application_starts"], "applications": item["applications"]} for item in result["rows"]]
        unit = "ms" if metric == "avg_load_time_ms" else "percent"
        evidence = [{"label": item["segment"], "value": item[metric], "unit": unit} for item in data]
        definition = "completed applications / application starts" if metric == "completion_rate" else "completed applications / all searches" if metric == "conversion_rate" else "mean recorded search response time"
        answer = f"For {window}, comparing {dimension.replace('_', ' ')} on {metric.replace('_', ' ')} ({definition}): " + "; ".join(f"{item['segment']} {item[metric]:.2f}{' ms' if unit == 'ms' else '%'} across {item['sessions']:,} sessions" for item in data) + ". Investigate traffic mix and the release timeline before treating a segment difference as an effect."
        chart = {"type": "bar", "title": f"{dimension.replace('_', ' ').title()} · {metric.replace('_', ' ')}", "x_key": "segment", "y_key": metric, "data": data}
        context = {**result, "reported_metric": metric, "definition": definition}
    else:
        current = aggregate(filters)
        data = daily(filters)
        evidence = [{"label": "Search sessions", "value": current["sessions"], "unit": "sessions"}, {"label": "Applications submitted", "value": current["applications"], "unit": "applications"}, {"label": "Search conversion", "value": current["conversion_rate"], "unit": "percent"}, {"label": "Application completion", "value": current["completion_rate"], "unit": "percent"}]
        answer = f"From {window}, the selected population generated {current['sessions']:,} search sessions and {current['applications']:,} submitted applications. Search-to-application conversion is {current['conversion_rate']:.2f}% (submissions / searches); application completion is {current['completion_rate']:.2f}% (submissions / starts). Mean search latency is {current['latency_ms']:.0f} ms. Segment the funnel by device and examine the randomized experiment before recommending a rollout."
        completion_requested = any(term in text for term in ("completion", "complete", "cv upload"))
        chart = {"type": "line", "title": "Daily application completion (%)" if completion_requested else "Daily search-to-application conversion (%)", "x_key": "date", "y_key": "completion_rate" if completion_requested else "conversion_rate", "data": data}
        context = {"aggregate": current, "daily": data, "window": filters.window()}
    return {"answer": answer, "evidence": evidence, "chart": chart, "context": context, "limitations": limits}


async def investigate(question: str, visualize: bool, provider: str, filters: Filters, selected: dict, allow_inference: bool = True, model: str | None = None, api_key: str | None = None) -> dict:
    answer = selected["answer"]
    interpretation = None
    mode = "evidence"
    limitations = list(selected["limitations"])
    synthetic = selected.get("synthetic", True)
    credentials_ready = bool(api_key or configured(provider))
    if credentials_ready and allow_inference:
        try:
            response = await complete(provider, "You are a product analyst working on TalentPulse. " + ("This evidence is explicitly synthetic." if synthetic else "This evidence comes from a private uploaded dataset; provenance and randomization are user-provided and unverified. Do not label it synthetic or claim StepStone production provenance.") + " Give only a brief qualitative hypothesis and a suggested next experiment, using the supplied aggregate evidence. The application already displays all quantitative findings: do not include any numbers, percentages, dates, p-values, latency values or costs in your response. Do not make causal claims from observational trends. Distinguish user-randomized experiments from session-level trends. Say when evidence does not answer the question. Never claim actual StepStone impact or actual model quality. Do not create SQL, charts, or numeric claims. Label hypotheses.", json.dumps({"question": question, "filters": filters.model_dump(mode="json"), "aggregate_evidence": selected["context"]}, ensure_ascii=False), max_tokens=400, model=model, api_key=api_key)
            proposed = response["content"][:2500]
            # Provider text cannot replace or invent the numeric finding. Remove
            # known model names before rejecting any remaining numeral.
            numeric_check = re.sub(r"GPT[- ]?4o|GPT[- ]?OSS\s*120B|gpt-oss:120b", "MODEL", proposed, flags=re.IGNORECASE)
            if not re.search(r"\d", numeric_check):
                interpretation = proposed
                mode = "provider"
            else:
                limitations.append("The provider interpretation included numeric claims and was discarded. All displayed numbers come directly from backend queries.")
        except ProviderFailure as exc:
            limitations.append(str(exc) + " The response below uses deterministic database evidence.")
    elif not credentials_ready:
        limitations.append(f"{provider} is not configured; this is a deterministic evidence summary, not a model-generated answer.")
    structure = {"finding": answer, "evidence": "Metrics and chart values are deterministic backend calculations from " + ("selected synthetic telemetry." if synthetic else "authorized uploaded rows; no missing outcomes are imputed."), "affected_segments": "Selected filters: " + ", ".join(f"{key}={value}" for key, value in filters.model_dump(mode="json").items() if value is not None), "hypothesis": interpretation or "Funnel friction and traffic mix may explain observed differences; validate with segmented evidence before changing the product.", "confidence": "Descriptive " + ("synthetic evidence. Experiment decisions use a fixed user-level window and multiplicity adjustment." if synthetic else "uploaded evidence. Causal validity and randomization require explicit user-provided design information." ) + " Observational trends have no causal attribution.", "next_step": "Inspect the available outcome denominators and role/device mix before deciding whether a conversion question can be answered.", "suggested_experiment": "Pre-register a user-randomized relevance or application-journey test, with a declared outcome denominator and measured latency/error/cost guardrails."}
    answer = "\n\n".join(f"{key.replace('_', ' ').title()}: {value}" for key, value in structure.items())
    return {"answer": answer, "investigation": structure, "interpretation": interpretation, "mode": mode, "provider": provider if mode == "provider" else None, "model": (model or model_id(provider)) if mode == "provider" else None, "synthetic": synthetic, "evidence": selected["evidence"], "chart": selected["chart"] if visualize else None, "suggested_questions": ["Visualize the application funnel and largest drop", "Compare mobile and desktop application completion", "Compare GPT-4o and Ollama experiment conversion with guardrails"], "limitations": limitations}
