"""Capability-based executor routing."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import NightShiftContractError
from .executor_registry import ExecutorProfile


@dataclass(frozen=True, slots=True)
class RouteDecision:
    executor_id: str
    reason: str
    requires_local_writer: bool
    heavy_compute: bool
    max_parallel: int


def route_executor(
    *,
    required_capabilities: tuple[str, ...],
    executors: tuple[ExecutorProfile, ...],
    mutating: bool,
    require_independent_review: bool = False,
) -> RouteDecision:
    required = set(required_capabilities)
    candidates = [
        x
        for x in executors
        if x.enabled
        and required.issubset(set(x.capabilities))
        and (not mutating or x.mutating)
        and (not require_independent_review or x.independent_review)
    ]
    if not candidates:
        raise NightShiftContractError("no executor satisfies required capabilities")
    winner = min(candidates, key=lambda x: (x.cost_rank, x.executor_id))
    return RouteDecision(
        winner.executor_id,
        "minimum enabled cost rank satisfying capabilities",
        winner.requires_local_writer,
        winner.heavy_compute,
        winner.max_parallel,
    )
