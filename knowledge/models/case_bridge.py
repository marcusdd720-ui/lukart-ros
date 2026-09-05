"""KCB-1.0 controlled, auditable cross-case disclosure contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from knowledge.models.case_scope import (
    CaseReference,
    CaseScope,
    ReferenceAuthorization,
)


class BridgeStatus(StrEnum):
    PROPOSED = "proposed"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class DisclosureLevel(StrEnum):
    METADATA = "metadata"
    DERIVED_REFERENCE = "derived_reference"
    SOURCE_VERSION = "source_version"
    REDACTED = "redacted"
    FULL_CONTENT = "full_content"


@dataclass(frozen=True, slots=True)
class BridgeSubjectRef:
    subject_id: str
    subject_version: str
    reference_type: str
    source_ref: str
    provenance_ref: str
    integrity_sha256: str | None = None

    def __post_init__(self) -> None:
        required = (
            self.subject_id,
            self.subject_version,
            self.reference_type,
            self.source_ref,
            self.provenance_ref,
        )
        if any(not value.strip() for value in required):
            raise ValueError("BridgeSubjectRef required fields cannot be empty")


@dataclass(frozen=True, slots=True)
class BridgeCandidate:
    candidate_id: str
    source_case_id: str
    target_case_id: str
    subject_ids: tuple[str, ...]
    purpose_hint: str

    def __post_init__(self) -> None:
        required = (
            self.candidate_id,
            self.source_case_id,
            self.target_case_id,
            self.purpose_hint,
        )
        if any(not value.strip() for value in required):
            raise ValueError("BridgeCandidate required fields cannot be empty")
        if any(not value.strip() for value in self.subject_ids):
            raise ValueError("BridgeCandidate subject IDs cannot be empty")


@dataclass(frozen=True, slots=True)
class CaseBridge:
    bridge_id: str
    source_case_id: str
    target_case_id: str
    subject_refs: tuple[BridgeSubjectRef, ...]
    disclosure_level: DisclosureLevel
    purpose: str
    authorization_ref: str | None
    provenance_ref: str
    created_at: str
    status: BridgeStatus = BridgeStatus.PROPOSED
    human_review_required: bool = False
    human_approval_ref: str | None = None
    version: int = 1
    audit_lineage: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        required = (
            self.bridge_id,
            self.source_case_id,
            self.target_case_id,
            self.purpose,
            self.provenance_ref,
            self.created_at,
        )
        if any(not value.strip() for value in required):
            raise ValueError("CaseBridge required fields cannot be empty")
        if self.source_case_id == self.target_case_id:
            raise ValueError("CaseBridge requires different source and target Cases")
        if self.version < 1:
            raise ValueError("CaseBridge version must be >= 1")
        if not self.subject_refs:
            raise ValueError("CaseBridge requires at least one bounded subject reference")
        if any(not item.strip() for item in self.audit_lineage):
            raise ValueError("audit_lineage cannot contain empty values")
        active_states = {BridgeStatus.APPROVED, BridgeStatus.ACTIVE}
        if self.status in active_states:
            if self.authorization_ref is None or not self.authorization_ref.strip():
                raise ValueError("approved/active bridge requires authorization")
        if self.human_review_required and self.status in active_states:
            if self.human_approval_ref is None or not self.human_approval_ref.strip():
                raise ValueError("human-reviewed bridge requires human approval record")

    @property
    def consumable(self) -> bool:
        return self.status is BridgeStatus.ACTIVE

    def import_into(self, target: CaseScope, subject_id: str) -> CaseScope:
        if not self.consumable:
            raise ValueError("CaseBridge is not ACTIVE")
        if target.case_id != self.target_case_id:
            raise ValueError("CaseBridge target Case mismatch")
        subject = next((item for item in self.subject_refs if item.subject_id == subject_id), None)
        if subject is None:
            raise ValueError("subject is outside CaseBridge disclosure scope")
        reference = CaseReference(
            reference_id=f"bridge:{self.bridge_id}:{subject.subject_id}:{subject.subject_version}",
            reference_type=subject.reference_type,
            source_ref=subject.source_ref,
            reason=f"KCB bridge {self.bridge_id}: {self.purpose}",
            authorization=ReferenceAuthorization.AUTHORIZED,
            integrity_sha256=subject.integrity_sha256,
            cross_case_source=self.source_case_id,
        )
        return target.with_reference(reference)

    def revocation_requires_propagation(self, relied_upon: bool) -> bool:
        return self.status is BridgeStatus.REVOKED and relied_upon
