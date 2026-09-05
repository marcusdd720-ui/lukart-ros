import pytest

from knowledge.models.action_plan import (
    ActionPlan,
    DeadlineBinding,
    PlanStatus,
    PlanTask,
    TaskStatus,
)
from knowledge.models.case_model_projection import CaseModelProjection
from knowledge.models.case_scope import CaseScope, ReferenceSet, ScopePolicy
from knowledge.models.decision_model import DecisionModel, DecisionOption, DecisionStatus
from knowledge.models.problem_model import ProblemModel
from knowledge.models.strategy_model import StrategyApproach, StrategyModel, StrategyStatus


def _strategy() -> StrategyModel:
    scope = CaseScope(
        case_id="CASE-001",
        owner="client:001",
        scope_policy=ScopePolicy(),
        reference_set=ReferenceSet(),
    )
    problem = ProblemModel.build(
        "PROBLEM-1",
        CaseModelProjection.build(scope),
        "choose the next action",
    )
    option = DecisionOption("OPT-A", "collect evidence first")
    decision = DecisionModel.build(
        "DEC-1",
        problem,
        options=(option,),
        selected_option="OPT-A",
        rationale="material evidence is missing",
        authority="human:reviewer",
        status=DecisionStatus.SELECTED,
    )
    approach = StrategyApproach("APP-A", "collect then communicate")
    return StrategyModel.build(
        "STRAT-1",
        decision,
        objectives=("close evidence gap",),
        approach_options=(approach,),
        selected_approach="APP-A",
        rationale="collecting first reduces decision risk",
        status=StrategyStatus.SELECTED,
        version=2,
    )


def test_plan_keeps_evidence_and_document_tasks_separate() -> None:
    tasks = (
        PlanTask(
            "TASK-EVIDENCE",
            "obtain source document",
            "human:case-owner",
            expected_output="source-document",
            completion_criteria=("source received",),
        ),
        PlanTask(
            "TASK-DOCUMENT",
            "prepare final communication",
            "renderer",
            dependencies=("TASK-EVIDENCE",),
            expected_output="final-document",
            completion_criteria=("document rendered",),
        ),
    )
    plan = ActionPlan.build("PLAN-1", _strategy(), tasks=tasks)

    assert plan.tasks[1].dependencies == ("TASK-EVIDENCE",)
    assert plan.strategy_version == 2


def test_deadline_preserves_rule_and_source_identity() -> None:
    deadline = DeadlineBinding(
        deadline="2026-09-30",
        rule_ref="RULE-30D",
        source_ref="AUTHORITY-1",
    )
    task = PlanTask("TASK-1", "respond", "human:owner", deadline=deadline)

    assert task.deadline is not None
    assert task.deadline.rule_ref == "RULE-30D"
    assert task.deadline.source_ref == "AUTHORITY-1"


def test_ready_task_with_required_approval_needs_evidence() -> None:
    with pytest.raises(ValueError, match="approval evidence"):
        PlanTask(
            "TASK-1",
            "file document",
            "executor",
            approval_rule="human approval required",
            status=TaskStatus.READY,
        )


def test_completed_task_requires_completion_evidence() -> None:
    with pytest.raises(ValueError, match="completion evidence"):
        PlanTask(
            "TASK-1",
            "send document",
            "executor",
            completion_criteria=("delivery recorded",),
            status=TaskStatus.COMPLETED,
        )


def test_plan_rejects_dependency_cycle() -> None:
    tasks = (
        PlanTask("A", "first", "owner", dependencies=("B",)),
        PlanTask("B", "second", "owner", dependencies=("A",)),
    )

    with pytest.raises(ValueError, match="acyclic"):
        ActionPlan.build("PLAN-1", _strategy(), tasks=tasks)


def test_plan_requires_selected_strategy() -> None:
    selected = _strategy()
    proposed = StrategyModel(
        strategy_id=selected.strategy_id,
        decision_id=selected.decision_id,
        decision_version=selected.decision_version,
        objectives=selected.objectives,
        status=StrategyStatus.PROPOSED,
    )

    with pytest.raises(ValueError, match="SELECTED Strategy"):
        ActionPlan.build("PLAN-1", proposed)


def test_completed_plan_requires_completed_tasks() -> None:
    task = PlanTask("TASK-1", "work", "owner")

    with pytest.raises(ValueError, match="all tasks"):
        ActionPlan.build(
            "PLAN-1",
            _strategy(),
            tasks=(task,),
            status=PlanStatus.COMPLETED,
        )
