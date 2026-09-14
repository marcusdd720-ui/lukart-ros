"""Governed, fail-closed CASE product-hardening contracts.

The module reuses :class:`CanonicalCaseLedger` as the only authoritative CASE
history. Operational execution state is never a replacement for that ledger.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum

from core.case_ledger import CanonicalCaseLedger, CaseId, ContentAddress, LedgerEvent, ObjectId
from core.p3.contracts import RuntimeIdentity, canonical_json
from knowledge.models.case import Case, CaseStatus

HARDENING_SCHEMA_V1 = "lukart.case-product-hardening.v1"
EVENT_ENVELOPE_SCHEMA_V1 = "lukart.case-event-envelope.v1"
EXTERNAL_ACTION_IDENTITY_SCHEMA_V1 = "lukart.external-action-identity.v1"
EXTERNAL_ACTION_RECEIPT_SCHEMA_V1 = "lukart.external-action-receipt.v1"
RESPONSE_CLASSIFICATION_SCHEMA_V1 = "lukart.response-classification.v1"
RESPONSE_DELTA_SCHEMA_V1 = "lukart.response-delta.v1"
LEGAL_RULE_SCHEMA_V1 = "lukart.temporal-legal-rule.v1"
LEGAL_EFFECT_SCHEMA_V1 = "lukart.legal-effect-assessment.v1"
CLOSURE_ASSESSMENT_SCHEMA_V1 = "lukart.closure-assessment.v1"
REOPEN_DECISION_SCHEMA_V1 = "lukart.case-reopen-decision.v1"
AUTHORITY_APPROVAL_SCHEMA_V1 = "lukart.authority-approval.v1"
CASE_AUTHORITY_SCHEMA_V1 = "lukart.case-authority-grant.v1"
CONTENT_EVIDENCE_SCHEMA_V1 = "lukart.content-addressed-evidence.v1"

EXTERNAL_ACTION_RECEIPT_RECORDED = "EXTERNAL_ACTION_RECEIPT_RECORDED"
EXTERNAL_ACTION_RESERVED = "EXTERNAL_ACTION_RESERVED"
EXTERNAL_ACTION_CONFIRMED = "EXTERNAL_ACTION_CONFIRMED"
EXTERNAL_ACTION_OUTCOME_UNKNOWN = "EXTERNAL_ACTION_OUTCOME_UNKNOWN"
RESPONSE_CLASSIFICATION_ACCEPTED = "RESPONSE_CLASSIFICATION_ACCEPTED"
RESPONSE_DELTA_RECORDED = "RESPONSE_DELTA_RECORDED"
LEGAL_EFFECT_ASSESSMENT_RECORDED = "LEGAL_EFFECT_ASSESSMENT_RECORDED"
CASE_FILED = "CASE_FILED"
CASE_CLOSED = "CASE_CLOSED"
CASE_REOPENED = "CASE_REOPENED"


class CaseProductHardeningError(ValueError):
    """A fail-closed CASE product contract was violated."""


class OutcomeUnknownError(CaseProductHardeningError):
    """The external outcome is unknown and must be reconciled."""


class IdempotencyConflictError(CaseProductHardeningError):
    """A logical action id was reused for a different immutable intent."""


def _identifier(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise CaseProductHardeningError(
            f"{field_name} must be nonblank and already canonical"
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CaseProductHardeningError(f"{field_name} contains control characters")
    return value


def _aware(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CaseProductHardeningError(f"{field_name} must be timezone-aware")
    return value


def _json_mapping(value: Mapping[str, object], *, field_name: str) -> dict[str, object]:
    try:
        decoded = json.loads(canonical_json(dict(value)))
    except (TypeError, ValueError) as exc:
        raise CaseProductHardeningError(
            f"{field_name} is not canonically serializable"
        ) from exc
    if not isinstance(decoded, dict):
        raise CaseProductHardeningError(f"{field_name} must be a mapping")
    return decoded


def _prerequisite_mapping(
    value: Mapping[str, bool | None],
    *,
    field_name: str,
) -> dict[str, bool | None]:
    normalized: dict[str, bool | None] = {}
    for key, item in value.items():
        _identifier(key, field_name=f"{field_name} key")
        if item is not None and not isinstance(item, bool):
            raise CaseProductHardeningError(
                f"{field_name} values must be bool or None"
            )
        normalized[key] = item
    _json_mapping(normalized, field_name=field_name)
    return normalized


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


@dataclass(frozen=True, slots=True)
class EnterpriseEventEnvelope:
    occurred_at: datetime
    recorded_at: datetime
    schema_version: str
    policy_version: str
    actor_ref: str
    authority_ref: str
    correlation_id: str
    causation_id: str
    payload: Mapping[str, object]
    payload_digest: ContentAddress
    schema: str = EVENT_ENVELOPE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != EVENT_ENVELOPE_SCHEMA_V1:
            raise CaseProductHardeningError("unsupported event envelope schema")
        _aware(self.occurred_at, field_name="occurred_at")
        _aware(self.recorded_at, field_name="recorded_at")
        for name, value in (
            ("schema_version", self.schema_version),
            ("policy_version", self.policy_version),
            ("actor_ref", self.actor_ref),
            ("authority_ref", self.authority_ref),
            ("correlation_id", self.correlation_id),
            ("causation_id", self.causation_id),
        ):
            _identifier(value, field_name=name)
        copied = _json_mapping(self.payload, field_name="event payload")
        object.__setattr__(self, "payload", copied)
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        payload: Mapping[str, object],
        schema_version: str,
        policy_version: str,
        actor_ref: str,
        authority_ref: str,
        correlation_id: str,
        causation_id: str,
        occurred_at: datetime | None = None,
        recorded_at: datetime | None = None,
    ) -> EnterpriseEventEnvelope:
        copied = _json_mapping(payload, field_name="event payload")
        now = datetime.now(UTC)
        return cls(
            occurred_at=occurred_at or now,
            recorded_at=recorded_at or now,
            schema_version=schema_version,
            policy_version=policy_version,
            actor_ref=actor_ref,
            authority_ref=authority_ref,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload=copied,
            payload_digest=ContentAddress.for_value(copied),
        )

    def verify(self) -> None:
        if self.payload_digest != ContentAddress.for_value(self.payload):
            raise CaseProductHardeningError("event payload digest mismatch")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "occurred_at": self.occurred_at.isoformat(),
            "recorded_at": self.recorded_at.isoformat(),
            "actor_ref": self.actor_ref,
            "authority_ref": self.authority_ref,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "payload_digest": self.payload_digest.canonical_dict(),
            "payload": dict(self.payload),
        }


@dataclass(frozen=True, slots=True)
class ContentAddressedEvidence:
    evidence_id: str
    case_id: CaseId
    content_digest: ContentAddress
    media_type: str
    source_ref: str
    received_at: datetime
    external_timestamp: datetime | None = None
    parser_version: str = "none"
    extraction_version: str = "none"
    storage_ref: str = "private"
    privacy_classification: str = "PRIVATE"
    schema: str = CONTENT_EVIDENCE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CONTENT_EVIDENCE_SCHEMA_V1:
            raise CaseProductHardeningError("unsupported content evidence schema")
        for name, value in (
            ("evidence_id", self.evidence_id),
            ("media_type", self.media_type),
            ("source_ref", self.source_ref),
            ("parser_version", self.parser_version),
            ("extraction_version", self.extraction_version),
            ("storage_ref", self.storage_ref),
            ("privacy_classification", self.privacy_classification),
        ):
            _identifier(value, field_name=name)
        _aware(self.received_at, field_name="received_at")
        if self.external_timestamp is not None:
            _aware(self.external_timestamp, field_name="external_timestamp")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "evidence_id": self.evidence_id,
            "case_id": self.case_id.value,
            "content_digest": self.content_digest.canonical_dict(),
            "media_type": self.media_type,
            "source_ref": self.source_ref,
            "received_at": self.received_at.isoformat(),
            "external_timestamp": _iso(self.external_timestamp),
            "parser_version": self.parser_version,
            "extraction_version": self.extraction_version,
            "storage_ref": self.storage_ref,
            "privacy_classification": self.privacy_classification,
        }


@dataclass(frozen=True, slots=True)
class ExternalActionIdentity:
    case_id: CaseId
    artifact_id: ObjectId
    artifact_version: str
    artifact_digest: ContentAddress
    logical_action_id: str
    action_type: str
    channel: str
    payload_digest: ContentAddress | None = None
    schema: str = EXTERNAL_ACTION_IDENTITY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != EXTERNAL_ACTION_IDENTITY_SCHEMA_V1:
            raise CaseProductHardeningError("unsupported external action identity schema")
        for name, value in (
            ("artifact_version", self.artifact_version),
            ("logical_action_id", self.logical_action_id),
            ("action_type", self.action_type),
            ("channel", self.channel),
        ):
            _identifier(value, field_name=name)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id.value,
            "artifact_id": self.artifact_id.value,
            "artifact_version": self.artifact_version,
            "artifact_digest": self.artifact_digest.canonical_dict(),
            "logical_action_id": self.logical_action_id,
            "action_type": self.action_type,
            "channel": self.channel,
            "payload_digest": (
                self.payload_digest.canonical_dict() if self.payload_digest else None
            ),
        }

    @property
    def identity_digest(self) -> ContentAddress:
        return ContentAddress.for_value(self.canonical_dict())

    @property
    def idempotency_key(self) -> str:
        return f"case-action:{self.identity_digest.digest}"


@dataclass(frozen=True, slots=True)
class AuthorityApproval:
    approval_id: str
    actor_ref: str
    authority_basis: str
    scope: str
    case_id: CaseId
    artifact_id: ObjectId
    artifact_version: str
    artifact_digest: ContentAddress
    action_type: str
    granted_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    schema: str = AUTHORITY_APPROVAL_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != AUTHORITY_APPROVAL_SCHEMA_V1:
            raise CaseProductHardeningError("unsupported authority approval schema")
        for name, value in (
            ("approval_id", self.approval_id),
            ("actor_ref", self.actor_ref),
            ("authority_basis", self.authority_basis),
            ("scope", self.scope),
            ("artifact_version", self.artifact_version),
            ("action_type", self.action_type),
        ):
            _identifier(value, field_name=name)
        _aware(self.granted_at, field_name="granted_at")
        if self.expires_at is not None:
            _aware(self.expires_at, field_name="expires_at")
        if self.revoked_at is not None:
            _aware(self.revoked_at, field_name="revoked_at")

    def authorizes(
        self,
        identity: ExternalActionIdentity,
        *,
        at: datetime | None = None,
    ) -> bool:
        moment = at or datetime.now(UTC)
        _aware(moment, field_name="authorization check time")
        return (
            self.revoked_at is None
            and (self.expires_at is None or moment <= self.expires_at)
            and self.case_id == identity.case_id
            and self.artifact_id == identity.artifact_id
            and self.artifact_version == identity.artifact_version
            and self.artifact_digest == identity.artifact_digest
            and self.action_type == identity.action_type
        )


@dataclass(frozen=True, slots=True)
class CaseAuthorityGrant:
    grant_id: str
    case_id: CaseId
    actor_ref: str
    authority_ref: str
    allowed_actions: frozenset[str]
    granted_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    schema: str = CASE_AUTHORITY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CASE_AUTHORITY_SCHEMA_V1:
            raise CaseProductHardeningError("unsupported CASE authority schema")
        for name, value in (
            ("grant_id", self.grant_id),
            ("actor_ref", self.actor_ref),
            ("authority_ref", self.authority_ref),
        ):
            _identifier(value, field_name=name)
        if not self.allowed_actions:
            raise CaseProductHardeningError("CASE authority must permit at least one action")
        for action in self.allowed_actions:
            _identifier(action, field_name="allowed_action")
        _aware(self.granted_at, field_name="granted_at")
        if self.expires_at is not None:
            _aware(self.expires_at, field_name="expires_at")
        if self.revoked_at is not None:
            _aware(self.revoked_at, field_name="revoked_at")

    def authorizes(
        self,
        *,
        case_id: CaseId,
        action: str,
        actor_ref: str,
        authority_ref: str,
        at: datetime | None = None,
    ) -> bool:
        moment = at or datetime.now(UTC)
        _aware(moment, field_name="authorization check time")
        return (
            self.revoked_at is None
            and (self.expires_at is None or moment <= self.expires_at)
            and self.case_id == case_id
            and self.actor_ref == actor_ref
            and self.authority_ref == authority_ref
            and action in self.allowed_actions
        )


class ReceiptOutcome(StrEnum):
    CONFIRMED_SUCCESS = "CONFIRMED_SUCCESS"
    CONFIRMED_NO_EFFECT = "CONFIRMED_NO_EFFECT"
    UNKNOWN = "UNKNOWN"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True, slots=True)
class ExternalActionReceipt:
    receipt_id: str
    identity_digest: ContentAddress
    attempt_id: str
    outcome: ReceiptOutcome
    evidence_ref: str
    recorded_at: datetime
    receipt_digest: ContentAddress
    provider_reference: str | None = None
    external_timestamp: datetime | None = None
    schema_version: str = "1"
    schema: str = EXTERNAL_ACTION_RECEIPT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != EXTERNAL_ACTION_RECEIPT_SCHEMA_V1:
            raise CaseProductHardeningError("unsupported external action receipt schema")
        for name, value in (
            ("receipt_id", self.receipt_id),
            ("attempt_id", self.attempt_id),
            ("evidence_ref", self.evidence_ref),
            ("schema_version", self.schema_version),
        ):
            _identifier(value, field_name=name)
        if self.provider_reference is not None:
            _identifier(self.provider_reference, field_name="provider_reference")
        _aware(self.recorded_at, field_name="receipt recorded_at")
        if self.external_timestamp is not None:
            _aware(self.external_timestamp, field_name="receipt external_timestamp")
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        receipt_id: str,
        identity: ExternalActionIdentity,
        attempt_id: str,
        outcome: ReceiptOutcome,
        evidence_ref: str,
        provider_reference: str | None = None,
        external_timestamp: datetime | None = None,
        recorded_at: datetime | None = None,
    ) -> ExternalActionReceipt:
        moment = recorded_at or datetime.now(UTC)
        body = cls._body(
            receipt_id=receipt_id,
            identity_digest=identity.identity_digest,
            attempt_id=attempt_id,
            outcome=outcome,
            evidence_ref=evidence_ref,
            provider_reference=provider_reference,
            external_timestamp=external_timestamp,
            recorded_at=moment,
            schema_version="1",
        )
        return cls(
            receipt_id=receipt_id,
            identity_digest=identity.identity_digest,
            attempt_id=attempt_id,
            outcome=outcome,
            evidence_ref=evidence_ref,
            provider_reference=provider_reference,
            external_timestamp=external_timestamp,
            recorded_at=moment,
            receipt_digest=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(
        *,
        receipt_id: str,
        identity_digest: ContentAddress,
        attempt_id: str,
        outcome: ReceiptOutcome,
        evidence_ref: str,
        provider_reference: str | None,
        external_timestamp: datetime | None,
        recorded_at: datetime,
        schema_version: str,
    ) -> dict[str, object]:
        return {
            "schema": EXTERNAL_ACTION_RECEIPT_SCHEMA_V1,
            "schema_version": schema_version,
            "receipt_id": receipt_id,
            "identity_digest": identity_digest.canonical_dict(),
            "attempt_id": attempt_id,
            "outcome": outcome.value,
            "evidence_ref": evidence_ref,
            "provider_reference": provider_reference,
            "external_timestamp": _iso(external_timestamp),
            "recorded_at": recorded_at.isoformat(),
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            receipt_id=self.receipt_id,
            identity_digest=self.identity_digest,
            attempt_id=self.attempt_id,
            outcome=self.outcome,
            evidence_ref=self.evidence_ref,
            provider_reference=self.provider_reference,
            external_timestamp=self.external_timestamp,
            recorded_at=self.recorded_at,
            schema_version=self.schema_version,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "receipt_digest": self.receipt_digest.canonical_dict(),
        }

    def verify(self) -> None:
        if self.receipt_digest != ContentAddress.for_value(self.canonical_body()):
            raise CaseProductHardeningError("external receipt content-address mismatch")


def verify_receipt_for_transition(
    receipt: ExternalActionReceipt,
    expected_identity: ExternalActionIdentity,
) -> None:
    receipt.verify()
    if receipt.identity_digest != expected_identity.identity_digest:
        raise CaseProductHardeningError(
            "external receipt does not match expected action identity"
        )
    if receipt.outcome is not ReceiptOutcome.CONFIRMED_SUCCESS:
        raise CaseProductHardeningError(
            "external receipt does not prove confirmed success"
        )


class ExternalActionState(StrEnum):
    RESERVED = "RESERVED"
    PRE_EFFECT_FAILED = "PRE_EFFECT_FAILED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    CONFIRMED_EXTERNAL_SUCCESS = "CONFIRMED_EXTERNAL_SUCCESS"
    CONFIRMED_NO_EFFECT = "CONFIRMED_NO_EFFECT"
    RECEIPT_RECOVERED = "RECEIPT_RECOVERED"


class ResponseSignal(StrEnum):
    ACKNOWLEDGMENT = "ACKNOWLEDGMENT"
    INFORMATION_ONLY = "INFORMATION_ONLY"
    FUTURE_RESPONSE_PROMISED = "FUTURE_RESPONSE_PROMISED"
    PARTIAL_RESPONSE = "PARTIAL_RESPONSE"
    SUBSTANTIVE_RESPONSE = "SUBSTANTIVE_RESPONSE"
    RESOLUTION_ISSUED = "RESOLUTION_ISSUED"
    NO_RESOLUTION = "NO_RESOLUTION"
    UNKNOWN = "UNKNOWN"
    UNRESOLVED = "UNRESOLVED"
    FINAL_RESOLUTION = "FINAL_RESOLUTION"


_NEGATED_RESOLUTION_MARKERS = (
    "nie wydano rozstrzygnięcia",
    "nie wydano decyzji",
    "brak rozstrzygnięcia",
    "no resolution was issued",
    "no decision was issued",
)


@dataclass(frozen=True, slots=True)
class ResponseClassification:
    response_digest: ContentAddress
    signals: frozenset[ResponseSignal]
    evidence_refs: tuple[str, ...]
    validator_version: str
    candidate_source: str
    classification_digest: ContentAddress
    schema: str = RESPONSE_CLASSIFICATION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != RESPONSE_CLASSIFICATION_SCHEMA_V1:
            raise CaseProductHardeningError("unsupported response classification schema")
        _identifier(self.validator_version, field_name="validator_version")
        _identifier(self.candidate_source, field_name="candidate_source")
        for ref in self.evidence_refs:
            _identifier(ref, field_name="classification evidence_ref")
        self.verify()

    @classmethod
    def validate_candidate(
        cls,
        *,
        response_text: str,
        proposed_signals: Sequence[ResponseSignal],
        evidence_refs: Sequence[str],
        validator_version: str = "response-validator.v1",
        candidate_source: str = "deterministic",
    ) -> ResponseClassification:
        normalized = " ".join(response_text.lower().split())
        signals = frozenset(proposed_signals)
        negated = any(marker in normalized for marker in _NEGATED_RESOLUTION_MARKERS)
        conflicted = (
            ResponseSignal.RESOLUTION_ISSUED in signals
            and ResponseSignal.NO_RESOLUTION in signals
        )
        if conflicted and ResponseSignal.UNRESOLVED not in signals:
            raise CaseProductHardeningError(
                "conflicting resolution signals must remain explicitly UNRESOLVED"
            )
        if ResponseSignal.FINAL_RESOLUTION in signals:
            unsafe_final = (
                ResponseSignal.RESOLUTION_ISSUED not in signals
                or ResponseSignal.NO_RESOLUTION in signals
                or ResponseSignal.UNKNOWN in signals
                or ResponseSignal.UNRESOLVED in signals
                or negated
            )
            if unsafe_final:
                raise CaseProductHardeningError(
                    "FINAL_RESOLUTION lacks safe affirmative resolution evidence"
                )
        response_digest = ContentAddress.for_value({"response_text": response_text})
        body = cls._body(
            response_digest=response_digest,
            signals=signals,
            evidence_refs=tuple(evidence_refs),
            validator_version=validator_version,
            candidate_source=candidate_source,
        )
        return cls(
            response_digest=response_digest,
            signals=signals,
            evidence_refs=tuple(evidence_refs),
            validator_version=validator_version,
            candidate_source=candidate_source,
            classification_digest=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(
        *,
        response_digest: ContentAddress,
        signals: frozenset[ResponseSignal],
        evidence_refs: tuple[str, ...],
        validator_version: str,
        candidate_source: str,
    ) -> dict[str, object]:
        return {
            "schema": RESPONSE_CLASSIFICATION_SCHEMA_V1,
            "response_digest": response_digest.canonical_dict(),
            "signals": sorted(signal.value for signal in signals),
            "evidence_refs": list(evidence_refs),
            "validator_version": validator_version,
            "candidate_source": candidate_source,
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            response_digest=self.response_digest,
            signals=self.signals,
            evidence_refs=self.evidence_refs,
            validator_version=self.validator_version,
            candidate_source=self.candidate_source,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "classification_digest": self.classification_digest.canonical_dict(),
        }

    def verify(self) -> None:
        expected = ContentAddress.for_value(self.canonical_body())
        if self.classification_digest != expected:
            raise CaseProductHardeningError(
                "response classification content-address mismatch"
            )


class EpistemicLabel(StrEnum):
    FACT = "FACT"
    CLAIM = "CLAIM"
    HYPOTHESIS = "HYPOTHESIS"
    INTERPRETATION = "INTERPRETATION"
    UNKNOWN = "UNKNOWN"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class DeltaAssertion:
    statement: str
    label: EpistemicLabel
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _identifier(self.statement, field_name="delta assertion statement")
        for ref in self.evidence_refs:
            _identifier(ref, field_name="delta assertion evidence_ref")
        if self.label is EpistemicLabel.FACT and not self.evidence_refs:
            raise CaseProductHardeningError("FACT delta assertion requires evidence")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "statement": self.statement,
            "label": self.label.value,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True, slots=True)
class ResponseDelta:
    case_id: CaseId
    base_ledger_position: int
    base_state_digest: ContentAddress
    response_digest: ContentAddress
    classification_digest: ContentAddress
    assertions: tuple[DeltaAssertion, ...]
    contradictions: tuple[str, ...]
    deadline_changes: tuple[str, ...]
    procedural_changes: tuple[str, ...]
    lifecycle_candidates: tuple[str, ...]
    validator_version: str
    delta_digest: ContentAddress
    schema_version: str = "1"
    schema: str = RESPONSE_DELTA_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != RESPONSE_DELTA_SCHEMA_V1:
            raise CaseProductHardeningError("unsupported response delta schema")
        if self.base_ledger_position < -1:
            raise CaseProductHardeningError("base_ledger_position cannot be less than -1")
        _identifier(self.validator_version, field_name="delta validator_version")
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        case_id: CaseId,
        base_ledger_position: int,
        base_state_digest: ContentAddress,
        classification: ResponseClassification,
        assertions: Sequence[DeltaAssertion] = (),
        contradictions: Sequence[str] = (),
        deadline_changes: Sequence[str] = (),
        procedural_changes: Sequence[str] = (),
        lifecycle_candidates: Sequence[str] = (),
        validator_version: str = "response-delta.v1",
    ) -> ResponseDelta:
        body = cls._body(
            case_id=case_id,
            base_ledger_position=base_ledger_position,
            base_state_digest=base_state_digest,
            response_digest=classification.response_digest,
            classification_digest=classification.classification_digest,
            assertions=tuple(assertions),
            contradictions=tuple(contradictions),
            deadline_changes=tuple(deadline_changes),
            procedural_changes=tuple(procedural_changes),
            lifecycle_candidates=tuple(lifecycle_candidates),
            validator_version=validator_version,
            schema_version="1",
        )
        return cls(
            case_id=case_id,
            base_ledger_position=base_ledger_position,
            base_state_digest=base_state_digest,
            response_digest=classification.response_digest,
            classification_digest=classification.classification_digest,
            assertions=tuple(assertions),
            contradictions=tuple(contradictions),
            deadline_changes=tuple(deadline_changes),
            procedural_changes=tuple(procedural_changes),
            lifecycle_candidates=tuple(lifecycle_candidates),
            validator_version=validator_version,
            delta_digest=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(
        *,
        case_id: CaseId,
        base_ledger_position: int,
        base_state_digest: ContentAddress,
        response_digest: ContentAddress,
        classification_digest: ContentAddress,
        assertions: tuple[DeltaAssertion, ...],
        contradictions: tuple[str, ...],
        deadline_changes: tuple[str, ...],
        procedural_changes: tuple[str, ...],
        lifecycle_candidates: tuple[str, ...],
        validator_version: str,
        schema_version: str,
    ) -> dict[str, object]:
        return {
            "schema": RESPONSE_DELTA_SCHEMA_V1,
            "schema_version": schema_version,
            "case_id": case_id.value,
            "base_ledger_position": base_ledger_position,
            "base_state_digest": base_state_digest.canonical_dict(),
            "response_digest": response_digest.canonical_dict(),
            "classification_digest": classification_digest.canonical_dict(),
            "assertions": [item.canonical_dict() for item in assertions],
            "contradictions": list(contradictions),
            "deadline_changes": list(deadline_changes),
            "procedural_changes": list(procedural_changes),
            "lifecycle_candidates": list(lifecycle_candidates),
            "validator_version": validator_version,
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            case_id=self.case_id,
            base_ledger_position=self.base_ledger_position,
            base_state_digest=self.base_state_digest,
            response_digest=self.response_digest,
            classification_digest=self.classification_digest,
            assertions=self.assertions,
            contradictions=self.contradictions,
            deadline_changes=self.deadline_changes,
            procedural_changes=self.procedural_changes,
            lifecycle_candidates=self.lifecycle_candidates,
            validator_version=self.validator_version,
            schema_version=self.schema_version,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "delta_digest": self.delta_digest.canonical_dict()}

    def verify(self) -> None:
        if self.delta_digest != ContentAddress.for_value(self.canonical_body()):
            raise CaseProductHardeningError("response delta content-address mismatch")


@dataclass(frozen=True, slots=True)
class TemporalLegalRule:
    jurisdiction: str
    rule_id: str
    source_ref: str
    source_digest: ContentAddress
    valid_from: date
    valid_to: date | None
    retrieved_at: datetime
    verified_at: datetime
    verification_method: str
    verified: bool = True
    schema: str = LEGAL_RULE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != LEGAL_RULE_SCHEMA_V1:
            raise CaseProductHardeningError("unsupported temporal legal rule schema")
        for name, value in (
            ("jurisdiction", self.jurisdiction),
            ("rule_id", self.rule_id),
            ("source_ref", self.source_ref),
            ("verification_method", self.verification_method),
        ):
            _identifier(value, field_name=name)
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise CaseProductHardeningError("legal rule valid_to precedes valid_from")
        _aware(self.retrieved_at, field_name="legal rule retrieved_at")
        _aware(self.verified_at, field_name="legal rule verified_at")

    def valid_on(self, on_date: date) -> bool:
        return self.valid_from <= on_date and (
            self.valid_to is None or on_date <= self.valid_to
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "jurisdiction": self.jurisdiction,
            "rule_id": self.rule_id,
            "source_ref": self.source_ref,
            "source_digest": self.source_digest.canonical_dict(),
            "valid_from": self.valid_from.isoformat(),
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "retrieved_at": self.retrieved_at.isoformat(),
            "verified_at": self.verified_at.isoformat(),
            "verification_method": self.verification_method,
            "verified": self.verified,
        }


class LegalEffectStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    UNRESOLVED = "UNRESOLVED"
    VERIFIED_EFFECTIVE = "VERIFIED_EFFECTIVE"
    VERIFIED_NOT_EFFECTIVE = "VERIFIED_NOT_EFFECTIVE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class LegalEffectAssessment:
    case_id: CaseId
    subject_ref: str
    lifecycle_ref: str
    rule_digest: ContentAddress | None
    effect_status: LegalEffectStatus
    prerequisites: Mapping[str, bool | None]
    evidence_refs: tuple[str, ...]
    contradictions: tuple[str, ...]
    assessed_on: date
    effective_at: datetime | None
    assessment_digest: ContentAddress
    schema: str = LEGAL_EFFECT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != LEGAL_EFFECT_SCHEMA_V1:
            raise CaseProductHardeningError("unsupported legal effect schema")
        _identifier(self.subject_ref, field_name="subject_ref")
        _identifier(self.lifecycle_ref, field_name="lifecycle_ref")
        copied = _prerequisite_mapping(
            self.prerequisites,
            field_name="legal effect prerequisites",
        )
        object.__setattr__(self, "prerequisites", copied)
        if self.effective_at is not None:
            _aware(self.effective_at, field_name="effective_at")
            if self.effect_status is not LegalEffectStatus.VERIFIED_EFFECTIVE:
                raise CaseProductHardeningError(
                    "effective_at is allowed only for VERIFIED_EFFECTIVE"
                )
        self.verify()

    @staticmethod
    def _body(
        *,
        case_id: CaseId,
        subject_ref: str,
        lifecycle_ref: str,
        rule_digest: ContentAddress | None,
        effect_status: LegalEffectStatus,
        prerequisites: Mapping[str, bool | None],
        evidence_refs: tuple[str, ...],
        contradictions: tuple[str, ...],
        assessed_on: date,
        effective_at: datetime | None,
    ) -> dict[str, object]:
        return {
            "schema": LEGAL_EFFECT_SCHEMA_V1,
            "case_id": case_id.value,
            "subject_ref": subject_ref,
            "lifecycle_ref": lifecycle_ref,
            "rule_digest": rule_digest.canonical_dict() if rule_digest else None,
            "effect_status": effect_status.value,
            "prerequisites": dict(prerequisites),
            "evidence_refs": list(evidence_refs),
            "contradictions": list(contradictions),
            "assessed_on": assessed_on.isoformat(),
            "effective_at": _iso(effective_at),
        }

    @classmethod
    def assess(
        cls,
        *,
        case_id: CaseId,
        subject_ref: str,
        lifecycle_ref: str,
        rule: TemporalLegalRule | None,
        assessed_on: date,
        prerequisites: Mapping[str, bool | None],
        evidence_refs: Sequence[str],
        contradictions: Sequence[str] = (),
        effective_at: datetime | None = None,
    ) -> LegalEffectAssessment:
        normalized_prerequisites = _prerequisite_mapping(
            prerequisites,
            field_name="legal effect prerequisites",
        )
        values = tuple(normalized_prerequisites.values())
        if contradictions:
            status = LegalEffectStatus.UNRESOLVED
        elif rule is None or not rule.verified or not rule.valid_on(assessed_on):
            status = LegalEffectStatus.UNKNOWN
        elif not normalized_prerequisites or any(value is None for value in values):
            status = LegalEffectStatus.UNKNOWN
        elif not evidence_refs:
            status = LegalEffectStatus.UNKNOWN
        elif any(value is False for value in values):
            status = LegalEffectStatus.VERIFIED_NOT_EFFECTIVE
        else:
            status = LegalEffectStatus.VERIFIED_EFFECTIVE
        if status is not LegalEffectStatus.VERIFIED_EFFECTIVE:
            effective_at = None
        rule_digest = ContentAddress.for_value(rule.canonical_dict()) if rule else None
        evidence_tuple = tuple(evidence_refs)
        contradiction_tuple = tuple(contradictions)
        body = cls._body(
            case_id=case_id,
            subject_ref=subject_ref,
            lifecycle_ref=lifecycle_ref,
            rule_digest=rule_digest,
            effect_status=status,
            prerequisites=normalized_prerequisites,
            evidence_refs=evidence_tuple,
            contradictions=contradiction_tuple,
            assessed_on=assessed_on,
            effective_at=effective_at,
        )
        return cls(
            case_id=case_id,
            subject_ref=subject_ref,
            lifecycle_ref=lifecycle_ref,
            rule_digest=rule_digest,
            effect_status=status,
            prerequisites=normalized_prerequisites,
            evidence_refs=evidence_tuple,
            contradictions=contradiction_tuple,
            assessed_on=assessed_on,
            effective_at=effective_at,
            assessment_digest=ContentAddress.for_value(body),
        )

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            case_id=self.case_id,
            subject_ref=self.subject_ref,
            lifecycle_ref=self.lifecycle_ref,
            rule_digest=self.rule_digest,
            effect_status=self.effect_status,
            prerequisites=self.prerequisites,
            evidence_refs=self.evidence_refs,
            contradictions=self.contradictions,
            assessed_on=self.assessed_on,
            effective_at=self.effective_at,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "assessment_digest": self.assessment_digest.canonical_dict(),
        }

    def verify(self) -> None:
        if self.assessment_digest != ContentAddress.for_value(self.canonical_body()):
            raise CaseProductHardeningError(
                "legal effect assessment content-address mismatch"
            )


class ClosureBlocker(StrEnum):
    OPEN_DEADLINE = "OPEN_DEADLINE"
    EXPECTED_RESPONSE = "EXPECTED_RESPONSE"
    REQUIRED_FOLLOW_UP = "REQUIRED_FOLLOW_UP"
    MATERIAL_UNKNOWN = "MATERIAL_UNKNOWN"
    MATERIAL_UNRESOLVED = "MATERIAL_UNRESOLVED"
    UNRESOLVED_CONTRADICTION = "UNRESOLVED_CONTRADICTION"
    MISSING_EXPECTED_RECEIPT = "MISSING_EXPECTED_RECEIPT"
    UNASSESSED_RESPONSE = "UNASSESSED_RESPONSE"
    OPEN_REMEDY = "OPEN_REMEDY"
    UNRESOLVED_LEGAL_EFFECT = "UNRESOLVED_LEGAL_EFFECT"


@dataclass(frozen=True, slots=True)
class ClosureAssessment:
    case_id: CaseId
    state_digest: ContentAddress
    ledger_position: int
    blockers: tuple[ClosureBlocker, ...]
    closure_reason: str
    actor_ref: str
    authority_ref: str
    policy_version: str
    lifecycle_epoch: int
    assessed_at: datetime
    assessment_digest: ContentAddress
    schema: str = CLOSURE_ASSESSMENT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CLOSURE_ASSESSMENT_SCHEMA_V1:
            raise CaseProductHardeningError("unsupported closure assessment schema")
        if self.ledger_position < -1:
            raise CaseProductHardeningError("closure ledger_position cannot be less than -1")
        if self.lifecycle_epoch < 0:
            raise CaseProductHardeningError("lifecycle_epoch cannot be negative")
        for name, value in (
            ("closure_reason", self.closure_reason),
            ("actor_ref", self.actor_ref),
            ("authority_ref", self.authority_ref),
            ("policy_version", self.policy_version),
        ):
            _identifier(value, field_name=name)
        _aware(self.assessed_at, field_name="closure assessed_at")
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        case_id: CaseId,
        state_digest: ContentAddress,
        ledger_position: int,
        blockers: Sequence[ClosureBlocker],
        closure_reason: str,
        actor_ref: str,
        authority_ref: str,
        policy_version: str,
        lifecycle_epoch: int = 0,
        assessed_at: datetime | None = None,
    ) -> ClosureAssessment:
        moment = assessed_at or datetime.now(UTC)
        normalized = tuple(sorted(set(blockers), key=lambda item: item.value))
        body = cls._body(
            case_id=case_id,
            state_digest=state_digest,
            ledger_position=ledger_position,
            blockers=normalized,
            closure_reason=closure_reason,
            actor_ref=actor_ref,
            authority_ref=authority_ref,
            policy_version=policy_version,
            lifecycle_epoch=lifecycle_epoch,
            assessed_at=moment,
        )
        return cls(
            case_id=case_id,
            state_digest=state_digest,
            ledger_position=ledger_position,
            blockers=normalized,
            closure_reason=closure_reason,
            actor_ref=actor_ref,
            authority_ref=authority_ref,
            policy_version=policy_version,
            lifecycle_epoch=lifecycle_epoch,
            assessed_at=moment,
            assessment_digest=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(
        *,
        case_id: CaseId,
        state_digest: ContentAddress,
        ledger_position: int,
        blockers: tuple[ClosureBlocker, ...],
        closure_reason: str,
        actor_ref: str,
        authority_ref: str,
        policy_version: str,
        lifecycle_epoch: int,
        assessed_at: datetime,
    ) -> dict[str, object]:
        return {
            "schema": CLOSURE_ASSESSMENT_SCHEMA_V1,
            "case_id": case_id.value,
            "state_digest": state_digest.canonical_dict(),
            "ledger_position": ledger_position,
            "blockers": [item.value for item in blockers],
            "closure_reason": closure_reason,
            "actor_ref": actor_ref,
            "authority_ref": authority_ref,
            "policy_version": policy_version,
            "lifecycle_epoch": lifecycle_epoch,
            "assessed_at": assessed_at.isoformat(),
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            case_id=self.case_id,
            state_digest=self.state_digest,
            ledger_position=self.ledger_position,
            blockers=self.blockers,
            closure_reason=self.closure_reason,
            actor_ref=self.actor_ref,
            authority_ref=self.authority_ref,
            policy_version=self.policy_version,
            lifecycle_epoch=self.lifecycle_epoch,
            assessed_at=self.assessed_at,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "assessment_digest": self.assessment_digest.canonical_dict(),
        }

    @property
    def eligible(self) -> bool:
        return not self.blockers

    def verify(self) -> None:
        if self.assessment_digest != ContentAddress.for_value(self.canonical_body()):
            raise CaseProductHardeningError(
                "closure assessment content-address mismatch"
            )


@dataclass(frozen=True, slots=True)
class ReopenDecision:
    case_id: CaseId
    previous_epoch: int
    new_epoch: int
    reason: str
    actor_ref: str
    authority_ref: str
    decided_at: datetime
    decision_digest: ContentAddress
    schema: str = REOPEN_DECISION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != REOPEN_DECISION_SCHEMA_V1:
            raise CaseProductHardeningError("unsupported reopen decision schema")
        if self.new_epoch != self.previous_epoch + 1:
            raise CaseProductHardeningError(
                "reopen decision must increment lifecycle epoch by one"
            )
        for name, value in (
            ("reason", self.reason),
            ("actor_ref", self.actor_ref),
            ("authority_ref", self.authority_ref),
        ):
            _identifier(value, field_name=name)
        _aware(self.decided_at, field_name="reopen decided_at")
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        case_id: CaseId,
        previous_epoch: int,
        reason: str,
        actor_ref: str,
        authority_ref: str,
        decided_at: datetime | None = None,
    ) -> ReopenDecision:
        if previous_epoch < 0:
            raise CaseProductHardeningError("previous lifecycle epoch cannot be negative")
        moment = decided_at or datetime.now(UTC)
        body = cls._body(
            case_id=case_id,
            previous_epoch=previous_epoch,
            new_epoch=previous_epoch + 1,
            reason=reason,
            actor_ref=actor_ref,
            authority_ref=authority_ref,
            decided_at=moment,
        )
        return cls(
            case_id=case_id,
            previous_epoch=previous_epoch,
            new_epoch=previous_epoch + 1,
            reason=reason,
            actor_ref=actor_ref,
            authority_ref=authority_ref,
            decided_at=moment,
            decision_digest=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(
        *,
        case_id: CaseId,
        previous_epoch: int,
        new_epoch: int,
        reason: str,
        actor_ref: str,
        authority_ref: str,
        decided_at: datetime,
    ) -> dict[str, object]:
        return {
            "schema": REOPEN_DECISION_SCHEMA_V1,
            "case_id": case_id.value,
            "previous_epoch": previous_epoch,
            "new_epoch": new_epoch,
            "reason": reason,
            "actor_ref": actor_ref,
            "authority_ref": authority_ref,
            "decided_at": decided_at.isoformat(),
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(
            case_id=self.case_id,
            previous_epoch=self.previous_epoch,
            new_epoch=self.new_epoch,
            reason=self.reason,
            actor_ref=self.actor_ref,
            authority_ref=self.authority_ref,
            decided_at=self.decided_at,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "decision_digest": self.decision_digest.canonical_dict(),
        }

    def verify(self) -> None:
        if self.decision_digest != ContentAddress.for_value(self.canonical_body()):
            raise CaseProductHardeningError("reopen decision content-address mismatch")


def append_contract_event(
    ledger: CanonicalCaseLedger,
    *,
    case_id: CaseId,
    event_type: str,
    runtime_identity: RuntimeIdentity,
    expected_head: ContentAddress | None,
    payload: Mapping[str, object],
    policy_version: str,
    actor_ref: str,
    authority_ref: str,
    correlation_id: str,
    causation_id: str,
    occurred_at: datetime | None = None,
) -> LedgerEvent:
    envelope = EnterpriseEventEnvelope.build(
        payload=payload,
        schema_version=HARDENING_SCHEMA_V1,
        policy_version=policy_version,
        actor_ref=actor_ref,
        authority_ref=authority_ref,
        correlation_id=correlation_id,
        causation_id=causation_id,
        occurred_at=occurred_at,
    )
    return ledger.append_event(
        case_id=case_id,
        event_type=event_type,
        runtime_identity=runtime_identity,
        payload=envelope.canonical_dict(),
        expected_head=expected_head,
    )


def record_receipt_and_file_case(
    case: Case,
    ledger: CanonicalCaseLedger,
    *,
    identity: ExternalActionIdentity,
    receipt: ExternalActionReceipt,
    approval: AuthorityApproval,
    runtime_identity: RuntimeIdentity,
    expected_head: ContentAddress | None,
    policy_version: str,
    correlation_id: str,
    causation_id: str,
) -> tuple[LedgerEvent, LedgerEvent]:
    if case.id != identity.case_id.value:
        raise CaseProductHardeningError(
            "CASE model and external action identity do not match"
        )
    if not approval.authorizes(identity):
        raise CaseProductHardeningError(
            "external action is not covered by exact authority approval"
        )
    verify_receipt_for_transition(receipt, identity)
    receipt_event = append_contract_event(
        ledger,
        case_id=identity.case_id,
        event_type=EXTERNAL_ACTION_RECEIPT_RECORDED,
        runtime_identity=runtime_identity,
        expected_head=expected_head,
        payload={
            "identity": identity.canonical_dict(),
            "receipt": receipt.canonical_dict(),
            "approval_id": approval.approval_id,
        },
        policy_version=policy_version,
        actor_ref=approval.actor_ref,
        authority_ref=approval.authority_basis,
        correlation_id=correlation_id,
        causation_id=causation_id,
        occurred_at=receipt.external_timestamp or receipt.recorded_at,
    )
    filed_event = append_contract_event(
        ledger,
        case_id=identity.case_id,
        event_type=CASE_FILED,
        runtime_identity=runtime_identity,
        expected_head=receipt_event.event_id,
        payload={
            "receipt_digest": receipt.receipt_digest.canonical_dict(),
            "identity_digest": identity.identity_digest.canonical_dict(),
            "artifact_id": identity.artifact_id.value,
            "artifact_version": identity.artifact_version,
        },
        policy_version=policy_version,
        actor_ref=approval.actor_ref,
        authority_ref=approval.authority_basis,
        correlation_id=correlation_id,
        causation_id=receipt_event.event_id.digest,
        occurred_at=receipt.external_timestamp or receipt.recorded_at,
    )
    case.status = CaseStatus.FILED
    case.metadata["last_filing_receipt_digest"] = receipt.receipt_digest.digest
    case.touch()
    return receipt_event, filed_event


def record_response_classification(
    ledger: CanonicalCaseLedger,
    *,
    case_id: CaseId,
    classification: ResponseClassification,
    runtime_identity: RuntimeIdentity,
    expected_head: ContentAddress | None,
    policy_version: str,
    actor_ref: str,
    authority_ref: str,
    correlation_id: str,
    causation_id: str,
) -> LedgerEvent:
    classification.verify()
    return append_contract_event(
        ledger,
        case_id=case_id,
        event_type=RESPONSE_CLASSIFICATION_ACCEPTED,
        runtime_identity=runtime_identity,
        expected_head=expected_head,
        payload={"classification": classification.canonical_dict()},
        policy_version=policy_version,
        actor_ref=actor_ref,
        authority_ref=authority_ref,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )


def record_response_delta(
    ledger: CanonicalCaseLedger,
    *,
    delta: ResponseDelta,
    current_state_digest: ContentAddress,
    current_ledger_position: int,
    runtime_identity: RuntimeIdentity,
    expected_head: ContentAddress | None,
    policy_version: str,
    actor_ref: str,
    authority_ref: str,
    correlation_id: str,
    causation_id: str,
) -> LedgerEvent:
    delta.verify()
    if delta.base_state_digest != current_state_digest:
        raise CaseProductHardeningError("response delta base state is stale")
    if delta.base_ledger_position != current_ledger_position:
        raise CaseProductHardeningError("response delta ledger position is stale")
    return append_contract_event(
        ledger,
        case_id=delta.case_id,
        event_type=RESPONSE_DELTA_RECORDED,
        runtime_identity=runtime_identity,
        expected_head=expected_head,
        payload={"delta": delta.canonical_dict()},
        policy_version=policy_version,
        actor_ref=actor_ref,
        authority_ref=authority_ref,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )


def record_legal_effect_assessment(
    ledger: CanonicalCaseLedger,
    *,
    assessment: LegalEffectAssessment,
    runtime_identity: RuntimeIdentity,
    expected_head: ContentAddress | None,
    policy_version: str,
    actor_ref: str,
    authority_ref: str,
    correlation_id: str,
    causation_id: str,
) -> LedgerEvent:
    assessment.verify()
    return append_contract_event(
        ledger,
        case_id=assessment.case_id,
        event_type=LEGAL_EFFECT_ASSESSMENT_RECORDED,
        runtime_identity=runtime_identity,
        expected_head=expected_head,
        payload={"assessment": assessment.canonical_dict()},
        policy_version=policy_version,
        actor_ref=actor_ref,
        authority_ref=authority_ref,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )


def close_case_governed(
    case: Case,
    ledger: CanonicalCaseLedger,
    *,
    assessment: ClosureAssessment,
    authority: CaseAuthorityGrant,
    current_state_digest: ContentAddress,
    current_ledger_position: int,
    runtime_identity: RuntimeIdentity,
    expected_head: ContentAddress | None,
    correlation_id: str,
    causation_id: str,
) -> LedgerEvent:
    if case.id != assessment.case_id.value:
        raise CaseProductHardeningError("closure assessment belongs to another CASE")
    if assessment.state_digest != current_state_digest:
        raise CaseProductHardeningError("closure assessment is stale for current CASE state")
    if assessment.ledger_position != current_ledger_position:
        raise CaseProductHardeningError(
            "closure assessment is stale for current ledger position"
        )
    if not assessment.eligible:
        raise CaseProductHardeningError(
            "CASE closure is blocked by material open items"
        )
    if not authority.authorizes(
        case_id=assessment.case_id,
        action=CASE_CLOSED,
        actor_ref=assessment.actor_ref,
        authority_ref=assessment.authority_ref,
        at=assessment.assessed_at,
    ):
        raise CaseProductHardeningError("CASE closure actor is not authorized")
    event = append_contract_event(
        ledger,
        case_id=assessment.case_id,
        event_type=CASE_CLOSED,
        runtime_identity=runtime_identity,
        expected_head=expected_head,
        payload={
            "assessment": assessment.canonical_dict(),
            "authority_grant_id": authority.grant_id,
        },
        policy_version=assessment.policy_version,
        actor_ref=assessment.actor_ref,
        authority_ref=assessment.authority_ref,
        correlation_id=correlation_id,
        causation_id=causation_id,
        occurred_at=assessment.assessed_at,
    )
    case.status = CaseStatus.CLOSED
    case.metadata["lifecycle_epoch"] = assessment.lifecycle_epoch
    case.metadata["closure_assessment_digest"] = assessment.assessment_digest.digest
    case.touch()
    return event


def reopen_case_governed(
    case: Case,
    ledger: CanonicalCaseLedger,
    *,
    decision: ReopenDecision,
    authority: CaseAuthorityGrant,
    runtime_identity: RuntimeIdentity,
    expected_head: ContentAddress | None,
    policy_version: str,
    correlation_id: str,
    causation_id: str,
) -> LedgerEvent:
    if case.id != decision.case_id.value:
        raise CaseProductHardeningError("reopen decision belongs to another CASE")
    if case.status is not CaseStatus.CLOSED:
        raise CaseProductHardeningError("only a CLOSED CASE can be reopened")
    current_epoch = int(case.metadata.get("lifecycle_epoch", 0))
    if decision.previous_epoch != current_epoch:
        raise CaseProductHardeningError(
            "reopen decision is stale for lifecycle epoch"
        )
    if not authority.authorizes(
        case_id=decision.case_id,
        action=CASE_REOPENED,
        actor_ref=decision.actor_ref,
        authority_ref=decision.authority_ref,
        at=decision.decided_at,
    ):
        raise CaseProductHardeningError("CASE reopen actor is not authorized")
    event = append_contract_event(
        ledger,
        case_id=decision.case_id,
        event_type=CASE_REOPENED,
        runtime_identity=runtime_identity,
        expected_head=expected_head,
        payload={
            "decision": decision.canonical_dict(),
            "authority_grant_id": authority.grant_id,
        },
        policy_version=policy_version,
        actor_ref=decision.actor_ref,
        authority_ref=decision.authority_ref,
        correlation_id=correlation_id,
        causation_id=causation_id,
        occurred_at=decision.decided_at,
    )
    case.status = CaseStatus.ANALYSIS
    case.metadata["lifecycle_epoch"] = decision.new_epoch
    previous = event.previous_event_id
    case.metadata["reopened_from_event"] = previous.digest if previous else None
    case.touch()
    return event


__all__ = [
    "AUTHORITY_APPROVAL_SCHEMA_V1",
    "CASE_AUTHORITY_SCHEMA_V1",
    "CASE_CLOSED",
    "CASE_FILED",
    "CASE_REOPENED",
    "CLOSURE_ASSESSMENT_SCHEMA_V1",
    "CONTENT_EVIDENCE_SCHEMA_V1",
    "EXTERNAL_ACTION_CONFIRMED",
    "EXTERNAL_ACTION_IDENTITY_SCHEMA_V1",
    "EXTERNAL_ACTION_OUTCOME_UNKNOWN",
    "EXTERNAL_ACTION_RECEIPT_RECORDED",
    "EXTERNAL_ACTION_RESERVED",
    "LEGAL_EFFECT_ASSESSMENT_RECORDED",
    "RESPONSE_CLASSIFICATION_ACCEPTED",
    "RESPONSE_DELTA_RECORDED",
    "AuthorityApproval",
    "CaseAuthorityGrant",
    "CaseProductHardeningError",
    "ClosureAssessment",
    "ClosureBlocker",
    "ContentAddressedEvidence",
    "DeltaAssertion",
    "EnterpriseEventEnvelope",
    "EpistemicLabel",
    "ExternalActionIdentity",
    "ExternalActionReceipt",
    "ExternalActionState",
    "IdempotencyConflictError",
    "LegalEffectAssessment",
    "LegalEffectStatus",
    "OutcomeUnknownError",
    "ReceiptOutcome",
    "ReopenDecision",
    "ResponseClassification",
    "ResponseDelta",
    "ResponseSignal",
    "TemporalLegalRule",
    "append_contract_event",
    "close_case_governed",
    "record_legal_effect_assessment",
    "record_receipt_and_file_case",
    "record_response_classification",
    "record_response_delta",
    "reopen_case_governed",
    "verify_receipt_for_transition",
]
