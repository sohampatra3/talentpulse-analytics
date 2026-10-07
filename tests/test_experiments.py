"""Inferential tests check the statistical contract rather than UI snapshots."""

import pytest

from analytics.experiments import analyze_experiment, compare_proportions, holm_adjust, sample_ratio_mismatch


def test_known_user_conversion_lift_and_ci():
    result = compare_proportions(810, 10000, 1030, 10000)
    assert result["absolute_lift_pp"] == pytest.approx(2.2)
    assert result["relative_lift"] == pytest.approx(103 / 81 - 1)
    assert result["p_value"] < 1e-6
    assert result["confidence_interval_pp"][0] > 0
    assert result["confidence_interval_pp"][0] < 2.2 < result["confidence_interval_pp"][1]


def test_identical_groups_have_no_evidence():
    result = compare_proportions(80, 1000, 80, 1000)
    assert result["p_value"] == pytest.approx(1)
    assert result["absolute_lift"] == 0
    assert result["significant"] is False


def test_empty_group_is_inconclusive_not_zero_conversion():
    result = compare_proportions(0, 0, 10, 100)
    assert result["status"] == "insufficient_data"
    assert result["p_value"] is None
    assert result["control_rate"] is None


@pytest.mark.parametrize("successes,total", [(-1, 10), (11, 10), (0, -1), (1.5, 10)])
def test_impossible_binomial_counts_rejected(successes, total):
    with pytest.raises(ValueError):
        compare_proportions(successes, total, 2, 10)


def test_zero_baseline_does_not_report_infinite_relative_lift():
    result = compare_proportions(0, 100, 2, 100)
    assert result["relative_lift"] is None
    assert result["status"] == "small_sample"
    assert result["significant"] is False
    assert result["confidence_interval_pp"] is None
    assert result["p_value"] is None


def test_degenerate_all_success_or_all_failure_withholds_normal_inference():
    for successes in (0, 100):
        result = compare_proportions(successes, 100, successes, 100)
        assert result["p_value"] is None
        assert result["confidence_interval"] is None
        assert result["absolute_lift"] == 0


def test_holm_adjustment_reorders_back_and_is_monotone():
    assert holm_adjust([.04, .01, .03]) == pytest.approx([.06, .03, .06])
    assert holm_adjust([None, .01, .04]) == [None, .03, .08]


def test_srm_detects_assignment_imbalance():
    assert sample_ratio_mismatch([16667, 16666, 16667])["mismatch"] is False
    assert sample_ratio_mismatch([25000, 12500, 12500])["mismatch"] is True
    assert sample_ratio_mismatch([0, 0, 0])["status"] == "insufficient_data"


def test_non_equal_allocations_are_supported():
    result = sample_ratio_mismatch([100, 200, 700], [.1, .2, .7])
    assert result["p_value"] == 1
    assert result["mismatch"] is False


def test_primary_denominator_remains_users_despite_many_sessions():
    arms = [
        {"variant": "control", "assigned_users": 10000, "exposed_users": 9000, "converted_users": 729,
         "engaged_users": 7000, "sessions": 25000, "errors": 400, "avg_load_time_ms": 650, "model_cost_usd": 0},
        {"variant": "gpt4o", "assigned_users": 10000, "exposed_users": 9000, "converted_users": 927,
         "engaged_users": 7500, "sessions": 30000, "errors": 440, "avg_load_time_ms": 1300, "model_cost_usd": 54},
        {"variant": "ollama", "assigned_users": 10000, "exposed_users": 9000, "converted_users": 873,
         "engaged_users": 7300, "sessions": 31000, "errors": 460, "avg_load_time_ms": 1800, "model_cost_usd": 21.7},
    ]
    result = analyze_experiment(arms)
    assert result["variants"][0]["conversion_rate"] == pytest.approx(.081)
    assert result["variants"][1]["denominator"] == 9000
    assert result["comparisons"][0]["absolute_lift_pp"] == pytest.approx(2.2)
    assert all(comparison["adjusted_p_value"] >= comparison["p_value"] for comparison in result["comparisons"])
    assert result["guardrails"][1]["cost_per_search_usd"] == pytest.approx(.0018)
    assert result["analysis_unit"] == "user"
    assert result["synthetic"] is True


def test_conversion_cannot_exceed_exposed_population():
    with pytest.raises(ValueError):
        analyze_experiment([{"variant": "control", "assigned_users": 100, "exposed_users": 20,
                             "converted_users": 21, "engaged_users": 0}])


def test_empty_exposure_population_has_no_experiment_decision():
    result = analyze_experiment([
        {"variant": name, "assigned_users": 100, "exposed_users": 0,
         "converted_users": 0, "engaged_users": 0}
        for name in ("control", "gpt4o", "ollama")
    ])
    assert result["status"] == "insufficient_data"
    assert all(item["decision"] == "inconclusive" for item in result["comparisons"])
