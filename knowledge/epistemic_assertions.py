"""PHX-03 immutable epistemic assertions and CCL-derived state projection.

Canonical Case Ledger remains the only writable authority. This module defines
content-addressed assertion/transition contracts, validates exact evidence event
references, writes authoritative changes only through ``CanonicalCaseLedger``, and
rebuilds epistemic state deterministically from ledger history.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from core.case_ledger import CanonicalCaseLedger
from core.case_ledger.contracts import (
    CANONICALIZATION_PROFILE_V1,
    CanonicalizationProfile,
    CaseId,
    ContentAddress,
    LedgerEvent,
    ObjectId,
)
from core.p3.contracts import RuntimeIdentity, canonical_json
from knowledge.epistemic import (
    EpistemicStatusMachine,
    EpistemicTransitionRequest,
    KnowledgeStatus,
)

ASSERTION_SCHEMA_V2 = "lukart.epistemic-assertion.v2"
EPISTEMIC_POLICY_SCHEMA_V2 = "lukart.epistemic-policy.v2"
TRANSITION_DECISION_SCHEMA_V2 = "lukart.epistemic-transition-decision.v2"
EPISTEMIC_PROJECTION_SCHEMA_V2 = "lukart.epistemic-projection.v2"
ASSERTION_CREATED_EVENT_V1 = "epistemic.assertion.created.v1"
ASSERTION_TRANSITION_EVENT_V1 = "epistemic.assertion.transition.v1"
DEFAULT_FACT_EVIDENCE_EVENT_TYPES = ("evidence.ingested.v1",)


class EpistemicV2Error(ValueError):
    """Fail-closed PHX-03 contract or projection violation."""


def _identifier(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise EpistemicV2Error(f"{field_name} must be nonblank and already canonical")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise EpistemicV2Error(f"{field_name} cannot contain control characters")
    return value


def _canonical_mapping(
    value: Mapping[str, object],
    *,
    field_name: str,
) -> Mapping[str, object]:
    if any(not isinstance(key, str) for key in value):
        raise EpistemicV2Error(f"{field_name} keys must be strings")
    try:
        decoded: object = json.loads(canonical_json(dict(value)))
    except (TypeError, ValueError) as exc:
        raise EpistemicV2Error(f"{field_name} must be canonically serializable") from exc
    if not isinstance(decoded, dict):
        raise EpistemicV2Error(f"{field_name} must be an object")
    return MappingProxyType(cast(dict[str, object], decoded))


def _address(value: object, *, field_name: str) -> ContentAddress:
    if not isinstance(value, Mapping):
        raise EpistemicV2Error(f"{field_name} must be a content-address object")
    try:
        return ContentAddress.from_dict(cast(Mapping[str, object], value))
    except ValueError as exc:
        raise EpistemicV2Error(str(exc)) from exc


def _status(value: object, *, field_name: str) -> KnowledgeStatus:
    if not isinstance(value, str):
        raise EpistemicV2Error(f"{field_name} must be a string")
    try:
        return KnowledgeStatus(value)
    except ValueError as exc:
        raise EpistemicV2Error(f"unsupported {field_name}: {value}") from exc


def _sequence(value: object, *, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise EpistemicV2Error(f"{field_name} must be a sequence")
    return cast(Sequence[object], value)


@dataclass(frozen=True, slots=True)
class EvidenceEventRef:
    case_id: CaseId
    event_id: ContentAddress

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> EvidenceEventRef:
        raw_case = value.get("case_id")
        if not isinstance(raw_case, str):
            raise EpistemicV2Error("evidence case_id must be a string")
        return cls(
            case_id=CaseId(raw_case),
            event_id=_address(value.get("event_id"), field_name="evidence event_id"),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id.value,
            "event_id": self.event_id.canonical_dict(),
        }


@dataclass(frozen=True, slots=True)
class EpistemicPolicyV2:
    fact_evidence_event_types: tuple[str, ...]
    policy_identity: ContentAddress
    canonicalization_profile: CanonicalizationProfile = CanonicalizationProfile.LUKART_JSON_V1
    schema: str = EPISTEMIC_POLICY_SCHEMA_V2

    def __post_init__(self) -> None:
        if self.schema != EPISTEMIC_POLICY_SCHEMA_V2:
            raise EpistemicV2Error(f"unsupported epistemic policy schema: {self.schema}")
        if self.canonicalization_profile is not CanonicalizationProfile.LUKART_JSON_V1:
            raise EpistemicV2Error("unsupported epistemic canonicalization profile")
        normalized = tuple(
            sorted(
                _identifier(value, field_name="fact evidence event type")
                for value in self.fact_evidence_event_types
            )
        )
        if not normalized or len(normalized) != len(set(normalized)):
            raise EpistemicV2Error("fact evidence event types must be nonempty and unique")
        object.__setattr__(self, "fact_evidence_event_types", normalized)
        self.verify()

    @classmethod
    def reference(cls) -> EpistemicPolicyV2:
        event_types = tuple(sorted(DEFAULT_FACT_EVIDENCE_EVENT_TYPES))
        body = cls._body(event_types)
        return cls(
            fact_evidence_event_types=event_types,
            policy_identity=ContentAddress.for_value(body),
        )

    @staticmethod
    def _body(event_types: tuple[str, ...]) -> dict[str, object]:
        return {
            "schema": EPISTEMIC_POLICY_SCHEMA_V2,
            "canonicalization_profile": CANONICALIZATION_PROFILE_V1,
            "transition_policy": EpistemicStatusMachine.policy_document(),
            "fact_evidence_event_types": list(event_types),
            "authoritative_state_source": "canonical-case-ledger",
            "same_state_transition": "reject",
        }

    def canonical_body(self) -> dict[str, object]:
        return self._body(self.fact_evidence_event_types)

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "policy_identity": self.policy_identity.canonical_dict(),
        }

    def verify(self) -> None:
        if self.policy_identity != ContentAddress.for_value(self.canonical_body()):
            raise EpistemicV2Error("epistemic policy identity mismatch")


@dataclass(frozen=True, slots=True)
class Assertion:
    case_id: CaseId
    subject_id: ObjectId
    assertion_type: str
    content: Mapping[str, object]
    initial_status: KnowledgeStatus
    evidence_refs: tuple[EvidenceEventRef, ...]
    policy_identity: ContentAddress
    assertion_id: ContentAddress
    canonicalization_profile: CanonicalizationProfile = CanonicalizationProfile.LUKART_JSON_V1
    schema: str = ASSERTION_SCHEMA_V2

    def __post_init__(self) -> None:
        if self.schema != ASSERTION_SCHEMA_V2:
            raise EpistemicV2Error(f"unsupported assertion schema: {self.schema}")
        if self.canonicalization_profile is not CanonicalizationProfile.LUKART_JSON_V1:
            raise EpistemicV2Error("unsupported assertion canonicalization profile")
        object.__setattr__(
            self,
            "assertion_type",
            _identifier(self.assertion_type, field_name="assertion_type"),
        )
        object.__setattr__(
            self,
            "content",
            _canonical_mapping(self.content, field_name="assertion content"),
        )
        normalized = tuple(
            sorted(
                self.evidence_refs,
                key=lambda ref: (ref.case_id.value, str(ref.event_id)),
            )
        )
        ref_keys = {(ref.case_id.value, str(ref.event_id)) for ref in normalized}
        if len(ref_keys) != len(normalized):
            raise EpistemicV2Error("assertion evidence references must be unique")
        if self.initial_status is KnowledgeStatus.FACT and not normalized:
            raise EpistemicV2Error("initial FACT requires exact evidence references")
        if self.initial_status is KnowledgeStatus.REJECTED:
            raise EpistemicV2Error("an assertion cannot be created directly as REJECTED")
        object.__setattr__(self, "evidence_refs", normalized)
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        case_id: CaseId,
        subject_id: ObjectId,
        assertion_type: str,
        content: Mapping[str, object],
        initial_status: KnowledgeStatus,
        evidence_refs: tuple[EvidenceEventRef, ...],
        policy: EpistemicPolicyV2,
    ) -> Assertion:
        canonical_content = _canonical_mapping(content, field_name="assertion content")
        normalized_type = _identifier(assertion_type, field_name="assertion_type")
        normalized_refs = tuple(
            sorted(evidence_refs, key=lambda ref: (ref.case_id.value, str(ref.event_id)))
        )
        body = {
            "schema": ASSERTION_SCHEMA_V2,
            "canonicalization_profile": CANONICALIZATION_PROFILE_V1,
            "case_id": case_id.value,
            "subject_id": subject_id.value,
            "assertion_type": normalized_type,
            "content": canonical_content,
            "initial_status": initial_status.value,
            "evidence_refs": [ref.canonical_dict() for ref in normalized_refs],
            "policy_identity": policy.policy_identity.canonical_dict(),
        }
        return cls(
            case_id=case_id,
            subject_id=subject_id,
            assertion_type=normalized_type,
            content=canonical_content,
            initial_status=initial_status,
            evidence_refs=normalized_refs,
            policy_identity=policy.policy_identity,
            assertion_id=ContentAddress.for_value(body),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> Assertion:
        schema = value.get("schema")
        profile = value.get("canonicalization_profile")
        case_id = value.get("case_id")
        subject_id = value.get("subject_id")
        assertion_type = value.get("assertion_type")
        content = value.get("content")
        identity_fields = (schema, profile, case_id, subject_id, assertion_type)
        if not all(isinstance(item, str) for item in identity_fields):
            raise EpistemicV2Error("invalid assertion identity fields")
        if profile != CANONICALIZATION_PROFILE_V1:
            raise EpistemicV2Error(
                f"unsupported assertion canonicalization profile: {profile}"
            )
        if not isinstance(content, Mapping):
            raise EpistemicV2Error("assertion content must be an object")
        raw_refs = _sequence(
            value.get("evidence_refs"),
            field_name="assertion evidence_refs",
        )
        refs = tuple(
            EvidenceEventRef.from_dict(cast(Mapping[str, object], item))
            for item in raw_refs
            if isinstance(item, Mapping)
        )
        if len(refs) != len(raw_refs):
            raise EpistemicV2Error("assertion evidence_refs must contain objects")
        return cls(
            case_id=CaseId(cast(str, case_id)),
            subject_id=ObjectId(cast(str, subject_id)),
            assertion_type=cast(str, assertion_type),
            content=cast(Mapping[str, object], content),
            initial_status=_status(value.get("initial_status"), field_name="initial_status"),
            evidence_refs=refs,
            policy_identity=_address(
                value.get("policy_identity"),
                field_name="policy_identity",
            ),
            assertion_id=_address(value.get("assertion_id"), field_name="assertion_id"),
            schema=cast(str, schema),
        )

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "canonicalization_profile": self.canonicalization_profile.value,
            "case_id": self.case_id.value,
            "subject_id": self.subject_id.value,
            "assertion_type": self.assertion_type,
            "content": self.content,
            "initial_status": self.initial_status.value,
            "evidence_refs": [ref.canonical_dict() for ref in self.evidence_refs],
            "policy_identity": self.policy_identity.canonical_dict(),
        }

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "assertion_id": self.assertion_id.canonical_dict(),
        }

    def verify(self) -> None:
        if self.assertion_id != ContentAddress.for_value(self.canonical_body()):
            raise EpistemicV2Error("assertion content-address mismatch")


@dataclass(frozen=True, slots=True)
class EpistemicDecisionV2:
    assertion_id: ContentAddress
    source: KnowledgeStatus
    target: KnowledgeStatus
    evidence_refs: tuple[EvidenceEventRef, ...]
    rationale: str
    policy_identity: ContentAddress
    allowed: bool
    reason: str
    decision_id: ContentAddress
    schema: str = TRANSITION_DECISION_SCHEMA_V2

    def __post_init__(self) -> None:
        if self.schema != TRANSITION_DECISION_SCHEMA_V2:
            raise EpistemicV2Error(
                f"unsupported transition decision schema: {self.schema}"
            )
        object.__setattr__(self, "rationale", self.rationale.strip())
        object.__setattr__(
            self,
            "reason",
            _identifier(self.reason, field_name="decision reason"),
        )
        normalized = tuple(
            sorted(self.evidence_refs, key=lambda ref: (ref.case_id.value, str(ref.event_id)))
        )
        ref_keys = {(ref.case_id.value, str(ref.event_id)) for ref in normalized}
        if len(ref_keys) != len(normalized):
            raise EpistemicV2Error("transition evidence references must be unique")
        object.__setattr__(self, "evidence_refs", normalized)
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        assertion_id: ContentAddress,
        source: KnowledgeStatus,
        target: KnowledgeStatus,
        evidence_refs: tuple[EvidenceEventRef, ...],
        rationale: str,
        policy: EpistemicPolicyV2,
        allowed: bool,
        reason: str,
    ) -> EpistemicDecisionV2:
        normalized_refs = tuple(
            sorted(evidence_refs, key=lambda ref: (ref.case_id.value, str(ref.event_id)))
        )
        body = {
            "schema": TRANSITION_DECISION_SCHEMA_V2,
            "assertion_id": assertion_id.canonical_dict(),
            "source": source.value,
            "target": target.value,
            "evidence_refs": [ref.canonical_dict() for ref in normalized_refs],
            "rationale": rationale.strip(),
            "policy_identity": policy.policy_identity.canonical_dict(),
            "allowed": allowed,
            "reason": reason,
        }
        return cls(
            assertion_id=assertion_id,
            source=source,
            target=target,
            evidence_refs=normalized_refs,
            rationale=rationale,
            policy_identity=policy.policy_identity,
            allowed=allowed,
            reason=reason,
            decision_id=ContentAddress.for_value(body),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> EpistemicDecisionV2:
        schema = value.get("schema")
        allowed = value.get("allowed")
        reason = value.get("reason")
        rationale = value.get("rationale")
        if not isinstance(schema, str) or not isinstance(allowed, bool):
            raise EpistemicV2Error("transition decision schema/allowed fields are invalid")
        if not isinstance(reason, str) or not isinstance(rationale, str):
            raise EpistemicV2Error("transition decision reason/rationale fields are invalid")
        raw_refs = _sequence(
            value.get("evidence_refs"),
            field_name="transition evidence_refs",
        )
        refs: list[EvidenceEventRef] = []
        for raw_ref in raw_refs:
            if not isinstance(raw_ref, Mapping):
                raise EpistemicV2Error("transition evidence_refs must contain objects")
            refs.append(EvidenceEventRef.from_dict(cast(Mapping[str, object], raw_ref)))
        return cls(
            assertion_id=_address(value.get("assertion_id"), field_name="assertion_id"),
            source=_status(value.get("source"), field_name="transition source"),
            target=_status(value.get("target"), field_name="transition target"),
            evidence_refs=tuple(refs),
            rationale=rationale,
            policy_identity=_address(
                value.get("policy_identity"),
                field_name="policy_identity",
            ),
            allowed=allowed,
            reason=reason,
            decision_id=_address(value.get("decision_id"), field_name="decision_id"),
            schema=schema,
        )

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "assertion_id": self.assertion_id.canonical_dict(),
            "source": self.source.value,
            "target": self.target.value,
            "evidence_refs": [ref.canonical_dict() for ref in self.evidence_refs],
            "rationale": self.rationale,
            "policy_identity": self.policy_identity.canonical_dict(),
            "allowed": self.allowed,
            "reason": self.reason,
        }

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "decision_id": self.decision_id.canonical_dict(),
        }

    def verify(self) -> None:
        if self.decision_id != ContentAddress.for_value(self.canonical_body()):
            raise EpistemicV2Error("transition decision content-address mismatch")


@dataclass(frozen=True, slots=True)
class AssertionState:
    assertion_id: ContentAddress
    subject_id: ObjectId
    assertion_type: str
    status: KnowledgeStatus
    evidence_refs: tuple[EvidenceEventRef, ...]
    last_decision_id: ContentAddress | None = None

    def canonical_dict(self) -> dict[str, object]:
        return {
            "assertion_id": self.assertion_id.canonical_dict(),
            "subject_id": self.subject_id.value,
            "assertion_type": self.assertion_type,
            "status": self.status.value,
            "evidence_refs": [ref.canonical_dict() for ref in self.evidence_refs],
            "last_decision_id": (
                self.last_decision_id.canonical_dict()
                if self.last_decision_id
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class EpistemicProjectionV2:
    case_id: CaseId
    ledger_head: ContentAddress | None
    policy_identity: ContentAddress
    states: tuple[AssertionState, ...]
    projection_identity: ContentAddress
    schema: str = EPISTEMIC_PROJECTION_SCHEMA_V2

    @classmethod
    def build(
        cls,
        *,
        case_id: CaseId,
        events: tuple[LedgerEvent, ...],
        policy: EpistemicPolicyV2,
    ) -> EpistemicProjectionV2:
        machine = EpistemicStatusMachine()
        states: dict[str, AssertionState] = {}
        seen_events: dict[str, LedgerEvent] = {}

        for event in events:
            if event.case_id != case_id:
                raise EpistemicV2Error(
                    "epistemic projection received a foreign case event"
                )
            event_key = str(event.event_id)

            if event.event_type == ASSERTION_CREATED_EVENT_V1:
                raw = event.payload.get("assertion")
                if not isinstance(raw, Mapping):
                    raise EpistemicV2Error("assertion event payload is invalid")
                assertion = Assertion.from_dict(cast(Mapping[str, object], raw))
                identity_matches = (
                    assertion.case_id == case_id
                    and assertion.policy_identity == policy.policy_identity
                )
                if not identity_matches:
                    raise EpistemicV2Error("assertion case/policy identity mismatch")
                assertion_key = str(assertion.assertion_id)
                if assertion_key in states:
                    raise EpistemicV2Error("duplicate assertion identity in case history")
                cls._verify_evidence(
                    case_id=case_id,
                    refs=assertion.evidence_refs,
                    seen_events=seen_events,
                    policy=policy,
                    require_fact_evidence=assertion.initial_status
                    is KnowledgeStatus.FACT,
                )
                states[assertion_key] = AssertionState(
                    assertion_id=assertion.assertion_id,
                    subject_id=assertion.subject_id,
                    assertion_type=assertion.assertion_type,
                    status=assertion.initial_status,
                    evidence_refs=assertion.evidence_refs,
                )

            elif event.event_type == ASSERTION_TRANSITION_EVENT_V1:
                raw = event.payload.get("decision")
                if not isinstance(raw, Mapping):
                    raise EpistemicV2Error("transition event payload is invalid")
                decision = EpistemicDecisionV2.from_dict(
                    cast(Mapping[str, object], raw)
                )
                if not decision.allowed:
                    raise EpistemicV2Error(
                        "denied transition cannot be part of canonical history"
                    )
                if decision.policy_identity != policy.policy_identity:
                    raise EpistemicV2Error("transition policy identity mismatch")
                key = str(decision.assertion_id)
                current = states.get(key)
                if current is None:
                    raise EpistemicV2Error("transition references an unknown assertion")
                if current.status is not decision.source:
                    raise EpistemicV2Error(
                        "transition source does not match projected state"
                    )
                if decision.source is decision.target:
                    raise EpistemicV2Error("canonical transition cannot be a no-op")
                cls._verify_evidence(
                    case_id=case_id,
                    refs=decision.evidence_refs,
                    seen_events=seen_events,
                    policy=policy,
                    require_fact_evidence=decision.target is KnowledgeStatus.FACT,
                )
                recomputed = machine.decide(
                    EpistemicTransitionRequest(
                        source=decision.source,
                        target=decision.target,
                        evidence_refs=tuple(
                            str(ref.event_id) for ref in decision.evidence_refs
                        ),
                        rationale=decision.rationale,
                    )
                )
                if not recomputed.allowed or recomputed.reason != decision.reason:
                    raise EpistemicV2Error(
                        "recorded transition decision violates epistemic policy"
                    )
                states[key] = AssertionState(
                    assertion_id=current.assertion_id,
                    subject_id=current.subject_id,
                    assertion_type=current.assertion_type,
                    status=decision.target,
                    evidence_refs=decision.evidence_refs or current.evidence_refs,
                    last_decision_id=decision.decision_id,
                )

            elif event.event_type.startswith("epistemic."):
                raise EpistemicV2Error(
                    f"unknown epistemic event type: {event.event_type}"
                )

            seen_events[event_key] = event

        ordered = tuple(sorted(states.values(), key=lambda item: str(item.assertion_id)))
        ledger_head = events[-1].event_id if events else None
        body = {
            "schema": EPISTEMIC_PROJECTION_SCHEMA_V2,
            "case_id": case_id.value,
            "ledger_head": ledger_head.canonical_dict() if ledger_head else None,
            "policy_identity": policy.policy_identity.canonical_dict(),
            "states": [state.canonical_dict() for state in ordered],
        }
        return cls(
            case_id=case_id,
            ledger_head=ledger_head,
            policy_identity=policy.policy_identity,
            states=ordered,
            projection_identity=ContentAddress.for_value(body),
        )

    @staticmethod
    def _verify_evidence(
        *,
        case_id: CaseId,
        refs: tuple[EvidenceEventRef, ...],
        seen_events: Mapping[str, LedgerEvent],
        policy: EpistemicPolicyV2,
        require_fact_evidence: bool,
    ) -> None:
        if require_fact_evidence and not refs:
            raise EpistemicV2Error("FACT requires exact prior evidence events")
        for ref in refs:
            if ref.case_id != case_id:
                raise EpistemicV2Error(
                    "cross-case evidence requires a future explicit trust contract"
                )
            source = seen_events.get(str(ref.event_id))
            if source is None:
                raise EpistemicV2Error(
                    "evidence reference does not resolve to a prior CCL event"
                )
            if (
                require_fact_evidence
                and source.event_type not in policy.fact_evidence_event_types
            ):
                raise EpistemicV2Error(
                    "FACT evidence reference has an unauthorized event type"
                )

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id.value,
            "ledger_head": self.ledger_head.canonical_dict()
            if self.ledger_head
            else None,
            "policy_identity": self.policy_identity.canonical_dict(),
            "states": [state.canonical_dict() for state in self.states],
        }

    def verify(self) -> None:
        if self.projection_identity != ContentAddress.for_value(self.canonical_body()):
            raise EpistemicV2Error("epistemic projection identity mismatch")

    def get(self, assertion_id: ContentAddress) -> AssertionState | None:
        return next(
            (state for state in self.states if state.assertion_id == assertion_id),
            None,
        )


class EpistemicLedgerService:
    """Authorized epistemic write facade; all writes terminate in CanonicalCaseLedger."""

    def __init__(
        self,
        ledger: CanonicalCaseLedger,
        *,
        policy: EpistemicPolicyV2 | None = None,
    ) -> None:
        self._ledger = ledger
        self.policy = policy or EpistemicPolicyV2.reference()
        self._machine = EpistemicStatusMachine()

    def project(self, case_id: CaseId) -> EpistemicProjectionV2:
        projection = EpistemicProjectionV2.build(
            case_id=case_id,
            events=self._ledger.events(case_id),
            policy=self.policy,
        )
        projection.verify()
        return projection

    def create_assertion(
        self,
        *,
        case_id: CaseId,
        subject_id: ObjectId,
        assertion_type: str,
        content: Mapping[str, object],
        initial_status: KnowledgeStatus,
        evidence_refs: tuple[EvidenceEventRef, ...],
        runtime_identity: RuntimeIdentity,
        expected_head: ContentAddress | None,
    ) -> Assertion:
        events = self._ledger.events(case_id)
        actual_head = events[-1].event_id if events else None
        if actual_head != expected_head:
            raise EpistemicV2Error("epistemic create lost exact canonical ledger head")
        EpistemicProjectionV2._verify_evidence(
            case_id=case_id,
            refs=evidence_refs,
            seen_events={str(event.event_id): event for event in events},
            policy=self.policy,
            require_fact_evidence=initial_status is KnowledgeStatus.FACT,
        )
        assertion = Assertion.build(
            case_id=case_id,
            subject_id=subject_id,
            assertion_type=assertion_type,
            content=content,
            initial_status=initial_status,
            evidence_refs=evidence_refs,
            policy=self.policy,
        )
        self._ledger.append_event(
            case_id=case_id,
            event_type=ASSERTION_CREATED_EVENT_V1,
            runtime_identity=runtime_identity,
            payload={"assertion": assertion.canonical_dict()},
            expected_head=expected_head,
            object_id=subject_id,
        )
        return assertion

    def decide_transition(
        self,
        *,
        case_id: CaseId,
        assertion_id: ContentAddress,
        target: KnowledgeStatus,
        evidence_refs: tuple[EvidenceEventRef, ...] = (),
        rationale: str = "",
    ) -> EpistemicDecisionV2:
        events = self._ledger.events(case_id)
        projection = EpistemicProjectionV2.build(
            case_id=case_id,
            events=events,
            policy=self.policy,
        )
        state = projection.get(assertion_id)
        if state is None:
            raise EpistemicV2Error("unknown assertion identity")
        if state.status is target:
            return EpistemicDecisionV2.build(
                assertion_id=assertion_id,
                source=state.status,
                target=target,
                evidence_refs=evidence_refs,
                rationale=rationale,
                policy=self.policy,
                allowed=False,
                reason="canonical transition cannot be a no-op",
            )
        try:
            EpistemicProjectionV2._verify_evidence(
                case_id=case_id,
                refs=evidence_refs,
                seen_events={str(event.event_id): event for event in events},
                policy=self.policy,
                require_fact_evidence=target is KnowledgeStatus.FACT,
            )
        except EpistemicV2Error as exc:
            return EpistemicDecisionV2.build(
                assertion_id=assertion_id,
                source=state.status,
                target=target,
                evidence_refs=evidence_refs,
                rationale=rationale,
                policy=self.policy,
                allowed=False,
                reason=str(exc),
            )
        legacy = self._machine.decide(
            EpistemicTransitionRequest(
                source=state.status,
                target=target,
                evidence_refs=tuple(str(ref.event_id) for ref in evidence_refs),
                rationale=rationale,
            )
        )
        return EpistemicDecisionV2.build(
            assertion_id=assertion_id,
            source=state.status,
            target=target,
            evidence_refs=evidence_refs,
            rationale=rationale,
            policy=self.policy,
            allowed=legacy.allowed,
            reason=legacy.reason,
        )

    def transition(
        self,
        *,
        case_id: CaseId,
        assertion_id: ContentAddress,
        target: KnowledgeStatus,
        runtime_identity: RuntimeIdentity,
        expected_head: ContentAddress | None,
        evidence_refs: tuple[EvidenceEventRef, ...] = (),
        rationale: str = "",
    ) -> EpistemicDecisionV2:
        actual_head = self._ledger.head(case_id)
        if actual_head != expected_head:
            raise EpistemicV2Error(
                "epistemic transition lost exact canonical ledger head"
            )
        decision = self.decide_transition(
            case_id=case_id,
            assertion_id=assertion_id,
            target=target,
            evidence_refs=evidence_refs,
            rationale=rationale,
        )
        if not decision.allowed:
            raise EpistemicV2Error(decision.reason)
        state = self.project(case_id).get(assertion_id)
        if state is None:
            raise EpistemicV2Error("assertion disappeared before transition")
        self._ledger.append_event(
            case_id=case_id,
            event_type=ASSERTION_TRANSITION_EVENT_V1,
            runtime_identity=runtime_identity,
            payload={"decision": decision.canonical_dict()},
            expected_head=expected_head,
            object_id=state.subject_id,
        )
        return decision
