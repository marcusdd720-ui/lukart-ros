from __future__ import annotations

from enum import StrEnum


class Decision(StrEnum):
    """
    Release decision produced by the Release Quality Manager.
    """

    UNKNOWN = "UNKNOWN"

    READY_FOR_MERGE = "READY_FOR_MERGE"

    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"

    NEEDS_REVIEW = "NEEDS_REVIEW"

    BLOCK_RELEASE = "BLOCK_RELEASE"

    @property
    def is_terminal(self) -> bool:
        """
        Returns True when the decision represents a completed evaluation.
        """
        return self is not Decision.UNKNOWN

    @property
    def allows_release(self) -> bool:
        """
        Returns True when the release is allowed.
        """
        return self in (
            Decision.READY_FOR_MERGE,
            Decision.READY_WITH_WARNINGS,
        )

    @property
    def blocks_release(self) -> bool:
        """
        Returns True when the release must not continue.
        """
        return self is Decision.BLOCK_RELEASE