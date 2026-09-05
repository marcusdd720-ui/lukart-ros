import pytest

from knowledge.models.case_model_projection import CaseModelProjection
from knowledge.models.case_scope import CaseScope, ReferenceSet, ScopePolicy
from knowledge.models.problem_model import (
    EvidenceNeed,
    ProblemModel,
    ProblemStatus,
    RiskDimension,
)


def _case_model() -> CaseModelProjection:
    scope = CaseScope(
        case_id="CASE-001",
        owner="client:001",
        scope_policy=ScopePolicy(),
        reference_set=ReferenceSet(),
        version=4,
    )
    return CaseModelProjection.build(scope, version=2)


def test_multiple_problems_can_share_same_case_model_without_mutation() -> None:
    case_model = _case_model()

    liability = ProblemModel.build(
        "PROBLEM-LIABILITY",
        case_model,
        "determine whether the obligation exists",
        desired_outcomes=("obligation rejected",),
    )
    limitation = ProblemModel.build(
        "PROBLEM-LIMITATION",
        case_model,
        "determine whether the claim is time-barred",
        desired_outcomes=("limitation defense established",),
    )

    assert liability.case_id == limitation.case_id == "CASE-001"
    assert liability.case_model_version == limitation.case_model_version == 2
    assert liability.decision_need != limitation.decision_need
    assert case_model.version == 2


def test_problem_requires_explicit_decision_need() -> None:
    with pytest.raises(ValueError, match="decision_need"):
        ProblemModel.build("PROBLEM-1", _case_model(), "   ")


def test_problem_preserves_evidence_needs_open_questions_and_risk() -> None:
    need = EvidenceNeed(
        proposition_ref="PROP-1",
        burden_ref="RULE-1",
        missing_categories=("bank statement",),
        blocking=True,
    )
    risk = RiskDimension("procedural", "deadline may block the preferred remedy")

    problem = ProblemModel.build(
        "PROBLEM-1",
        _case_model(),
        "select available remedy",
        evidence_needs=(need,),
        open_questions=("when was notice effectively served?",),
        risk_dimensions=(risk,),
        success_criteria=("at least one admissible remedy remains available",),
        status=ProblemStatus.ACTIVE,
    )

    assert problem.evidence_needs == (need,)
    assert problem.open_questions == ("when was notice effectively served?",)
    assert problem.risk_dimensions == (risk,)
    assert problem.status is ProblemStatus.ACTIVE


def test_desired_outcome_is_not_case_fact() -> None:
    case_model = _case_model()
    problem = ProblemModel.build(
        "PROBLEM-1",
        case_model,
        "determine liability",
        desired_outcomes=("no liability",),
    )

    assert problem.desired_outcomes == ("no liability",)
    assert case_model.object_refs == ()


def test_blank_evidence_need_is_rejected() -> None:
    with pytest.raises(ValueError, match="proposition_ref"):
        EvidenceNeed("   ")
