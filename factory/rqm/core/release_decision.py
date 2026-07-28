from __future__ import annotations

from factory.rqm.model.provider_result import ProviderResult

from factory.rqm.model.release_decision import ReleaseDecision


class DecisionPolicy:
    """
    Policy engine responsible for deciding whether
    the project is ready for release.
    """

    def decide(
        self,
        score: float,
        results: list[ProviderResult],
    ) -> ReleaseDecision:

        has_errors = any(
            finding.severity == "ERROR"
            for result in results
            for finding in result.findings
        )

        if has_errors:
            return ReleaseDecision.BLOCKED

        if score < 85:
            return ReleaseDecision.BLOCKED

        if score < 95:
            return ReleaseDecision.MANUAL_REVIEW

        return ReleaseDecision.READY_FOR_MERGE
