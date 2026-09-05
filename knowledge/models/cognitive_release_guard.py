"""Fail-closed authorization boundary for cognitive document release."""

from __future__ import annotations

from dataclasses import dataclass

from knowledge.models.action_plan import ActionPlan, PlanStatus
from knowledge.models.decision_model import DecisionModel, DecisionStatus
from knowledge.models.document_binding import DocumentBinding, DocumentStatus
from knowledge.models.strategy_model import StrategyModel, StrategyStatus


@dataclass(frozen=True, slots=True)
class ReleaseAuthorization:
    allowed: bool
    reasons: tuple[str, ...]
    document_id: str
    document_version: int

    def __post_init__(self) -> None:
        if not self.document_id.strip() or self.document_version < 1:
            raise ValueError("ReleaseAuthorization requires a valid document identity")
        if self.allowed and self.reasons:
            raise ValueError("allowed release cannot contain blocking reasons")
        if not self.allowed and not self.reasons:
            raise ValueError("blocked release requires at least one reason")


def _has_binding_ref(
    binding: DocumentBinding,
    artifact_type: str,
    artifact_id: str,
    version: int,
) -> bool:
    return any(
        ref.artifact_type == artifact_type
        and ref.artifact_id == artifact_id
        and ref.version == version
        for ref in binding.input_refs
    )


def authorize_cognitive_release(
    *,
    binding: DocumentBinding,
    decision: DecisionModel,
    strategy: StrategyModel,
    plan: ActionPlan | None,
) -> ReleaseAuthorization:
    """Authorize external release only for a complete, approved cognitive chain."""

    reasons: list[str] = []

    if decision.status is not DecisionStatus.SELECTED:
        reasons.append("decision_not_selected")

    if strategy.status is not StrategyStatus.SELECTED:
        reasons.append("strategy_not_selected")
    if (
        strategy.decision_id != decision.decision_id
        or strategy.decision_version != decision.version
    ):
        reasons.append("strategy_decision_mismatch")

    if plan is None:
        reasons.append("action_plan_missing")
    else:
        if (
            plan.strategy_id != strategy.strategy_id
            or plan.strategy_version != strategy.version
        ):
            reasons.append("plan_strategy_mismatch")
        if plan.status not in {PlanStatus.ACTIVE, PlanStatus.COMPLETED}:
            reasons.append("action_plan_not_active")

    if binding.status is not DocumentStatus.APPROVED:
        reasons.append("document_not_approved")
    if binding.approval_ref is None or not binding.approval_ref.strip():
        reasons.append("human_approval_missing")

    if not _has_binding_ref(binding, "decision", decision.decision_id, decision.version):
        reasons.append("decision_binding_missing")
    if not _has_binding_ref(binding, "strategy", strategy.strategy_id, strategy.version):
        reasons.append("strategy_binding_missing")
    if plan is not None and not _has_binding_ref(
        binding,
        "plan",
        plan.plan_id,
        plan.version,
    ):
        reasons.append("plan_binding_missing")

    unique_reasons = tuple(dict.fromkeys(reasons))
    return ReleaseAuthorization(
        allowed=not unique_reasons,
        reasons=unique_reasons,
        document_id=binding.document_id,
        document_version=binding.version,
    )
