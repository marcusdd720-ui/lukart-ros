from __future__ import annotations

from knowledge.models.action_plan import ActionPlan, PlanStatus
from knowledge.models.cognitive_release_guard import authorize_cognitive_release
from knowledge.models.decision_model import DecisionModel, DecisionOption, DecisionStatus
from knowledge.models.document_binding import ArtifactRef, DocumentBinding, DocumentStatus
from knowledge.models.strategy_model import StrategyApproach, StrategyModel, StrategyStatus


def _selected_chain() -> tuple[DecisionModel, StrategyModel, ActionPlan]:
    decision = DecisionModel(
        decision_id="decision-1",
        problem_id="problem-1",
        problem_version=1,
        evidence_assessment_refs=("evidence-1",),
        options=(DecisionOption("file", "File the approved submission."),),
        selected_option="file",
        rationale="Verified evidence supports the selected procedural action.",
        authority="human:reviewer-1",
        status=DecisionStatus.SELECTED,
    )
    strategy = StrategyModel(
        strategy_id="strategy-1",
        decision_id=decision.decision_id,
        decision_version=decision.version,
        objectives=("Execute the authorized decision.",),
        approach_options=(StrategyApproach("submit", "Prepare and submit."),),
        selected_approach="submit",
        rationale="Selected by the authorized decision path.",
        status=StrategyStatus.SELECTED,
    )
    plan = ActionPlan(
        plan_id="plan-1",
        strategy_id=strategy.strategy_id,
        strategy_version=strategy.version,
        tasks=(),
        status=PlanStatus.ACTIVE,
    )
    return decision, strategy, plan


def _approved_binding(
    decision: DecisionModel,
    strategy: StrategyModel,
    plan: ActionPlan,
) -> DocumentBinding:
    return DocumentBinding(
        document_id="document-1",
        renderer_id="kdoc-dumb-renderer",
        renderer_version="1.0",
        template_id="submission",
        template_version="1.0",
        input_refs=(
            ArtifactRef("decision", decision.decision_id, decision.version, "d" * 64),
            ArtifactRef("strategy", strategy.strategy_id, strategy.version, "e" * 64),
            ArtifactRef("plan", plan.plan_id, plan.version, "f" * 64),
        ),
        source_digest="a" * 64,
        generated_at="2026-09-05T00:00:00Z",
        communication_target="external-recipient",
        approval_required=True,
        approval_ref="human-approval:1",
        status=DocumentStatus.APPROVED,
    )


def test_release_allows_only_complete_approved_chain() -> None:
    decision, strategy, plan = _selected_chain()
    binding = _approved_binding(decision, strategy, plan)

    result = authorize_cognitive_release(
        binding=binding,
        decision=decision,
        strategy=strategy,
        plan=plan,
    )

    assert result.allowed is True
    assert result.reasons == ()


def test_release_blocks_abstention_and_missing_plan() -> None:
    decision = DecisionModel(
        decision_id="decision-1",
        problem_id="problem-1",
        problem_version=1,
        evidence_assessment_refs=(),
        options=(),
        rationale="Evidence is insufficient.",
        status=DecisionStatus.ABSTAIN,
    )
    strategy = StrategyModel(
        strategy_id="strategy-1",
        decision_id=decision.decision_id,
        decision_version=decision.version,
        objectives=(),
        rationale="Decision abstained.",
        status=StrategyStatus.ABSTAIN,
    )
    binding = DocumentBinding(
        document_id="document-1",
        renderer_id="kdoc-dumb-renderer",
        renderer_version="1.0",
        template_id="review",
        template_version="1.0",
        input_refs=(
            ArtifactRef("decision", decision.decision_id, decision.version, "d" * 64),
            ArtifactRef("strategy", strategy.strategy_id, strategy.version, "e" * 64),
        ),
        source_digest="a" * 64,
        generated_at="2026-09-05T00:00:00Z",
        communication_target="local-human-review",
        approval_required=True,
        status=DocumentStatus.REVIEW_REQUIRED,
    )

    result = authorize_cognitive_release(
        binding=binding,
        decision=decision,
        strategy=strategy,
        plan=None,
    )

    assert result.allowed is False
    assert "decision_not_selected" in result.reasons
    assert "strategy_not_selected" in result.reasons
    assert "action_plan_missing" in result.reasons
    assert "document_not_approved" in result.reasons
    assert "human_approval_missing" in result.reasons


def test_release_blocks_chain_binding_mismatch() -> None:
    decision, strategy, plan = _selected_chain()
    binding = DocumentBinding(
        document_id="document-1",
        renderer_id="kdoc-dumb-renderer",
        renderer_version="1.0",
        template_id="submission",
        template_version="1.0",
        input_refs=(
            ArtifactRef("decision", decision.decision_id, decision.version, "d" * 64),
            ArtifactRef("strategy", strategy.strategy_id, strategy.version, "e" * 64),
            ArtifactRef("plan", "another-plan", plan.version, "f" * 64),
        ),
        source_digest="a" * 64,
        generated_at="2026-09-05T00:00:00Z",
        communication_target="external-recipient",
        approval_required=True,
        approval_ref="human-approval:1",
        status=DocumentStatus.APPROVED,
    )

    result = authorize_cognitive_release(
        binding=binding,
        decision=decision,
        strategy=strategy,
        plan=plan,
    )

    assert result.allowed is False
    assert "plan_binding_missing" in result.reasons
