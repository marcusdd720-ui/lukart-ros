"""Fail-closed bridge from verified private evidence into the CIRP runtime.

The adapter never reads plaintext evidence and never writes Canonical Case Ledger state.
It binds an explicitly selected subset of an already verified CASE-OPS projection to a
fresh CIRP run identity, preserving the Canonical Case Ledger as the sole writable case
history authority.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from core.case_ledger.contracts import CaseId, LedgerEvent
from core.cirp.contracts import CIRPContractError, CIRPRunIdentity
from core.cirp.engine import CIRPRunRequest, canonical_rule_pack_set_digest
from core.p3.contracts import P3ContractError, content_digest, require_hex_digest
from core.private_case_runtime_bridge_v1 import (
    VerifiedLocalDocumentV1,
    VerifiedLocalEvidenceProjectionV1,
    load_verified_projection,
)
from core.private_evidence_v1 import PrivateEvidenceStore

PRIVATE_CIRP_INTAKE_SCHEMA_V1 = "lukart.cirp.private-intake-binding.v1"


def _require_unique_nonblank(values: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        if not value or value != value.strip():
            raise CIRPContractError(f"{field_name} must contain canonical nonblank values")
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise CIRPContractError(f"{field_name} cannot contain control characters")
        normalized.append(value)
    if len(normalized) != len(set(normalized)):
        raise CIRPContractError(f"{field_name} cannot contain duplicates")
    return tuple(normalized)


def _selected_documents(
    projection: VerifiedLocalEvidenceProjectionV1,
    document_ids: tuple[str, ...],
) -> tuple[VerifiedLocalDocumentV1, ...]:
    selected_ids = _require_unique_nonblank(document_ids, field_name="document_ids")
    if not selected_ids:
        raise CIRPContractError("private CIRP intake requires at least one selected document")
    by_id = {document.document_id: document for document in projection.documents}
    if len(by_id) != len(projection.documents):
        raise CIRPContractError("verified private projection contains duplicate document ids")
    missing = tuple(document_id for document_id in selected_ids if document_id not in by_id)
    if missing:
        raise CIRPContractError(
            "private CIRP intake references unknown document ids: " + ", ".join(missing)
        )
    return tuple(by_id[document_id] for document_id in sorted(selected_ids))


def _projection_evidence_ids(
    documents: tuple[VerifiedLocalDocumentV1, ...],
) -> tuple[str, ...]:
    evidence_ids: list[str] = []
    for document in documents:
        evidence_ids.extend((document.evidence_id, document.derived_evidence_id))
    return tuple(dict.fromkeys(evidence_ids))


def _event_ids(events: tuple[LedgerEvent, ...], *, case_id: str) -> tuple[str, ...]:
    ordered = sorted(events, key=lambda event: event.case_sequence)
    sequences = tuple(event.case_sequence for event in ordered)
    if len(sequences) != len(set(sequences)):
        raise CIRPContractError("private CIRP intake events cannot reuse case_sequence")
    result: list[str] = []
    for event in ordered:
        if event.case_id.value != case_id:
            raise CIRPContractError("private CIRP intake event belongs to another case")
        event.verify()
        result.append(str(event.event_id))
    if len(result) != len(set(result)):
        raise CIRPContractError("private CIRP intake events cannot contain duplicates")
    return tuple(result)


def _binding_configuration_digest(
    *,
    projection: VerifiedLocalEvidenceProjectionV1,
    selected_documents: tuple[VerifiedLocalDocumentV1, ...],
    source_configuration_digest: str,
) -> str:
    try:
        normalized_configuration = require_hex_digest(
            source_configuration_digest,
            field_name="source_configuration_digest",
        )
    except P3ContractError as exc:
        raise CIRPContractError(str(exc)) from exc
    return content_digest(
        {
            "schema": PRIVATE_CIRP_INTAKE_SCHEMA_V1,
            "private_projection_subset": {
                "schema": projection.schema,
                "case_id": projection.case_id,
                "case_scope_digest": projection.case_scope_digest,
                "documents": [item.canonical_dict() for item in selected_documents],
            },
            "source_configuration_digest": normalized_configuration,
        }
    )


def bind_private_case_request(
    store: PrivateEvidenceStore,
    request: CIRPRunRequest,
    *,
    document_ids: tuple[str, ...],
    policy_identity: str,
    runtime_identity: str,
    evaluation_time: datetime,
    source_configuration_digest: str,
    input_events: tuple[LedgerEvent, ...] = (),
    model_identity: str | None = None,
) -> CIRPRunRequest:
    """Bind one CIRP request to verified local evidence without exposing plaintext.

    ``request`` supplies semantic CIRP inputs and executable rule semantics. Its incoming
    run identity is deliberately replaced. Evidence accepted by the resulting request is
    restricted to the explicitly selected, derivation-verified private documents.
    """
    projection = load_verified_projection(store)
    documents = _selected_documents(projection, document_ids)
    evidence_ids = _projection_evidence_ids(documents)
    allowed = set(evidence_ids)

    source_document = next(
        (item for item in documents if item.document_id == request.document_assessment.document_id),
        None,
    )
    if source_document is None:
        raise CIRPContractError(
            "DocumentAssessment document_id is not selected by private CIRP intake"
        )
    if request.document_assessment.source_evidence_id != source_document.evidence_id:
        raise CIRPContractError(
            "DocumentAssessment source_evidence_id does not match verified private source"
        )

    available = set(request.available_evidence_ids)
    if not available.issubset(allowed):
        raise CIRPContractError(
            "available_evidence_ids contain evidence outside selected private intake"
        )

    referenced: set[str] = set(request.document_assessment.evidence_refs)
    referenced.update(request.procedural_assessment.evidence_refs)
    referenced.update(request.service_assessment.evidence_refs)
    for requirement in request.evidence_requirements:
        referenced.update(requirement.evidence_refs)
    if request.consolidation is not None:
        referenced.update(request.consolidation.evidence_refs)
    for evaluation in request.deadline_evaluations:
        if evaluation.trigger_evidence is not None:
            referenced.add(evaluation.trigger_evidence)
    if not referenced.issubset(allowed):
        raise CIRPContractError(
            "CIRP semantic inputs reference evidence outside selected private intake"
        )

    rule_pack_ids = tuple(pack.pack_id for pack in request.rule_packs)
    identity = CIRPRunIdentity(
        case_id=CaseId(projection.case_id),
        input_evidence_ids=evidence_ids,
        input_event_ids=_event_ids(input_events, case_id=projection.case_id),
        rule_pack_ids=rule_pack_ids,
        rule_pack_digest=canonical_rule_pack_set_digest(request.rule_packs),
        policy_identity=policy_identity,
        runtime_identity=runtime_identity,
        model_identity=model_identity,
        evaluation_time=evaluation_time,
        configuration_digest=_binding_configuration_digest(
            projection=projection,
            selected_documents=documents,
            source_configuration_digest=source_configuration_digest,
        ),
    )
    return replace(
        request,
        run_identity=identity,
        available_evidence_ids=evidence_ids,
    )
