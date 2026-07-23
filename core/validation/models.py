"""
Validation Engine 2.0

File: core/validation/models.py
Sprint: F-010
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.models.ids import EntityId


class Severity(Enum):
    """Validation severity."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(slots=True)
class ValidationContext:
    """Validation execution context."""

    project: str | None = None
    case_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ValidationIssue:
    """Single validation issue."""

    code: str
    message: str
    severity: Severity
    entity_id: Optional[EntityId] = None


@dataclass(slots=True)
class ValidationReport:
    """Validation report."""

    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity in (
                Severity.ERROR,
                Severity.CRITICAL,
            )
        ]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == Severity.WARNING
        ]

    @property
    def infos(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == Severity.INFO
        ]

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)

    def extend(self, issues: list[ValidationIssue]) -> None:
        self.issues.extend(issues)

    def __len__(self) -> int:
        return len(self.issues)