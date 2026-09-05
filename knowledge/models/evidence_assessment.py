"""Derived KEV-1.0 evidence assessment over a Problem Model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from knowledge.models.problem_model import ProblemModel


class AssessmentState(StrEnum):
    UNKNOWN = "unknown"
    SATISFIED = "satisfied"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"
    CONTRADICTED = "contradicted"


@dataclass(frozen=True, slots=True)
class EvidenceAssessment:
    assessment_id: str
    problem_id: str
    problem_version: int
    proposition_ref: str
    support_refs: tuple[str, ...] = ()
    contradiction_refs: tuple[str, ...] = ()
    provenance_state: AssessmentState = AssessmentState.UNKNOWN
    authenticity_state: AssessmentState = AssessmentState.UNKNOWN
    relevance_state: AssessmentState = AssessmentState.UNKNOWN
    completeness_state: AssessmentState = AssessmentState.UNKNOWN
    strength_state: AssessmentState = AssessmentState.UNKNOWN
    burden_ref: str | None = None
    missing_evidence: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    evaluator_version: str = "kev-1.0"
    version: int = 1

    def __post_init__(self) -> None:
        required = (
            self.assessment_id,
            self.problem_id,
            self.proposition_ref,
            self.evaluator_version,
        )
        if any(not value.strip() for value in required):
            raise ValueError("EvidenceAssessment identity fields cannot be empty")
        if self.problem_version < 1 or self.version < 1:
            raise ValueError("EvidenceAssessment versions must be >= 1")
        if self.burden_ref is not None and not self.burden_ref.strip():
            raise ValueError("EvidenceAssessment.burden_ref cannot be blank")
        text_values = (
            *self.support_refs,
            *self.contradiction_refs,
            *self.missing_evidence,
            *self.limitations,
        )
        if any(not value.strip() for value in text_values):
            raise ValueError("EvidenceAssessment references cannot contain empty values")

    @classmethod
    def build(
        cls,
        assessment_id: str,
        problem: ProblemModel,
        proposition_ref: str,
        *,
        support_refs: tuple[str, ...] = (),
        contradiction_refs: tuple[str, ...] = (),
        provenance_state: AssessmentState = AssessmentState.UNKNOWN,
        authenticity_state: AssessmentState = AssessmentState.UNKNOWN,
        relevance_state: AssessmentState = AssessmentState.UNKNOWN,
        completeness_state: AssessmentState = AssessmentState.UNKNOWN,
        strength_state: AssessmentState = AssessmentState.UNKNOWN,
        burden_ref: str | None = None,
        missing_evidence: tuple[str, ...] = (),
        limitations: tuple[str, ...] = (),
        evaluator_version: str = "kev-1.0",
        version: int = 1,
    ) -> EvidenceAssessment:
        return cls(
            assessment_id=assessment_id,
            problem_id=problem.problem_id,
            problem_version=problem.version,
            proposition_ref=proposition_ref,
            support_refs=support_refs,
            contradiction_refs=contradiction_refs,
            provenance_state=provenance_state,
            authenticity_state=authenticity_state,
            relevance_state=relevance_state,
            completeness_state=completeness_state,
            strength_state=strength_state,
            burden_ref=burden_ref,
            missing_evidence=missing_evidence,
            limitations=limitations,
            evaluator_version=evaluator_version,
            version=version,
        )
