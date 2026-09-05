"""Typed KST-1.0 Strategy Model downstream of an authorized Decision."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from knowledge.models.decision_model import DecisionModel, DecisionStatus


class StrategyStatus(StrEnum):
    PROPOSED = "proposed"
    ABSTAIN = "abstain"
    SELECTED = "selected"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class StrategyApproach:
    approach_id: str
    description: str

    def __post_init__(self) -> None:
        if not self.approach_id.strip() or not self.description.strip():
            raise ValueError("StrategyApproach fields cannot be empty")


@dataclass(frozen=True, slots=True)
class StrategyModel:
    strategy_id: str
    decision_id: str
    decision_version: int
    objectives: tuple[str, ...]
    approach_options: tuple[StrategyApproach, ...] = ()
    selected_approach: str | None = None
    sequencing_constraints: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    risk_controls: tuple[str, ...] = ()
    evidence_actions: tuple[str, ...] = ()
    communication_actions: tuple[str, ...] = ()
    execution_preconditions: tuple[str, ...] = ()
    fallback_paths: tuple[str, ...] = ()
    rationale: str | None = None
    status: StrategyStatus = StrategyStatus.PROPOSED
    version: int = 1
    lineage: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.strategy_id.strip() or not self.decision_id.strip():
            raise ValueError("StrategyModel identity fields cannot be empty")
        if self.decision_version < 1 or self.version < 1:
            raise ValueError("StrategyModel versions must be >= 1")
        approach_ids = [approach.approach_id for approach in self.approach_options]
        if len(approach_ids) != len(set(approach_ids)):
            raise ValueError("Strategy approach IDs must be unique")
        text_values = (
            *self.objectives,
            *self.sequencing_constraints,
            *self.dependencies,
            *self.risk_controls,
            *self.evidence_actions,
            *self.communication_actions,
            *self.execution_preconditions,
            *self.fallback_paths,
            *self.lineage,
        )
        if any(not value.strip() for value in text_values):
            raise ValueError("StrategyModel text collections cannot contain empty values")
        if self.selected_approach is not None and self.selected_approach not in approach_ids:
            raise ValueError("selected_approach must reference an available approach")
        if self.status is StrategyStatus.SELECTED:
            if self.selected_approach is None:
                raise ValueError("SELECTED strategy requires selected_approach")
            if not self.objectives:
                raise ValueError("SELECTED strategy requires at least one objective")
            if self.rationale is None or not self.rationale.strip():
                raise ValueError("SELECTED strategy requires rationale")
        if self.status is StrategyStatus.ABSTAIN:
            if self.rationale is None or not self.rationale.strip():
                raise ValueError("ABSTAIN strategy requires rationale")

    @classmethod
    def build(
        cls,
        strategy_id: str,
        decision: DecisionModel,
        *,
        objectives: tuple[str, ...] = (),
        approach_options: tuple[StrategyApproach, ...] = (),
        selected_approach: str | None = None,
        sequencing_constraints: tuple[str, ...] = (),
        dependencies: tuple[str, ...] = (),
        risk_controls: tuple[str, ...] = (),
        evidence_actions: tuple[str, ...] = (),
        communication_actions: tuple[str, ...] = (),
        execution_preconditions: tuple[str, ...] = (),
        fallback_paths: tuple[str, ...] = (),
        rationale: str | None = None,
        status: StrategyStatus = StrategyStatus.PROPOSED,
        version: int = 1,
        lineage: tuple[str, ...] = (),
    ) -> StrategyModel:
        if decision.status not in {DecisionStatus.SELECTED, DecisionStatus.ABSTAIN}:
            raise ValueError("Strategy requires an authorized SELECTED or ABSTAIN Decision")
        if decision.status is DecisionStatus.ABSTAIN and status is StrategyStatus.SELECTED:
            raise ValueError("ABSTAIN Decision cannot produce a SELECTED strategy")
        return cls(
            strategy_id=strategy_id,
            decision_id=decision.decision_id,
            decision_version=decision.version,
            objectives=objectives,
            approach_options=approach_options,
            selected_approach=selected_approach,
            sequencing_constraints=sequencing_constraints,
            dependencies=dependencies,
            risk_controls=risk_controls,
            evidence_actions=evidence_actions,
            communication_actions=communication_actions,
            execution_preconditions=execution_preconditions,
            fallback_paths=fallback_paths,
            rationale=rationale,
            status=status,
            version=version,
            lineage=lineage,
        )
