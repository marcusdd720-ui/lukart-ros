"""Typed KDM-1.0 Decision Model downstream of Problem and Evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from knowledge.models.evidence_assessment import EvidenceAssessment
from knowledge.models.problem_model import ProblemModel


class DecisionStatus(StrEnum):
    PROPOSED = "proposed"
    DEFERRED = "deferred"
    ABSTAIN = "abstain"
    SELECTED = "selected"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    EXECUTED = "executed"


@dataclass(frozen=True, slots=True)
class DecisionOption:
    option_id: str
    description: str

    def __post_init__(self) -> None:
        if not self.option_id.strip() or not self.description.strip():
            raise ValueError("DecisionOption fields cannot be empty")


@dataclass(frozen=True, slots=True)
class DecisionModel:
    decision_id: str
    problem_id: str
    problem_version: int
    evidence_assessment_refs: tuple[str, ...]
    options: tuple[DecisionOption, ...]
    assumptions: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    rejected_options: tuple[str, ...] = ()
    selected_option: str | None = None
    rationale: str | None = None
    authority: str | None = None
    status: DecisionStatus = DecisionStatus.PROPOSED
    version: int = 1
    lineage: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.decision_id.strip() or not self.problem_id.strip():
            raise ValueError("DecisionModel identity fields cannot be empty")
        if self.problem_version < 1 or self.version < 1:
            raise ValueError("DecisionModel versions must be >= 1")
        option_ids = [option.option_id for option in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("DecisionModel option IDs must be unique")
        text_values = (
            *self.evidence_assessment_refs,
            *self.assumptions,
            *self.risks,
            *self.rejected_options,
            *self.lineage,
        )
        if any(not value.strip() for value in text_values):
            raise ValueError("DecisionModel text references cannot contain empty values")
        if self.selected_option is not None and self.selected_option not in option_ids:
            raise ValueError("selected_option must reference an available option")
        unknown_rejected = set(self.rejected_options) - set(option_ids)
        if unknown_rejected:
            raise ValueError("rejected_options must reference available options")
        if self.status is DecisionStatus.SELECTED:
            if self.selected_option is None:
                raise ValueError("SELECTED decision requires selected_option")
            if self.rationale is None or not self.rationale.strip():
                raise ValueError("SELECTED decision requires rationale")
            if self.authority is None or not self.authority.strip():
                raise ValueError("SELECTED decision requires authority")
        if self.status is DecisionStatus.ABSTAIN:
            if self.rationale is None or not self.rationale.strip():
                raise ValueError("ABSTAIN decision requires rationale")

    @classmethod
    def build(
        cls,
        decision_id: str,
        problem: ProblemModel,
        *,
        evidence_assessments: tuple[EvidenceAssessment, ...] = (),
        options: tuple[DecisionOption, ...] = (),
        assumptions: tuple[str, ...] = (),
        risks: tuple[str, ...] = (),
        rejected_options: tuple[str, ...] = (),
        selected_option: str | None = None,
        rationale: str | None = None,
        authority: str | None = None,
        status: DecisionStatus = DecisionStatus.PROPOSED,
        version: int = 1,
        lineage: tuple[str, ...] = (),
    ) -> DecisionModel:
        for assessment in evidence_assessments:
            if assessment.problem_id != problem.problem_id:
                raise ValueError("evidence assessment belongs to another Problem")
            if assessment.problem_version != problem.version:
                raise ValueError("evidence assessment targets another Problem version")
        return cls(
            decision_id=decision_id,
            problem_id=problem.problem_id,
            problem_version=problem.version,
            evidence_assessment_refs=tuple(
                assessment.assessment_id for assessment in evidence_assessments
            ),
            options=options,
            assumptions=assumptions,
            risks=risks,
            rejected_options=rejected_options,
            selected_option=selected_option,
            rationale=rationale,
            authority=authority,
            status=status,
            version=version,
            lineage=lineage,
        )
