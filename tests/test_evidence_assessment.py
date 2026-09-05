import pytest

from knowledge.models.case_model_projection import CaseModelProjection
from knowledge.models.case_scope import CaseScope, ReferenceSet, ScopePolicy
from knowledge.models.evidence_assessment import AssessmentState, EvidenceAssessment
from knowledge.models.problem_model import ProblemModel


def _problem() -> tuple[ProblemModel, CaseModelProjection]:
    scope = CaseScope(
        case_id="CASE-001",
        owner="client:001",
        scope_policy=ScopePolicy(),
        reference_set=ReferenceSet(),
    )
    case_model = CaseModelProjection.build(scope, version=3)
    problem = ProblemModel.build(
        "PROBLEM-1",
        case_model,
        "determine whether proposition PROP-1 is sufficiently established",
        version=2,
    )
    return problem, case_model


def test_assessment_binds_exact_problem_version() -> None:
    problem, _ = _problem()

    assessment = EvidenceAssessment.build(
        "ASSESS-1",
        problem,
        "PROP-1",
        provenance_state=AssessmentState.SATISFIED,
    )

    assert assessment.problem_id == "PROBLEM-1"
    assert assessment.problem_version == 2


def test_support_and_contradiction_are_preserved_together() -> None:
    problem, _ = _problem()

    assessment = EvidenceAssessment.build(
        "ASSESS-1",
        problem,
        "PROP-1",
        support_refs=("EV-1",),
        contradiction_refs=("EV-2",),
        completeness_state=AssessmentState.PARTIAL,
        strength_state=AssessmentState.CONTRADICTED,
    )

    assert assessment.support_refs == ("EV-1",)
    assert assessment.contradiction_refs == ("EV-2",)
    assert assessment.strength_state is AssessmentState.CONTRADICTED


def test_missing_evidence_can_be_material_without_mutating_problem() -> None:
    problem, case_model = _problem()

    assessment = EvidenceAssessment.build(
        "ASSESS-1",
        problem,
        "PROP-1",
        completeness_state=AssessmentState.INSUFFICIENT,
        missing_evidence=("signed contract", "bank statement"),
    )

    assert assessment.missing_evidence == ("signed contract", "bank statement")
    assert problem.version == 2
    assert case_model.object_refs == ()


def test_unknown_provenance_is_valid_explicit_state() -> None:
    problem, _ = _problem()

    assessment = EvidenceAssessment.build("ASSESS-1", problem, "PROP-1")

    assert assessment.provenance_state is AssessmentState.UNKNOWN


def test_blank_proposition_is_rejected() -> None:
    problem, _ = _problem()

    with pytest.raises(ValueError, match="identity fields"):
        EvidenceAssessment.build("ASSESS-1", problem, "   ")


def test_blank_burden_ref_is_rejected() -> None:
    problem, _ = _problem()

    with pytest.raises(ValueError, match="burden_ref"):
        EvidenceAssessment.build("ASSESS-1", problem, "PROP-1", burden_ref="   ")
