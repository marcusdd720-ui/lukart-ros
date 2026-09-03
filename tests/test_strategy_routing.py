from __future__ import annotations

import pytest

from learning.experiment import MetricDirection
from learning.models import MetricValue
from validation.strategy_routing import (
    StrategyBenchmark,
    StrategyRoutingError,
    StrategyRoutingPolicy,
    route_strategy,
)

DIGEST = "a" * 64
OTHER_DIGEST = "b" * 64


def _benchmark(
    strategy_id: str,
    accuracy: float,
    unsafe_rate: float,
    *,
    eligible: bool = True,
    digest: str = DIGEST,
) -> StrategyBenchmark:
    return StrategyBenchmark(
        strategy_id=strategy_id,
        strategy_version="1.0.0",
        benchmark_id="reasoning-gold-v2-validation",
        benchmark_digest=digest,
        metrics=(
            MetricValue("decision_accuracy", accuracy),
            MetricValue("unsafe_conclusion_rate", unsafe_rate),
        ),
        eligible=eligible,
    )


def _policy() -> StrategyRoutingPolicy:
    return StrategyRoutingPolicy(
        primary_metric="decision_accuracy",
        direction=MetricDirection.HIGHER_IS_BETTER,
        maximum_metrics=(MetricValue("unsafe_conclusion_rate", 0.0),),
    )


def test_route_selects_unique_measured_winner_with_guardrails() -> None:
    decision = route_strategy(
        (
            _benchmark("strategy-a", 0.95, 0.0),
            _benchmark("strategy-b", 1.0, 0.0),
        ),
        _policy(),
    )

    assert decision.strategy_id == "strategy-b"
    assert decision.primary_value == 1.0


def test_route_excludes_ineligible_strategy_even_if_metric_is_better() -> None:
    decision = route_strategy(
        (
            _benchmark("certified", 0.95, 0.0),
            _benchmark("uncertified", 1.0, 0.0, eligible=False),
        ),
        _policy(),
    )

    assert decision.strategy_id == "certified"


def test_route_rejects_benchmarks_from_different_corpus_bytes() -> None:
    with pytest.raises(StrategyRoutingError, match="same benchmark"):
        route_strategy(
            (
                _benchmark("strategy-a", 0.95, 0.0),
                _benchmark("strategy-b", 1.0, 0.0, digest=OTHER_DIGEST),
            ),
            _policy(),
        )


def test_route_rejects_guardrail_violation() -> None:
    with pytest.raises(StrategyRoutingError, match="constraints"):
        route_strategy((_benchmark("unsafe", 1.0, 0.1),), _policy())


def test_route_rejects_metric_tie_instead_of_guessing() -> None:
    with pytest.raises(StrategyRoutingError, match="ambiguous"):
        route_strategy(
            (
                _benchmark("strategy-a", 1.0, 0.0),
                _benchmark("strategy-b", 1.0, 0.0),
            ),
            _policy(),
        )


def test_benchmark_rejects_locked_evaluation_used_for_tuning() -> None:
    with pytest.raises(ValueError, match="locked evaluation"):
        StrategyBenchmark(
            strategy_id="bad-strategy",
            strategy_version="1.0.0",
            benchmark_id="reasoning-gold-v2",
            benchmark_digest=DIGEST,
            metrics=(MetricValue("decision_accuracy", 1.0),),
            eligible=True,
            locked_evaluation_used_for_tuning=True,
        )
