from __future__ import annotations

import pytest

from validation.performance_budget import (
    PerformanceBudget,
    PerformanceMeasurement,
    evaluate_performance_budget,
)


def _budget() -> PerformanceBudget:
    return PerformanceBudget(
        max_runtime_ms=1000.0,
        max_peak_memory_mb=512.0,
        max_model_calls=4,
        max_cost_units=2.0,
    )


def test_performance_budget_passes_within_all_limits() -> None:
    result = evaluate_performance_budget(
        PerformanceMeasurement(
            scenario_id="synthetic-e2e",
            runtime_ms=500.0,
            peak_memory_mb=256.0,
            model_calls=2,
            cost_units=0.5,
        ),
        _budget(),
    )

    assert result.passed is True
    assert result.violations == ()


def test_performance_budget_reports_every_exceeded_resource() -> None:
    result = evaluate_performance_budget(
        PerformanceMeasurement(
            scenario_id="synthetic-over-budget",
            runtime_ms=1500.0,
            peak_memory_mb=1024.0,
            model_calls=8,
            cost_units=3.0,
        ),
        _budget(),
    )

    assert result.passed is False
    assert result.violations == (
        "runtime_ms",
        "peak_memory_mb",
        "model_calls",
        "cost_units",
    )


def test_performance_contract_rejects_non_finite_or_negative_values() -> None:
    with pytest.raises(ValueError, match="finite and non-negative"):
        PerformanceMeasurement("bad", float("nan"), 1.0, 0, 0.0)
    with pytest.raises(ValueError, match="non-negative"):
        PerformanceMeasurement("bad", 1.0, 1.0, -1, 0.0)
    with pytest.raises(ValueError, match="finite and non-negative"):
        PerformanceBudget(1.0, 1.0, 0, float("inf"))
