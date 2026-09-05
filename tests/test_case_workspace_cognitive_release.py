from __future__ import annotations

from pathlib import Path

import pytest

from knowledge.graph import KnowledgeGraph
from knowledge.models.action_plan import ActionPlan, PlanStatus
from knowledge.models.case import Case
from knowledge.models.case_workspace import CaseWorkspace
from knowledge.models.decision_model import DecisionModel, DecisionOption, DecisionStatus
from knowledge.models.document_binding import ArtifactRef, DocumentBinding, DocumentStatus
from knowledge.models.strategy_model import StrategyApproach, StrategyModel, StrategyStatus


def _workspace(tmp_path: Path) -> CaseWorkspace:
    return CaseWorkspace(
        key="CASE-1",
        graph_case_id="case:CASE-1",
        case=Case(id="CASE-1", title="", working_title="Case One"),
        graph=KnowledgeGraph(),
        root=tmp_path,
    )


def _approved_chain() -> tuple[DecisionModel, StrategyModel, ActionPlan, DocumentBinding]:
    decision = DecisionModel(
        decision_id="decision-1",
        problem_id="problem-1",
        problem_version=1,
        evidence_assessment_refs=("evidence-1",),
        options=(DecisionOption("file", "File the approved submission."),),
        selected_option="file",
        rationale="Verified evidence supports filing.",
        authority="human:reviewer-1",
        status=DecisionStatus.SELECTED,
    )
    strategy = StrategyModel(
        strategy_id="strategy-1",
        decision_id=decision.decision_id,
        decision_version=decision.version,
        objectives=("Execute the authorized filing.",),
        approach_options=(StrategyApproach("submit", "Prepare and submit."),),
        selected_approach="submit",
        rationale="Authorized decision selected this approach.",
        status=StrategyStatus.SELECTED,
    )
    plan = ActionPlan(
        plan_id="plan-1",
        strategy_id=strategy.strategy_id,
        strategy_version=strategy.version,
        tasks=(),
        status=PlanStatus.ACTIVE,
    )
    binding = DocumentBinding(
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
    return decision, strategy, plan, binding


def test_unenforced_workspace_is_preparation_only_and_blocks_outbound(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)

    assert workspace.cognitive_release_blockers() == ()
    with pytest.raises(PermissionError, match="cognitive_release_not_enforced"):
        workspace.sync_outbound()


def test_enforced_workspace_blocks_outbound_and_release_without_chain(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    workspace.cognitive_release_enforced = True

    blockers = workspace.cognitive_release_blockers()
    assert "release_binding_missing" in blockers
    assert "release_decision_missing" in blockers
    assert "release_strategy_missing" in blockers

    with pytest.raises(PermissionError, match="Cognitive release blocked"):
        workspace.sync_outbound()

    assert workspace.run_stage("OUTBOUND") == 1
    assert workspace.run_stage("RELEASE") == 1


def test_approved_bound_chain_unlocks_workspace_release_boundary(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    decision, strategy, plan, binding = _approved_chain()
    workspace.bind_cognitive_release(
        binding=binding,
        decision=decision,
        strategy=strategy,
        plan=plan,
    )

    assert workspace.cognitive_release_enforced is True
    assert workspace.cognitive_release_blockers() == ()
    assert workspace.sync_outbound() == []