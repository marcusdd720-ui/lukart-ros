from __future__ import annotations

from enum import StrEnum


class QualityStatus(StrEnum):
    """
    Legacy compatibility layer.

    Deprecated in RQM 4.0.

    The Common Domain Model determines provider status from
    Result.passed / Result.failed instead of storing it explicitly.
    """

    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"
    NOT_RUN = "NOT_RUN"

    @property
    def passed(self) -> bool:
        """Returns True if the status represents a successful execution."""
        return self is QualityStatus.PASS

    @property
    def failed(self) -> bool:
        """Returns True if the status represents a failed execution."""
        return self is QualityStatus.FAIL

    @property
    def executed(self) -> bool:
        """Returns True if the provider was executed."""
        return self not in (
            QualityStatus.NOT_RUN,
            QualityStatus.SKIPPED,
        )

    @property
    def terminal(self) -> bool:
        """Returns True if execution has finished."""
        return self is not QualityStatus.NOT_RUN
