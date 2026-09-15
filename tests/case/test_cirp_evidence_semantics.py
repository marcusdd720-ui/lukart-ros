from datetime import date

import pytest

from core.cirp.contracts import (
    AssessmentStatus,
    CIRPContractError,
    DocumentAssessment,
    DocumentKind,
    EvidenceCategory,
    EvidenceImportance,
    EvidenceRequirement,
    EvidenceRequirementStatus,
    ServiceAssessment,
    ServiceStatus,
)


def _document(*, status: AssessmentStatus, evidence_refs: tuple[str, ...]):
    return DocumentAssessment(
        document_id="DOC-TEST-1",
        source_evidence_id="EVIDENCE-SOURCE-1",
        document_kind=DocumentKind.NOTICE,
        issuer="Synthetic Authority",
        recipient="Synthetic Recipient",
        document_date=date(2026, 9, 1),
        case_reference="SYNTHETIC-CASE-1",
        subject="Synthetic notice",
        operative_content=("Synthetic operative content",),
        requested_actions=(),
        stated_deadlines=(),
        classification_status=status,
        evidence_refs=evidence_refs,
        open_questions=(),
    )


def test_verified_document_classification_requires_evidence_refs() -> None:
    with pytest.raises(CIRPContractError, match="requires evidence_refs"):
        _document(status=AssessmentStatus.VERIFIED, evidence_refs=())


def test_provisional_document_does_not_silently_upgrade_to_verified() -> None:
    assessment = _document(
        status=AssessmentStatus.PROVISIONAL,
        evidence_refs=("EVIDENCE-SOURCE-1",),
    )
    assert assessment.classification_status is AssessmentStatus.PROVISIONAL


def test_present_evidence_requirement_requires_evidence_refs() -> None:
    with pytest.raises(
        CIRPContractError,
        match="PRESENT evidence requirement requires evidence_refs",
    ):
        EvidenceRequirement(
            requirement_id="REQ-TEST-1",
            description="Synthetic supporting document",
            category=EvidenceCategory.MERITS_CRITICAL,
            importance=EvidenceImportance.CRITICAL,
            required_for=("REMEDY-TEST-1",),
            expected_evidence_kind="DOCUMENT",
            status=EvidenceRequirementStatus.PRESENT,
            evidence_refs=(),
        )


def test_missing_evidence_requirement_cannot_carry_evidence_refs() -> None:
    with pytest.raises(
        CIRPContractError,
        match="MISSING evidence requirement cannot contain evidence_refs",
    ):
        EvidenceRequirement(
            requirement_id="REQ-TEST-2",
            description="Synthetic missing document",
            category=EvidenceCategory.MERITS_CRITICAL,
            importance=EvidenceImportance.CRITICAL,
            required_for=("REMEDY-TEST-1",),
            expected_evidence_kind="DOCUMENT",
            status=EvidenceRequirementStatus.MISSING,
            evidence_refs=("EVIDENCE-IMPOSSIBLE",),
        )


def test_verified_service_requires_date_and_evidence() -> None:
    with pytest.raises(CIRPContractError, match="VERIFIED service requires date and evidence"):
        ServiceAssessment(
            service_required=True,
            service_method="SYNTHETIC_DELIVERY",
            service_date=date(2026, 9, 4),
            service_time=None,
            evidence_refs=(),
            source_status=ServiceStatus.USER_REPORTED,
            conflicting_dates=(),
            assessment_status=ServiceStatus.VERIFIED,
        )


def test_conflicting_service_cannot_be_collapsed_to_one_settled_date() -> None:
    assessment = ServiceAssessment(
        service_required=True,
        service_method="SYNTHETIC_DELIVERY",
        service_date=None,
        service_time=None,
        evidence_refs=("EVIDENCE-A", "EVIDENCE-B"),
        source_status=ServiceStatus.CONFLICTING,
        conflicting_dates=(date(2026, 9, 4), date(2026, 9, 5)),
        assessment_status=ServiceStatus.CONFLICTING,
    )
    assert assessment.assessment_status is ServiceStatus.CONFLICTING
    assert assessment.service_date is None
