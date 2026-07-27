from __future__ import annotations

from factory.rqm.model.provider_result import ProviderResult


class ScoreEngine:
    """
    Calculates overall quality score from provider results.
    """

    def calculate(self, results: list[ProviderResult]) -> float:
        score = 100.0

        for result in results:
            metrics = result.metrics or {}

            failed = int(metrics.get("failed", 0))
            errors = int(metrics.get("errors", 0))
            warnings = int(metrics.get("warnings", 0))

            if failed:
                score -= 40
                score -= failed * 2

            score -= errors * 8
            score -= warnings * 2

        return round(max(0.0, min(100.0, score)), 2)