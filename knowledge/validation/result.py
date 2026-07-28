"""
Knowledge Operating System (KOS)

File: knowledge/validation/result.py
Version: 2.0
Sprint: GRAPH-010A

Validation result models.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ValidationIssue:
    """
    Represents a single validation issue.
    """

    code: str
    message: str


@dataclass(slots=True)
class ValidationResult:
    """
    Result returned by Validation Engine.
    """

    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.issues

    def add(
        self,
        code: str,
        message: str,
    ) -> None:
        """
        Add validation issue.
        """

        self.issues.append(
            ValidationIssue(
                code=code,
                message=message,
            )
        )

    def merge(
        self,
        other: ValidationResult,
    ) -> None:
        """
        Merge another validation result.
        """

        self.issues.extend(other.issues)

    def __len__(self) -> int:
        return len(self.issues)
