"""
Ontology Validation Report.

Rich validation report used by validators and services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ValidationSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(slots=True, frozen=True)
class ValidationMessage:
    """
    Single validation message.
    """

    severity: ValidationSeverity
    code: str
    message: str
    location: str | None = None


@dataclass(slots=True)
class ValidationReport:
    """
    Validation result.

    Instead of returning True/False validators should return
    ValidationReport.
    """

    messages: list[ValidationMessage] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(
            m.severity == ValidationSeverity.ERROR
            for m in self.messages
        )

    def add_info(
        self,
        code: str,
        message: str,
        *,
        location: str | None = None,
    ) -> None:
        self.messages.append(
            ValidationMessage(
                ValidationSeverity.INFO,
                code,
                message,
                location,
            )
        )

    def add_warning(
        self,
        code: str,
        message: str,
        *,
        location: str | None = None,
    ) -> None:
        self.messages.append(
            ValidationMessage(
                ValidationSeverity.WARNING,
                code,
                message,
                location,
            )
        )

    def add_error(
        self,
        code: str,
        message: str,
        *,
        location: str | None = None,
    ) -> None:
        self.messages.append(
            ValidationMessage(
                ValidationSeverity.ERROR,
                code,
                message,
                location,
            )
        )

    def extend(
        self,
        report: "ValidationReport",
    ) -> None:
        self.messages.extend(report.messages)

    def __bool__(self) -> bool:
        return self.is_valid