"""Tests for the real deterministic KQM fact-extraction experiment."""

from validation.kqm_experiment import run_experiment


def test_real_extractor_reaches_expected_development_and_validation_metrics() -> None:
    results = run_experiment()

    assert set(results) == {"development", "validation"}

    for metrics in results.values():
        assert metrics.true_positive == 48
        assert metrics.false_positive == 0
        assert metrics.false_negative == 3
        assert metrics.precision == 1.0
        assert metrics.recall == 48 / 51
        assert metrics.f1 == 2 * (1.0 * (48 / 51)) / (1.0 + (48 / 51))
        assert metrics.critical_recall == 1.0
        assert metrics.critical_precision == 1.0
        assert metrics.critical_fact_loss == 0
        assert metrics.case_number_false_positive_rate == 0.0
        assert metrics.provenance_completeness == 1.0
