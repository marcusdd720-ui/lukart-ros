from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from factory.rqm.model.decision import Decision
from factory.rqm.model.report import Report
from factory.rqm.model.result import Result


@dataclass(frozen=True, slots=True)
class QualityReport:
    """
    Legacy compatibility wrapper.

    This class provides backward compatibility for code that still
    expects the old QualityReport API while internally using the
    Common Domain Model (Report).
    """

    report: Report

    @property
    def version(self) -> str:
        return "4.0"

    @property
    def timestamp(self) -> datetime:
        return self.report.created_at

    @property
    def overall_score(self) -> float:
        return self.report.score

    @property
    def decision(self) -> Decision:
        return self.report.decision

    @property
    def providers(self) -> list[Result]:
        return self.report.results

    @property
    def trend(self) -> str:
        return self.report.metadata.get("trend", "NEW")

    @property
    def delta(self) -> float:
        return float(self.report.metadata.get("delta", 0.0))

    @property
    def metadata(self) -> dict[str, object]:
        return self.report.metadata

    def provider_map(self) -> dict[str, Result]:
        return {result.name: result for result in self.report.results}

    def has_critical_findings(self) -> bool:
        return any(result.failed for result in self.report.results)

    def to_report(self) -> Report:
        """
        Return the underlying Common Domain Model report.
        """
        return self.report

    @classmethod
    def from_report(cls, report: Report) -> QualityReport:
        """
        Create a compatibility wrapper from a Common Domain Model report.
        """
        return cls(report)
