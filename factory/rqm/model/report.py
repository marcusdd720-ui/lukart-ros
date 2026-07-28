from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from factory.rqm.model.decision import Decision
from factory.rqm.model.result import Result


@dataclass(slots=True)
class Report:
    """
    Aggregated Release Quality Manager report.

    A Report is the aggregate root of the Common Domain Model.
    It combines provider results together with the overall
    quality assessment and release decision.
    """

    results: list[Result] = field(default_factory=list)

    score: float = 100.0

    decision: Decision = Decision.UNKNOWN

    created_at: datetime = field(default_factory=datetime.utcnow)

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def findings(self) -> list:
        """
        Return a flattened list of findings from all provider results.
        """
        return [finding for result in self.results for finding in result.findings]

    @property
    def passed(self) -> bool:
        """
        True if every provider passed.
        """
        return all(result.passed for result in self.results)

    @property
    def failed(self) -> bool:
        """
        Convenience inverse of passed.
        """
        return not self.passed

    @property
    def provider_count(self) -> int:
        """
        Number of executed providers.
        """
        return len(self.results)

    @property
    def finding_count(self) -> int:
        """
        Total number of findings.
        """
        return len(self.findings)

    def get_result(self, name: str) -> Result | None:
        """
        Return a provider result by its name.

        Parameters
        ----------
        name
            Provider name.

        Returns
        -------
        Result | None
            Matching provider result or None.
        """
        for result in self.results:
            if result.name == name:
                return result

        return None

    def has_failures(self) -> bool:
        """
        Return True if at least one provider failed.
        """
        return any(result.failed for result in self.results)

    def summary(self) -> dict[str, Any]:
        """
        Return a lightweight report summary.
        """
        return {
            "providers": self.provider_count,
            "findings": self.finding_count,
            "score": self.score,
            "decision": self.decision.value,
            "passed": self.passed,
        }
