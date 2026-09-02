"""Tests for the real deterministic KQM fact-extraction experiment."""

from validation.kqm_experiment import run_experiment


def test_real_extractor_reaches_expected_development_and_validation_metrics() -> None:
    results = run_experiment()

    assert set(results) == {"development", "validation"}

    expected = {
        "development": (57, 3),
        "validation": (19, 1),
    }
    for name, metrics in results.items():
        true_positive, false_negative = expected[name]
        total = true_positive + false_negative

        assert metrics.true_positive == true_positive
        assert metrics.false_positive == 0
        assert metrics.false_negative == false_negative
        assert metrics.precision == 1.0
        assert metrics.recall == true_positive / total
        assert metrics.f1 == 2 * (1.0 * (true_positive / total)) / (1.0 + (true_positive / total))
        assert metrics.critical_recall == 1.0
        assert metrics.critical_precision == 1.0
        assert metrics.critical_fact_loss == 0
        assert metrics.case_number_false_positive_rate == 0.0
        assert metrics.provenance_completeness == 1.0
