"""Deterministic performance-budget and SLA evaluation contracts."""

from __future__ import annotations

import math
from dataclasses import dataclass


def _finite_non_negative(name: str, value: float) -> float:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value


@dataclass(frozen=True, slots=True)
class PerformanceMeasurement:
    scenario_id: str
    runtime_ms: float
    peak_memory_mb: float
    model_calls: int
    cost_units: float

    def __post_init__(self) -> None:
        scenario = self.scenario_id.strip()
        if not scenario:
            raise ValueError("scenario_id cannot be blank")
        object.__setattr__(self, "scenario_id", scenario)
        object.__setattr__(self, "runtime_ms", _finite_non_negative("runtime_ms", self.runtime_ms))
        object.__setattr__(
            self,
            "peak_memory_mb",
            _finite_non_negative("peak_memory_mb", self.peak_memory_mb),
        )
        if self.model_calls < 0:
            raise ValueError("model_calls must be non-negative")
        object.__setattr__(self, "cost_units", _finite_non_negative("cost_units", self.cost_units))


@dataclass(frozen=True, slots=True)
class PerformanceBudget:
    max_runtime_ms: float
    max_peak_memory_mb: float
    max_model_calls: int
    max_cost_units: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "max_runtime_ms",
            _finite_non_negative("max_runtime_ms", self.max_runtime_ms),
        )
        object.__setattr__(
            self,
            "max_peak_memory_mb",
            _finite_non_negative("max_peak_memory_mb", self.max_peak_memory_mb),
        )
        if self.max_model_calls < 0:
            raise ValueError("max_model_calls must be non-negative")
        object.__setattr__(
            self,
            "max_cost_units",
            _finite_non_negative("max_cost_units", self.max_cost_units),
        )


@dataclass(frozen=True, slots=True)
class PerformanceBudgetResult:
    passed: bool
    scenario_id: str
    violations: tuple[str, ...]


def evaluate_performance_budget(
    measurement: PerformanceMeasurement,
    budget: PerformanceBudget,
) -> PerformanceBudgetResult:
    violations: list[str] = []
    if measurement.runtime_ms > budget.max_runtime_ms:
        violations.append("runtime_ms")
    if measurement.peak_memory_mb > budget.max_peak_memory_mb:
        violations.append("peak_memory_mb")
    if measurement.model_calls > budget.max_model_calls:
        violations.append("model_calls")
    if measurement.cost_units > budget.max_cost_units:
        violations.append("cost_units")
    return PerformanceBudgetResult(
        passed=not violations,
        scenario_id=measurement.scenario_id,
        violations=tuple(violations),
    )
