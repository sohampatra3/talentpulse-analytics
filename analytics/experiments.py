"""User-randomized experiment inference; synthetic evidence is not a model benchmark."""

from __future__ import annotations

import math
from typing import Any, Iterable

from scipy.stats import chi2, norm


def _validate_count(successes: int, total: int) -> None:
    if not isinstance(total, int) or not isinstance(successes, int):
        raise ValueError("Counts must be integers")
    if total < 0 or successes < 0 or successes > total:
        raise ValueError("Successes must be between zero and total")


def compare_proportions(
    control_successes: int,
    control_total: int,
    variant_successes: int,
    variant_total: int,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Two-sided pooled z test and unpooled difference CI, all at user grain.

    Raw rate/lift values are fractions. `*_pp` values are percentage points.
    Empty groups return an explicitly inconclusive result rather than zero.
    """
    _validate_count(control_successes, control_total)
    _validate_count(variant_successes, variant_total)
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between zero and one")
    if not control_total or not variant_total:
        return {
            "control_rate": None, "variant_rate": None,
            "absolute_lift": None, "absolute_lift_pp": None,
            "relative_lift": None, "confidence_interval": None,
            "confidence_interval_pp": None, "p_value": None,
            "significant": False, "status": "insufficient_data",
            "method": "two-sided pooled proportions z test",
        }
    control_rate = control_successes / control_total
    variant_rate = variant_successes / variant_total
    difference = variant_rate - control_rate
    pooled = (control_successes + variant_successes) / (control_total + variant_total)
    pooled_se = math.sqrt(pooled * (1 - pooled) * (1 / control_total + 1 / variant_total))
    p_value = float(2 * norm.sf(abs(difference / pooled_se))) if pooled_se else 1.0
    difference_se = math.sqrt(
        control_rate * (1 - control_rate) / control_total
        + variant_rate * (1 - variant_rate) / variant_total
    )
    critical = float(norm.ppf(1 - alpha / 2))
    ci = [max(-1.0, difference - critical * difference_se),
          min(1.0, difference + critical * difference_se)]
    observed_cells = [control_successes, control_total - control_successes,
                      variant_successes, variant_total - variant_successes]
    adequate = min(observed_cells) >= 5
    return {
        "control_rate": control_rate,
        "variant_rate": variant_rate,
        "absolute_lift": difference,
        "absolute_lift_pp": difference * 100,
        "relative_lift": difference / control_rate if control_rate else None,
        "confidence_interval": ci if adequate else None,
        "confidence_interval_pp": [value * 100 for value in ci] if adequate else None,
        "p_value": p_value if adequate else None,
        "significant": p_value < alpha and adequate,
        "status": "ready" if adequate else "small_sample",
        "method": "two-sided pooled proportions z test",
        "ci_method": "unpooled normal difference interval",
        "confidence_level": 1 - alpha,
        "normal_approximation_adequate": adequate,
        "warning": None if adequate else "A binomial cell contains fewer than five users; asymptotic inference is withheld.",
    }


def holm_adjust(p_values: Iterable[float | None]) -> list[float | None]:
    """Holm adjustment retains the planned family size, including missing tests."""
    values = list(p_values)
    valid: list[tuple[int, float]] = []
    for index, value in enumerate(values):
        if value is not None:
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("P values must be finite fractions")
            valid.append((index, value))
    ordered = sorted(valid, key=lambda item: item[1])
    adjusted: list[float | None] = [None] * len(values)
    previous = 0.0
    for position, (index, value) in enumerate(ordered):
        previous = max(previous, min(1.0, (len(values) - position) * value))
        adjusted[index] = previous
    return adjusted


def sample_ratio_mismatch(
    counts: Iterable[int], expected_proportions: Iterable[float] | None = None,
    threshold: float = 0.001,
) -> dict[str, Any]:
    """Pearson chi-square SRM check on assignments, never on conversions."""
    observed = list(counts)
    if len(observed) < 2 or any(not isinstance(n, int) or n < 0 for n in observed):
        raise ValueError("SRM requires at least two non-negative integer counts")
    proportions = list(expected_proportions) if expected_proportions is not None else [1 / len(observed)] * len(observed)
    if (len(proportions) != len(observed) or any(p <= 0 for p in proportions)
            or not math.isclose(sum(proportions), 1.0, abs_tol=1e-8)):
        raise ValueError("Expected allocation must contain positive proportions summing to one")
    total = sum(observed)
    if not total:
        return {"p_value": None, "mismatch": False, "status": "insufficient_data", "observed": observed}
    expected = [total * p for p in proportions]
    statistic = sum((actual - target) ** 2 / target for actual, target in zip(observed, expected))
    p_value = float(chi2.sf(statistic, len(observed) - 1))
    return {"statistic": statistic, "p_value": p_value, "mismatch": p_value < threshold,
            "threshold": threshold, "observed": observed, "expected": expected,
            "status": "ready", "unit": "assigned users"}


def analyze_experiment(arms: list[dict[str, Any]], alpha: float = 0.05) -> dict[str, Any]:
    """Summarize fixed-window, exposed-user Bernoulli outcomes in three arms.

    Input: variant, assigned_users, exposed_users, converted_users, engaged_users,
    sessions, errors, avg_load_time_ms, model_cost_usd. Session metrics are guardrails;
    their rows are not independent observations for the primary significance test.
    """
    if not arms or len({arm["variant"] for arm in arms}) != len(arms):
        raise ValueError("Experiment arms must be present and unique")
    by_variant = {arm["variant"]: dict(arm) for arm in arms}
    if "control" not in by_variant:
        raise ValueError("A control arm is required")
    prepared: list[dict[str, Any]] = []
    for arm in arms:
        assigned = int(arm["assigned_users"])
        exposed = int(arm["exposed_users"])
        converted = int(arm["converted_users"])
        engaged = int(arm.get("engaged_users", 0))
        _validate_count(exposed, assigned)
        _validate_count(converted, exposed)
        _validate_count(engaged, exposed)
        prepared.append({**arm,
                         "conversion_rate": converted / exposed if exposed else None,
                         "engagement_rate": engaged / exposed if exposed else None,
                         "exposure_rate": exposed / assigned if assigned else None,
                         "denominator": exposed,
                         "numerator": converted})
    control = by_variant["control"]
    comparisons = []
    for variant, arm in by_variant.items():
        if variant == "control":
            continue
        result = compare_proportions(int(control["converted_users"]), int(control["exposed_users"]),
                                     int(arm["converted_users"]), int(arm["exposed_users"]), alpha)
        comparisons.append({"variant": variant, "control": "control", **result})
    adjusted = holm_adjust(comparison["p_value"] for comparison in comparisons)
    # Bonferroni simultaneous CIs match the family-wise confidence statement.
    family_size = max(1, len(comparisons))
    for comparison, adjusted_p in zip(comparisons, adjusted):
        arm = by_variant[comparison["variant"]]
        family_result = compare_proportions(int(control["converted_users"]), int(control["exposed_users"]),
                                            int(arm["converted_users"]), int(arm["exposed_users"]), alpha / family_size)
        comparison["adjusted_p_value"] = adjusted_p
        comparison["significant"] = (adjusted_p is not None and adjusted_p < alpha
                                      and comparison.get("normal_approximation_adequate", False))
        comparison["adjustment"] = "Holm, two treatment-versus-control comparisons"
        comparison["simultaneous_confidence_interval_pp"] = family_result["confidence_interval_pp"]
        comparison["decision"] = ("positive evidence" if comparison["significant"] and comparison["absolute_lift"] > 0
                                  else "negative evidence" if comparison["significant"] else "inconclusive")
    srm = sample_ratio_mismatch([int(arm["assigned_users"]) for arm in arms]) if len(arms) > 1 else {"status": "insufficient_data", "mismatch": False, "p_value": None}
    guardrails = []
    control_latency = float(control.get("avg_load_time_ms") or 0)
    for arm in prepared:
        sessions = int(arm.get("sessions", 0))
        errors = int(arm.get("errors", 0))
        latency = float(arm.get("avg_load_time_ms") or 0)
        cost = float(arm.get("model_cost_usd") or 0)
        guardrails.append({"variant": arm["variant"], "sessions": sessions,
                           "application_error_rate": errors / sessions if sessions else None,
                           "avg_load_time_ms": latency,
                           "latency_delta_ms": latency - control_latency,
                           "model_cost_usd": cost,
                           "cost_per_search_usd": cost / sessions if sessions else None,
                           "latency_budget_passed": latency <= 2500,
                           "unit": "sessions; descriptive guardrails"})
    return {"primary_metric": "Users with ≥1 submitted application / exposed users",
            "assignment_unit": "user", "analysis_unit": "user",
            "window_start": "2026-09-21", "window_end": "2026-10-04",
            "alpha": alpha, "variants": prepared, "comparisons": comparisons,
            "srm": srm, "guardrails": guardrails,
            "status": ("assignment_review_required" if srm["mismatch"]
                       else "analyzed" if any(item["p_value"] is not None for item in comparisons)
                       else "insufficient_data"),
            "synthetic": True,
            "limitations": ["Synthetic behavioral assumptions are not an evaluation of actual model quality.",
                            "Conditional exposed-user analysis requires exposure to be unaffected by assignment; compare exposure rates.",
                            "No continuous monitoring correction is applied; use this predeclared fixed window.",
                            "Guardrail differences are descriptive, not independent session-level significance tests.",
                            "Pointwise 95% intervals accompany Holm-adjusted decisions; simultaneous intervals are also provided."]}
