from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

import pytest

import core.cirp.intake as intake
from core.case_ledger.contracts import CaseId
from core.cirp.contracts import (
    AssessmentStatus,
    CIRPContractError,
    CIRPRunIdentity,
    DocumentAssessment,
    DocumentKind,
    ProceduralAssessment,
    ProceduralStage,
    ServiceAssessment,
    ServiceStatus,
)
from core.cirp.engine import CIRPRunRequest, canonical_rule_pack_set_digest
from core.p3.contracts import content_digest
from core.private_case_runtime_bridge_v1 import (
    VerifiedLocalDocumentV1,
    VerifiedLocalEvidenceProjectionV1,
)
from core.private_evidence_v1 import PrivateEvidenceStore

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)
SOURCE_A = "sha256:" + "a" * 64
DERIVED_A = "sha256:" + "b" * 64
SOURCE_B = "sha256:" + "c" * 64
DERIVED_B = "sha256:" + "d" * 64
CONFIG = "e" * 64


def _document(
    document_id: str,
    source: str,
    derived: str,
) -> VerifiedLocalDocumentV1:
    return VerifiedLocalDocumentV1(
        document_id=document_id,
        evidence_id=source,
        manifest_digest="sha256:" + "1" * 64,
        receipt_digest="sha256:" + "2" * 64,
        derived_evidence_id=derived,
        derived_manifest_digest="sha256:" + "3" * 64,
        derived_receipt_digest="sha256:" + "4" * 64,
        derivation_identity="sha256:" + "5" * 64,
        derivation_receipt_digest="sha256:" + "6" * 64,
        derivation_replay_class="DETERMINISTIC",
        case_scope_digest="sha256:" + "7" * 64,
    )


def _projection() -> VerifiedLocalEvidenceProjectionV1:
    return VerifiedLocalEvidenceProjectionV1(
        schema="lukart.private-case-runtime-projection.v1",
        case_id="CASE-SYNTHETIC-P02",
        case_scope_digest="sha256:" + "7" * 64,
        documents=(
            _document("DOC-001", SOURCE_A, DERIVED_A),
            _document("DOC-002", SOURCE_B, DERIVED_B),
        ),
    )


def _draft_request() -> CIRPRunRequest:
    identity = CIRPRunIdentity(
        case_id=CaseId("case:draft:p02"),
        input_evidence_ids=("evidence:draft:p02",),
        input_event_ids=(),
        rule_pack_ids=(),
        rule_pack_digest=canonical_rule_pack_set_digest(()),
        policy_identity="policy:draft:p02",
        runtime_identity="runtime:draft:p02",
        model_identity=None,
        evaluation_time=NOW,
        configuration_digest=content_digest({"draft": "p02"}),
    )
    return CIRPRunRequest(
        run_id="cirp-run:p02:synthetic",
        run_identity=identity,
        document_assessment=DocumentAssessment(
            document_id="DOC-001",
            source_evidence_id=SOURCE_A,
            document_kind=DocumentKind.NOTICE,
            issuer="Synthetic Authority",
            recipient="Synthetic Party",
            document_date=None,
            case_reference="SYNTHETIC-P02",
            subject="Synthetic private intake",
            operative_content=("Synthetic content.",),
            requested_actions=(),
            stated_deadlines=(),
            classification_status=AssessmentStatus.VERIFIED,
            evidence_refs=(SOURCE_A, DERIVED_A),
            open_questions=(),
        ),
        procedural_assessment=ProceduralAssessment(
            jurisdiction="PL",
            procedure_family="synthetic_p02",
            procedural_stage=ProceduralStage.INFORMATION_ONLY,
            issuing_authority="Synthetic Authority",
            competent_authority="Synthetic Authority",
            review_authority=None,
            filing_authority=None,
            filing_via=None,
            procedural_subject="Synthetic private intake",
            available_action_required=False,
            status=AssessmentStatus.VERIFIED,
            supporting_rules=(),
            evidence_refs=(DERIVED_A,),
            unresolved=(),
        ),
        service_assessment=ServiceAssessment(
            service_required=False,
            service_method=None,
            service_date=None,
            service_time=None,
            evidence_refs=(SOURCE_A,),
            source_status=ServiceStatus.NOT_APPLICABLE,
            conflicting_dates=(),
            assessment_status=ServiceStatus.NOT_APPLICABLE,
        ),
        rule_packs=(),
        deadline_rules=(),
        deadline_calendars=(),
        remedy_rules=(),
        deadline_evaluations=(),
        remedy_evaluations=(),
        evidence_requirements=(),
        strategy_options=(),
        available_evidence_ids=(SOURCE_A, DERIVED_A),
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    request: CIRPRunRequest | None = None,
    *,
    document_ids: tuple[str, ...] = ("DOC-001",),
) -> CIRPRunRequest:
    projection = _projection()
    monkeypatch.setattr(intake, "load_verified_projection", lambda store: projection)
    store = cast(PrivateEvidenceStore, object())
    return intake.bind_private_case_request(
        store,
        request or _draft_request(),
        document_ids=document_ids,
        policy_identity="policy:cirp-p02:synthetic:v1",
        runtime_identity="runtime:cirp-p02:private-intake:v1",
        evaluation_time=NOW,
        source_configuration_digest=CONFIG,
    )


