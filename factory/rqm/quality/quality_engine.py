from __future__ import annotations

from pathlib import Path

from factory.rqm.model import Report, Result
from factory.rqm.providers.provider_registry import ProviderRegistry
from factory.rqm.quality.score_engine import ScoreEngine
from factory.rqm.quality.decision_policy import DecisionPolicy


class QualityEngine:
    """
    Executes all registered quality providers and builds
    a unified Report using the Common Domain Model.
    """

    def __init__(
        self,
        root: Path,
        registry: ProviderRegistry,
    ) -> None:
        self.root = root
        self.registry = registry

        self.score_engine = ScoreEngine()
        self.decision_policy = DecisionPolicy()

    def run(self) -> Report:
        """
        Execute every registered provider.

        Returns
        -------
        Report
            Unified quality report.
        """

        results: list[Result] = []

        for provider in self.registry.create_all(self.root):

            provider_result = provider.run()

            if hasattr(provider_result, "to_result"):
                results.append(provider_result.to_result())

            elif isinstance(provider_result, Result):
                results.append(provider_result)

            else:
                raise TypeError(
                    f"{provider.__class__.__name__} returned "
                    f"unsupported result type: "
                    f"{type(provider_result).__name__}"
                )

        score = self.score_engine.calculate(results)

        decision = self.decision_policy.decide(score)

        return Report(
            results=results,
            score=score.value,
            decision=decision,
        )