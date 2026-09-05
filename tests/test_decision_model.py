import pytest

from knowledge.models.case_model_projection import CaseModelProjection
from knowledge.models.case_scope import CaseScope, ReferenceSet, ScopePolicy
from knowledge.models.decision_model import DecisionModel, DecisionOption, DecisionStatus
from knowledge.models.evidence_assessment import EvidenceAssessment
from knowledge.models.problem_model import ProblemModel


def _problem() -> ProblemModel:
    scope = CaseScope(
        case_id="CASE-001",
        owner="client:001",
        scope_policy=ScopePolicy(),
        reference_set=ReferenceSet(),
    )
    case_model = CaseModelProjection.build(scope, version=2)
    return ProblemModel.build("PROBLEM-1", case_model, "choose the next action", version=3)


def test_selected_decision_preserves_options_and_rejections() -> None:
    problem = _problem()
    options = (
        DecisionOption("OPT-A", "collect more evidence"),
        DecisionOption("OPT-B", "proceed with current evidence"),
    )

    decision = DecisionModel.build(
        "DEC-1",
        problem,
        options=options,
        rejected_options=("OPT-B",),
        selected_option="OPT-A",
        rationale="the identified evidence gap blocks a safe merits decision",
        authority="human:reviewer",
        status=DecisionStatus.SELECTED,
    )

    assert decision.selected_option == "OPT-A"
    assert decision.rejected_options == ("OPT-B",)
    assert decision.problem_version == 3


def test_abstain_is_valid_with_explicit_rationale() -> None:
    decision = DecisionModel.build(
        "DEC-1",
        _problem(),
        rationale="material evidence is missing",
        status=DecisionStatus.ABSTAIN,
    )

    assert decision.status is DecisionStatus.ABSTAIN
    assert decision.selected_option is None


def test_selected_decision_requires_authority() -> None:
    option = DecisionOption("OPT-A", "proceed")

    with pytest.raises(ValueError, match="authority"):
        DecisionModel.build(
            "DEC-1",
            _problem(),
            options=(option,),
            selected_option="OPT-A",
            rationale="evidence is sufficient",
            status=DecisionStatus.SELECTED,
        )


def test_selected_option_must_exist() -> None:
    with pytest.raises(ValueError, match="available option"):
        DecisionModel.build(
            "DEC-1",
            _problem(),
            selected_option="OPT-X",
        )


def test_evidence_assessment_must_match_problem_version() -> None:
    problem = _problem()
    assessment = EvidenceAssessment.build("ASSESS-1", problem, "PROP-1")
    newer_problem = ProblemModel.build(
        "PROBLEM-1",
        CaseModelProjection(
            case_id="CASE-001",
            scope_version=1,
            object_refs=(),
            relation_refs=(),
            source_reference_ids=(),
            version=2,
        ),
        "choose the next action",
        version=4,
    )

    with pytest.raises(ValueError, match="another Problem version"):
        DecisionModel.build(
            "DEC-1",
            newer_problem,
            evidence_assessments=(assessment,),
        )


def test_assumptions_remain_explicit() -> None:
    decision = DecisionModel.build(
        "DEC-1",
        _problem(),
        assumptions=("service date remains unverified",),
    )

    assert decision.assumptions == ("service date remains unverified",)