def test_private_intake_replaces_draft_identity_with_verified_selected_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bound = _bind(monkeypatch)

    assert bound.run_identity.case_id == CaseId("CASE-SYNTHETIC-P02")
    assert bound.run_identity.input_evidence_ids == (SOURCE_A, DERIVED_A)
    assert bound.available_evidence_ids == (SOURCE_A, DERIVED_A)
    assert bound.run_identity.input_event_ids == ()
    assert bound.run_identity.policy_identity == "policy:cirp-p02:synthetic:v1"
    assert bound.run_identity.runtime_identity == "runtime:cirp-p02:private-intake:v1"
    assert bound.run_identity.configuration_digest != CONFIG
    assert (
        bound.run_identity.configuration_digest
        != _draft_request().run_identity.configuration_digest
    )


def test_private_intake_binding_is_deterministic_for_same_verified_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _bind(monkeypatch)
    second = _bind(monkeypatch)

    assert first.run_identity.digest() == second.run_identity.digest()


def test_private_intake_document_selection_is_order_invariant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _bind(monkeypatch, document_ids=("DOC-001", "DOC-002"))
    second = _bind(monkeypatch, document_ids=("DOC-002", "DOC-001"))

    assert first.run_identity.digest() == second.run_identity.digest()
    assert first.run_identity.input_evidence_ids == (
        SOURCE_A,
        DERIVED_A,
        SOURCE_B,
        DERIVED_B,
    )


def test_private_intake_rejects_available_evidence_outside_selected_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = replace(
        _draft_request(),
        available_evidence_ids=(SOURCE_A, DERIVED_A, SOURCE_B),
    )

    with pytest.raises(CIRPContractError, match="outside selected private intake"):
        _bind(monkeypatch, request)


def test_private_intake_rejects_semantic_reference_outside_selected_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _draft_request()
    assessment = replace(
        request.procedural_assessment,
        evidence_refs=(DERIVED_A, DERIVED_B),
    )

    with pytest.raises(CIRPContractError, match="semantic inputs"):
        _bind(monkeypatch, replace(request, procedural_assessment=assessment))


def test_private_intake_rejects_document_source_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _draft_request()
    assessment = replace(request.document_assessment, source_evidence_id=SOURCE_B)

    with pytest.raises(CIRPContractError, match="source_evidence_id"):
        _bind(monkeypatch, replace(request, document_assessment=assessment))


def test_private_intake_rejects_unselected_or_unknown_document_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(CIRPContractError, match="not selected"):
        _bind(monkeypatch, document_ids=("DOC-002",))

    with pytest.raises(CIRPContractError, match="unknown document ids"):
        _bind(monkeypatch, document_ids=("DOC-999",))
