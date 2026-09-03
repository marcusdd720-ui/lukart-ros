"""Runtime and traced-memory measurement for deterministic validation scenarios."""

from __future__ import annotations

import time
import tracemalloc
from collections.abc import Callable
from typing import TypeVar

from validation.performance_budget import PerformanceMeasurement

_T = TypeVar("_T")
_BYTES_PER_MIB = 1024 * 1024


def measure_performance(
    scenario_id: str,
    operation: Callable[[], _T],
    *,
    model_calls: int,
    cost_units: float,
) -> tuple[_T, PerformanceMeasurement]:
    """Execute one operation and record wall runtime plus peak traced Python memory."""

    if model_calls < 0:
        raise ValueError("model_calls must be non-negative")
    if cost_units < 0:
        raise ValueError("cost_units must be non-negative")

    tracemalloc.start()
    started = time.perf_counter()
    try:
        result = operation()
        runtime_ms = (time.perf_counter() - started) * 1000.0
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    measurement = PerformanceMeasurement(
        scenario_id=scenario_id,
        runtime_ms=runtime_ms,
        peak_memory_mb=peak_bytes / _BYTES_PER_MIB,
        model_calls=model_calls,
        cost_units=cost_units,
    )
    return result, measurement
