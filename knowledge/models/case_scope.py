"""Backward-compatible runtime contract for KCS-1.2 Case boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from enum import StrEnum

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class CaseOperationalState(StrEnum):
    INTAKE = "intake"
    COLLECTING = "collecting"
    ANALYSIS = "analysis"
    DECISION_PREPARATION = "decision_preparation"
    ACTION = "action"
    MONITORING = "monitoring"
    CLOSED = "closed"
    ARCHIVED = "archived"


class CaseEpistemicState(StrEnum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    MATERIAL_CONTRADICTION = "material_contradiction"
    OPEN_QUESTIONS = "open_questions"
    ANALYTICALLY_READY = "analytically_ready"
    DECISION_READY = "decision_ready"


class ReferenceAuthorization(StrEnum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    REJECTED = "rejected"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class ScopePolicy:
    """Explicit bounded admission policy for one Case."""

    allowed_reference_types: frozenset[str] = field(default_factory=frozenset)
    denied_reference_types: frozenset[str] = field(default_factory=frozenset)
    permitted_source_classes: frozenset[str] = field(default_factory=frozenset)
    subject_bounds: frozenset[str] = field(default_factory=frozenset)
    temporal_bounds: tuple[str | None, str | None] = (None, None)
    cross_case_allowed: bool = False
    require_authorization: bool = True
    version: int = 1

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("ScopePolicy.version must be >= 1")
        overlap = self.allowed_reference_types & self.denied_reference_types
        if overlap:
            raise ValueError(f"reference type cannot be both allowed and denied: {sorted(overlap)}")

    def admits_type(self, reference_type: str) -> bool:
        normalized = reference_type.strip()
        if not normalized or normalized in self.denied_reference_types:
            return False
        return not self.allowed_reference_types or normalized in self.allowed_reference_types


@dataclass(frozen=True, slots=True)
class CaseReference:
    """Bounded reference available to a Case; it does not copy source ownership."""

    reference_id: str
    reference_type: str
    source_ref: str
    reason: str
    authorization: ReferenceAuthorization = ReferenceAuthorization.PENDING
    integrity_sha256: str | None = None
    cross_case_source: str | None = None

    def __post_init__(self) -> None:
        if not self.reference_id.strip():
            raise ValueError("CaseReference.reference_id cannot be empty")
        if not self.reference_type.strip():
            raise ValueError("CaseReference.reference_type cannot be empty")
        if not self.source_ref.strip():
            raise ValueError("CaseReference.source_ref cannot be empty")
        if not self.reason.strip():
            raise ValueError("CaseReference.reason cannot be empty")
        if self.integrity_sha256 is not None and not _SHA256_RE.fullmatch(self.integrity_sha256):
            raise ValueError("CaseReference.integrity_sha256 must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class ReferenceSet:
    references: tuple[CaseReference, ...] = ()

    def __post_init__(self) -> None:
        ids = [item.reference_id for item in self.references]
        if len(ids) != len(set(ids)):
            raise ValueError("ReferenceSet reference_id values must be unique")

    def get(self, reference_id: str) -> CaseReference | None:
        return next((item for item in self.references if item.reference_id == reference_id), None)

    def admit(self, reference: CaseReference, policy: ScopePolicy) -> "ReferenceSet":
        if self.get(reference.reference_id) is not None:
            raise ValueError(f"duplicate CaseReference: {reference.reference_id}")
        if not policy.admits_type(reference.reference_type):
            raise ValueError(f"reference type rejected by ScopePolicy: {reference.reference_type}")
        if reference.cross_case_source and not policy.cross_case_allowed:
            raise ValueError("cross-case reference rejected by ScopePolicy")
        if policy.require_authorization and reference.authorization is not ReferenceAuthorization.AUTHORIZED:
            raise ValueError("reference requires explicit authorization")
        return ReferenceSet(self.references + (reference,))


@dataclass(frozen=True, slots=True)
class CaseScope:
    """KCS-1.2 runtime adapter; legacy Case remains unchanged."""

    case_id: str
    scope_policy: ScopePolicy
    reference_set: ReferenceSet
    owner: str
    operational_state: CaseOperationalState = CaseOperationalState.INTAKE
    epistemic_state: CaseEpistemicState = CaseEpistemicState.INSUFFICIENT_EVIDENCE
    goals: tuple[str, ...] = ()
    model_ref: str | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("CaseScope.case_id cannot be empty")
        if not self.owner.strip():
            raise ValueError("CaseScope.owner cannot be empty")
        if self.version < 1:
            raise ValueError("CaseScope.version must be >= 1")
        if any(not goal.strip() for goal in self.goals):
            raise ValueError("CaseScope goals cannot contain empty values")

    def with_reference(self, reference: CaseReference) -> "CaseScope":
        return replace(
            self,
            reference_set=self.reference_set.admit(reference, self.scope_policy),
            version=self.version + 1,
        )

    def with_states(
        self,
        *,
        operational_state: CaseOperationalState | None = None,
        epistemic_state: CaseEpistemicState | None = None,
    ) -> "CaseScope":
        return replace(
            self,
            operational_state=operational_state or self.operational_state,
            epistemic_state=epistemic_state or self.epistemic_state,
            version=self.version + 1,
        )
