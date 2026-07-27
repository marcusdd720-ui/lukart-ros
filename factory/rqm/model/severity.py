from __future__ import annotations

from enum import StrEnum


class Severity(StrEnum):
    """Severity level of a finding."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"