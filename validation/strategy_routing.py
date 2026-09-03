"""Measured strategy benchmarking and fail-closed routing contracts."""

from __future__ import annotations

from dataclasses import dataclass
from string import hexdigits

from learning.experiment import MetricDirection
from learning.models import MetricValue

_HEX_DIGITS = frozenset(hexdigits.lower())


@dataclass(frozen=True, slots=True)
class StrategyBenchmark:
    strategy_id: str
    strategy_version: str
    benchmark_id: str
    benchmark_digest: str
    metrics: tuple[MetricValue, ...]
    eligible: bool
    locked_evaluation_used_for_tuning: bool = False

    def __post_init__(self) -> None:
        for field_name in ("strategy_id", "strategy_version", "benchmark_id"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name} cannot be blank")
            object.__setattr__(self, field_name, value)
        digest = self.benchmark_digest.strip().lower()
        if len(digest) != 64 or any(char not in _HEX_DIGITS for char in digest):
            raise ValueError("benchmark_digest must be a lowercase SHA-256 digest")
        object.__setattr__(self, "benchmark_digest", digest)
        names = [metric.name for metric in self.metrics]
        if not names or len(names) != len(set(names)):
            raise ValueError("strategy benchmark metrics must be non-empty and unique")
        if self.locked_evaluation_used_for_tuning:
            raise ValueError("locked evaluation cannot be used for strategy tuning")

    def metric_map(self) -> dict[str, float]:
        return {metric.name: metric.value for metric in self.metrics}


@dataclass(frozen=True, slots=True)
class StrategyRoutingPolicy:
    primary_metric: str
    direction: MetricDirection
    minimum_metrics: tuple[MetricValue, ...] = ()
    maximum_metrics: tuple[MetricValue, ...] = ()

    def __post_init__(self) -> None:
        primary = self.primary_metric.strip()
        if not primary:
            raise ValueError("primary_metric cannot be blank")
        object.__setattr__(self, "primary_metric", primary)
        minimum_names = [metric.name for metric in self.minimum_metrics]
        maximum_names = [metric.name for metric in self.maximum_metrics]
        if len(minimum_names) != len(set(minimum_names)):
            raise ValueError("minimum metric constraints must be unique")
        if len(maximum_names) != len(set(maximum_names)):
            raise ValueError("maximum metric constraints must be unique")
        if set(minimum_names) & set(maximum_names):
            raise ValueError("a metric cannot be both minimum and maximum constrained")


@dataclass(frozen=True, slots=True)
class StrategyRouteDecision:
    strategy_id: str
    strategy_version: str
    benchmark_id: str
    benchmark_digest: str
    primary_metric: str
    primary_value: float


class StrategyRoutingError(RuntimeError):
    """Raised when no unique evidence-backed strategy route exists."""


def _passes_constraints(
    metrics: dict[str, float],
    policy: StrategyRoutingPolicy,
) -> bool:
    for constraint in policy.minimum_metrics:
        if constraint.name not in metrics or metrics[constraint.name] < constraint.value:
            return False
    for constraint in policy.maximum_metrics:
        if constraint.name not in metrics or metrics[constraint.name] > constraint.value:
            return False
    return True


def route_strategy(
    benchmarks: tuple[StrategyBenchmark, ...],
    policy: StrategyRoutingPolicy,
) -> StrategyRouteDecision:
    """Route only among comparable, eligible strategies with a unique measured winner."""

    eligible = tuple(item for item in benchmarks if item.eligible)
    if not eligible:
        raise StrategyRoutingError("no eligible strategy benchmark exists")

    benchmark_keys = {(item.benchmark_id, item.benchmark_digest) for item in eligible}
    if len(benchmark_keys) != 1:
        raise StrategyRoutingError("eligible strategies were not measured on the same benchmark")

    candidates: list[tuple[float, StrategyBenchmark]] = []
    for item in eligible:
        metrics = item.metric_map()
        if policy.primary_metric not in metrics:
            continue
        if not _passes_constraints(metrics, policy):
            continue
        candidates.append((metrics[policy.primary_metric], item))
    if not candidates:
        raise StrategyRoutingError("no eligible strategy satisfies routing metric constraints")

    values = [value for value, _ in candidates]
    winner_value = (
        max(values)
        if policy.direction is MetricDirection.HIGHER_IS_BETTER
        else min(values)
    )
    winners = [item for value, item in candidates if value == winner_value]
    if len(winners) != 1:
        raise StrategyRoutingError("strategy routing is ambiguous at the measured primary metric")

    winner = winners[0]
    return StrategyRouteDecision(
        strategy_id=winner.strategy_id,
        strategy_version=winner.strategy_version,
        benchmark_id=winner.benchmark_id,
        benchmark_digest=winner.benchmark_digest,
        primary_metric=policy.primary_metric,
        primary_value=winner_value,
    )
