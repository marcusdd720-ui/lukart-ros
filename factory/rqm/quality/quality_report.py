from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from factory.rqm.model import Report, Result


@dataclass(slots=True)
class QualityReport:
    """
    Backward-compatible wrapper around the new Common Domain Model.

    Existing code can continue using QualityReport while the project
    is gradually migrated to Report.
    """

    results: list[Result] = field(default_factory=list)

    score: float = 100.0

    decision: str = "UNKNOWN"

    created_at: datetime = field(default_factory=datetime.utcnow)

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_report(self) -> Report:
        """Convert QualityReport to the new Report model."""
        return Report(
            results=list(self.results),
            score=self.score,
            decision=self.decision,
            created_at=self.created_at,
            metadata=dict(self.metadata),
        )

    @classmethod
    def from_report(cls, report: Report) -> "QualityReport":
        """Create QualityReport from the new Report model."""
        return cls(
            results=list(report.results),
            score=report.score,
            decision=report.decision,
            created_at=report.created_at,
            metadata=dict(report.metadata),
        )

    @property
    def findings(self):
        return self.to_report().findings

    @property
    def passed(self) -> bool:
        return self.to_report().passed

    @property
    def failed(self) -> bool:
        return self.to_report().failed

    def __len__(self) -> int:
        return len(self.results)

    def __bool__(self) -> bool:
        return self.passed

    def __iter__(self):
        return iter(self.results)