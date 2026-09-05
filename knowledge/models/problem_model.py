"""Typed KMP-1.0 Problem Model over an immutable Case Model projection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from knowledge.models.case_model_projection import CaseModelProjection


class ProblemStatus(StrEnum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    BLOCKED = "blocked"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class EvidenceNeed:
    proposition_ref: str
    burden_ref: str | None = None
    supporting_refs: tuple[str, ...] = ()
    missing_categories: tuple[str, ...] = ()
    blocking: bool = False

    def __post_init__(self) -> None:
        if not self.proposition_ref.strip():
            raise ValueError("EvidenceNeed.proposition_ref cannot be empty")
        if self.burden_ref is not None and not self.burden_ref.strip():
            raise ValueError("EvidenceNeed.burden_ref cannot be blank")
        values_to_validate = (*self.supporting_refs, *self.missing_categories)
        if any(not value.strip() for value in values_to_validate):
            raise ValueError("EvidenceNeed references/categories cannot contain empty values")


@dataclass(frozen=True, slots=True)
class RiskDimension:
    name: str
    description: str

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.description.strip():
            raise ValueError("RiskDimension name and description cannot be empty")


@dataclass(frozen=True, slots=True)
class ProblemModel:
    problem_id: str
    case_id: str
    case_model_version: int
    scope_version: int
    decision_need: str
    stakeholder_interests: tuple[str, ...] = ()
    desired_outcomes: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    domain_frames: tuple[str, ...] = ()
    evidence_needs: tuple[EvidenceNeed, ...] = ()
    open_questions: tuple[str, ...] = ()
    risk_dimensions: tuple[RiskDimension, ...] = ()
    success_criteria: tuple[str, ...] = ()
    status: ProblemStatus = ProblemStatus.PROPOSED
    version: int = 1
    lineage: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.problem_id.strip():
            raise ValueError("ProblemModel.problem_id cannot be empty")
        if not self.case_id.strip():
            raise ValueError("ProblemModel.case_id cannot be empty")
        if not self.decision_need.strip():
            raise ValueError("ProblemModel.decision_need cannot be empty")
        if self.case_model_version < 1 or self.scope_version < 1 or self.version < 1:
            raise ValueError("ProblemModel versions must be >= 1")
        text_collections = (
            self.stakeholder_interests,
            self.desired_outcomes,
            self.constraints,
            self.domain_frames,
            self.open_questions,
            self.success_criteria,
            self.lineage,
        )
        if any(not value.strip() for values in text_collections for value in values):
            raise ValueError("ProblemModel text collections cannot contain empty values")

    @classmethod
    def build(
        cls,
        problem_id: str,
        case_model: CaseModelProjection,
        decision_need: str,
        *,
        stakeholder_interests: tuple[str, ...] = (),
        desired_outcomes: tuple[str, ...] = (),
        constraints: tuple[str, ...] = (),
        domain_frames: tuple[str, ...] = (),
        evidence_needs: tuple[EvidenceNeed, ...] = (),
        open_questions: tuple[str, ...] = (),
        risk_dimensions: tuple[RiskDimension, ...] = (),
        success_criteria: tuple[str, ...] = (),
        status: ProblemStatus = ProblemStatus.PROPOSED,
        version: int = 1,
        lineage: tuple[str, ...] = (),
    ) -> ProblemModel:
        return cls(
            problem_id=problem_id,
            case_id=case_model.case_id,
            case_model_version=case_model.version,
            scope_version=case_model.scope_version,
            decision_need=decision_need,
            stakeholder_interests=stakeholder_interests,
            desired_outcomes=desired_outcomes,
            constraints=constraints,
            domain_frames=domain_frames,
            evidence_needs=evidence_needs,
            open_questions=open_questions,
            risk_dimensions=risk_dimensions,
            success_criteria=success_criteria,
            status=status,
            version=version,
            lineage=lineage,
        )
