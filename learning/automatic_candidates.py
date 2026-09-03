"""Bounded automatic candidate generation from measured failures.

The generator proposes only a LearningCandidate. It has no patch, merge, promotion, or deployment
authority and abstains when no curated mapping exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from learning.candidates import candidate_from_failure
from learning.models import ChangeKind, LearningCandidate, LearningSource, MeasuredFailure


class CandidateGenerationStatus(StrEnum):
    GENERATED = "generated"
    ABSTAINED = "abstained"


@dataclass(frozen=True, slots=True, order=True)
class CandidateGenerationRule:
    rule_id: str
    source: LearningSource
    failure_code: str
    target_component: str
    change_kind: ChangeKind
    hypothesis: str
    success_criteria: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("rule_id", "failure_code", "target_component", "hypothesis"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name} cannot be blank")
            object.__setattr__(self, field_name, value)
        criteria = tuple(item.strip() for item in self.success_criteria)
        if not criteria or not all(criteria):
            raise ValueError("candidate generation rule requires success criteria")
        if len(criteria) != len(set(criteria)):
            raise ValueError("candidate generation success criteria must be unique")
        object.__setattr__(self, "success_criteria", criteria)


@dataclass(frozen=True, slots=True)
class CandidateGenerationDecision:
    status: CandidateGenerationStatus
    reason: str
    rule_id: str | None = None
    candidate: LearningCandidate | None = None

    def __post_init__(self) -> None:
        reason = self.reason.strip()
        if not reason:
            raise ValueError("candidate generation decision requires a reason")
        object.__setattr__(self, "reason", reason)
        if self.status is CandidateGenerationStatus.GENERATED:
            if self.rule_id is None or not self.rule_id.strip() or self.candidate is None:
                raise ValueError("generated decision requires rule and candidate")
        elif self.rule_id is not None or self.candidate is not None:
            raise ValueError("abstained decision cannot contain a generated candidate")


class AutomaticCandidateGenerator:
    """Exact-rule proposal generator that fails closed on unknown or ambiguous failure classes."""

    def __init__(self, rules: tuple[CandidateGenerationRule, ...]) -> None:
        rule_ids = [rule.rule_id for rule in rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("candidate generation rule ids must be unique")
        keys = [(rule.source, rule.failure_code) for rule in rules]
        if len(keys) != len(set(keys)):
            raise ValueError("candidate rules must be unique by source and failure code")
        self._rules = rules

    def generate(self, failure: MeasuredFailure) -> CandidateGenerationDecision:
        matched = tuple(
            rule
            for rule in self._rules
            if rule.source is failure.source and rule.failure_code == failure.code
        )
        if not matched:
            return CandidateGenerationDecision(
                status=CandidateGenerationStatus.ABSTAINED,
                reason="no curated automatic-candidate rule matches the measured failure",
            )

        rule = matched[0]
        candidate = candidate_from_failure(
            failure,
            target_component=rule.target_component,
            change_kind=rule.change_kind,
            hypothesis=rule.hypothesis,
            success_criteria=rule.success_criteria,
        )
        return CandidateGenerationDecision(
            status=CandidateGenerationStatus.GENERATED,
            reason="curated failure mapping produced a bounded learning candidate",
            rule_id=rule.rule_id,
            candidate=candidate,
        )
