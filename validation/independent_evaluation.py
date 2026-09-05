"""Independent evaluation protocol with explicit external-review boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from validation.measurement import MeasurementSnapshot


class ReviewOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING = "PENDING"
    NOT_PERFORMED = "NOT_PERFORMED"


@dataclass(frozen=True, slots=True)
class ReviewerAssessment:
    """Assessment supplied by an external reviewer."""

    reviewer_id: str
    outcome: ReviewOutcome
    rationale: str
    evidence_ref: str


@dataclass(frozen=True, slots=True)
class EvaluationRecord:
    """Immutable evaluation record binding measurements to external assessment."""

    measurements: MeasurementSnapshot
    assessment: ReviewerAssessment


class IndependentEvaluationError(ValueError):
    """Raised when an external-review record is incomplete or non-independent."""


class IndependentEvaluator:
    """Accept external assessments without generating or modifying the outcome."""

    forbidden_reviewer_ids = frozenset({"system", "automated", "factory"})

    def record(
        self,
        measurements: MeasurementSnapshot,
        assessment: ReviewerAssessment,
    ) -> EvaluationRecord:
        reviewer_id = assessment.reviewer_id.strip()
        if not reviewer_id:
            raise IndependentEvaluationError("reviewer_id is required")
        if reviewer_id.lower() in self.forbidden_reviewer_ids:
            raise IndependentEvaluationError("reviewer_id must identify an external reviewer")
        if assessment.outcome not in {ReviewOutcome.PASS, ReviewOutcome.FAIL}:
            raise IndependentEvaluationError(
                "independent evaluation outcome must be PASS or FAIL"
            )
        if not assessment.rationale.strip():
            raise IndependentEvaluationError("rationale is required")
        if not assessment.evidence_ref.strip():
            raise IndependentEvaluationError("evidence_ref is required")
        return EvaluationRecord(measurements=measurements, assessment=assessment)
