from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from factory.rqm.model.finding import Finding
from factory.rqm.model.severity import Severity


@dataclass(slots=True)
class Result:
    """
    Result produced by a single quality provider.

    A Result contains all findings reported by the provider together
    with execution metadata.
    """

    name: str

    findings: list[Finding] = field(default_factory=list)

    duration: float = 0.0

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """
        True when the provider reported no ERROR or CRITICAL findings.
        """
        return not any(
            finding.severity in (Severity.ERROR, Severity.CRITICAL)
            for finding in self.findings
        )

    @property
    def failed(self) -> bool:
        """Convenience inverse of passed."""
        return not self.passed

    @property
    def warning_count(self) -> int:
        return sum(
            finding.severity == Severity.WARNING
            for finding in self.findings
        )

    @property
    def error_count(self) -> int:
        return sum(
            finding.severity == Severity.ERROR
            for finding in self.findings
        )

    @property
    def critical_count(self) -> int:
        return sum(
            finding.severity == Severity.CRITICAL
            for finding in self.findings
        )

    @property
    def info_count(self) -> int:
        return sum(
            finding.severity == Severity.INFO
            for finding in self.findings
        )

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    def has_severity(self, severity: Severity) -> bool:
        """
        Return True if the result contains at least one finding
        with the given severity.
        """
        return any(
            finding.severity == severity
            for finding in self.findings
        )

    def add_finding(self, finding: Finding) -> None:
        """Append a finding to the result."""
        self.findings.append(finding)