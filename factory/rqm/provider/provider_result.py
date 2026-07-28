from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from factory.rqm.model import Finding, Result


@dataclass(slots=True)
class ProviderResult:
    """
    Legacy compatibility wrapper around the Common Domain Model.

    Existing providers may continue returning ProviderResult while the
    internal pipeline operates on Result.
    """

    provider: str

    findings: list[Finding] = field(default_factory=list)

    duration: float = 0.0

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_result(self) -> Result:
        """
        Convert this ProviderResult into the Common Domain Model.
        """
        return Result(
            name=self.provider,
            findings=list(self.findings),
            duration=self.duration,
            metadata=dict(self.metadata),
        )

    @classmethod
    def from_result(cls, result: Result) -> ProviderResult:
        """
        Create a ProviderResult from the Common Domain Model.
        """
        return cls(
            provider=result.name,
            findings=list(result.findings),
            duration=result.duration,
            metadata=dict(result.metadata),
        )

    @property
    def passed(self) -> bool:
        """
        True when the provider produced no ERROR or CRITICAL findings.
        """
        return self.to_result().passed

    @property
    def failed(self) -> bool:
        """
        Convenience inverse of passed.
        """
        return self.to_result().failed

    @property
    def finding_count(self) -> int:
        """
        Total number of findings.
        """
        return len(self.findings)

    def add_finding(self, finding: Finding) -> None:
        """
        Append a finding.
        """
        self.findings.append(finding)

    def __len__(self) -> int:
        return len(self.findings)

    def __bool__(self) -> bool:
        return self.passed

    def __iter__(self) -> Iterator[Finding]:
        return iter(self.findings)
