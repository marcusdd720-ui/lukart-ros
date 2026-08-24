from __future__ import annotations

from enum import StrEnum

from factory.rqm.model.decision import Decision


class ReleaseDecision(StrEnum):
    """
    Legacy compatibility layer.

    Deprecated in RQM 4.0.
    Use factory.rqm.model.decision.Decision instead.
    """

    READY_FOR_MERGE = Decision.READY_FOR_MERGE.value
    READY_FOR_RELEASE = Decision.READY_WITH_WARNINGS.value
    MANUAL_REVIEW = Decision.NEEDS_REVIEW.value
    BLOCKED = Decision.BLOCK_RELEASE.value
    UNKNOWN = Decision.UNKNOWN.value

    def to_decision(self) -> Decision:
        """Convert legacy ReleaseDecision to Decision."""
        mapping = {
            ReleaseDecision.UNKNOWN: Decision.UNKNOWN,
            ReleaseDecision.READY_FOR_MERGE: Decision.READY_FOR_MERGE,
            ReleaseDecision.READY_FOR_RELEASE: Decision.READY_WITH_WARNINGS,
            ReleaseDecision.MANUAL_REVIEW: Decision.NEEDS_REVIEW,
            ReleaseDecision.BLOCKED: Decision.BLOCK_RELEASE,
        }
        return mapping[self]

    @classmethod
    def from_decision(cls, decision: Decision) -> ReleaseDecision:
        """Convert Decision to the legacy ReleaseDecision enum."""
        mapping = {
            Decision.UNKNOWN: cls.UNKNOWN,
            Decision.READY_FOR_MERGE: cls.READY_FOR_MERGE,
            Decision.READY_WITH_WARNINGS: cls.READY_FOR_RELEASE,
            Decision.NEEDS_REVIEW: cls.MANUAL_REVIEW,
            Decision.BLOCK_RELEASE: cls.BLOCKED,
        }
        return mapping[decision]
