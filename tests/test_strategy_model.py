import pytest

from knowledge.models.case_model_projection import CaseModelProjection
from knowledge.models.case_scope import CaseScope, ReferenceSet, ScopePolicy
from knowledge.models.decision_model import DecisionModel, DecisionOption, DecisionStatus
from knowledge.models.problem_model import ProblemModel
from knowledge.models.strategy_model import StrategyApproach, StrategyModel, StrategyStatus


def _problem() -> ProblemModel:
    scope = CaseScope(
        case_id="CASE-001",
        owner="client:001",
        scope_policy=ScopePolicy(),
        reference_set=ReferenceSet(),
    )
    return ProblemModel.build(
        "PROBLEM-1",
        CaseModelProjection.build(scope, version=2),
        "choose the next action",
        version=3,
    )


def _selected_decision() -> DecisionModel:
    option = DecisionOption("OPT-A", "collect missing evidence first")
    return DecisionModel.build(
        "DEC-1",
        _problem(),
        options=(option,),
        selected_option="OPT-A",
        rationale="the evidence gap is material",
        authority="human:reviewer",
        status=DecisionStatus.SELECTED,
        version=2,
    )


def test_strategy_compares_approaches_without_mutating_decision() -> None:
    decision = _selected_decision()
    approaches = (
        StrategyApproach("APP-A", "collect evidence before filing"),
        StrategyApproach("APP-B", "seek human review before action"),
    )
    strategy = StrategyModel.build(
        "STRAT-1",
        decision,
        objectives=("close the evidence gap",),
        approach_options=approaches,
        selected_approach="APP-A",
        risk_controls=("stop if source authenticity cannot be verified",),
        fallback_paths=("APP-B",),
        rationale="APP-A addresses the blocking evidence gap directly",
        status=StrategyStatus.SELECTED,
    )

    assert strategy.decision_id == decision.decision_id
    assert strategy.decision_version == 2
    assert strategy.selected_approach == "APP-A"
    assert decision.selected_option == "OPT-A"


def test_missing_evidence_action_does_not_promote_evidence_state() -> None:
    strategy = StrategyModel.build(
        "STRAT-1",
        _selected_decision(),
        evidence_actions=("obtain original service record",),
    )

    assert strategy.evidence_actions == ("obtain original service record",)


def test_proposed_decision_cannot_produce_strategy() -> None:
    decision = DecisionModel.build("DEC-1", _problem())

    with pytest.raises(ValueError, match="authorized"):
        StrategyModel.build("STRAT-1", decision)


def test_abstain_decision_cannot_select_strategy() -> None:
    decision = DecisionModel.build(
        "DEC-1",
        _problem(),
        rationale="material evidence is missing",
        status=DecisionStatus.ABSTAIN,
    )
    approach = StrategyApproach("APP-A", "proceed anyway")

    with pytest.raises(ValueError, match="ABSTAIN Decision"):
        StrategyModel.build(
            "STRAT-1",
            decision,
            objectives=("proceed",),
            approach_options=(approach,),
            selected_approach="APP-A",
            rationale="unsafe override",
            status=StrategyStatus.SELECTED,
        )


def test_selected_strategy_requires_rationale() -> None:
    approach = StrategyApproach("APP-A", "collect evidence")

    with pytest.raises(ValueError, match="rationale"):
        StrategyModel.build(
            "STRAT-1",
            _selected_decision(),
            objectives=("close evidence gap",),
            approach_options=(approach,),
            selected_approach="APP-A",
            status=StrategyStatus.SELECTED,
        )
