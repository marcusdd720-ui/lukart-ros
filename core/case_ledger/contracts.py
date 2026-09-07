"""Canonical Case Ledger v1 identity and immutable event contracts.

The ledger contract deliberately separates stable logical object identity from
content-addressed immutable revision and event identity.  It reuses the existing
P3 canonical JSON implementation as the only v1 canonicalization profile and
fails closed on unknown schema, canonicalization or digest identifiers.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import cast

from core.p3.contracts import P3ContractError, canonical_json, content_digest, require_hex_digest

CANONICALIZATION_PROFILE_V1 = "lukart.canonical-json.v1"
OBJECT_REVISION_SCHEMA_V1 = "lukart.object-revision.v1"
LEDGER_EVENT_SCHEMA_V1 = "lukart.canonical-case-ledger-event.v1"
LEDGER_BUNDLE_SCHEMA_V1 = "lukart.canonical-case-ledger-bundle.v1"


class CaseLedgerContractError(P3ContractError):
    """Fail-closed violation of the canonical ledger or object identity contract."""


class DigestAlgorithm(StrEnum):
    SHA256 = "sha256"


class CanonicalizationProfile(StrEnum):
    LUKART_JSON_V1 = CANONICALIZATION_PROFILE_V1


def _require_exact_identifier(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise CaseLedgerContractError(f"{field_name} must be nonblank and already canonical")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CaseLedgerContractError(f"{field_name} cannot contain control characters")
    return value


def _require_schema_token(value: str, *, field_name: str) -> str:
    return _require_exact_identifier(value, field_name=field_name)


def _freeze_json(value: object) -> object:
    if isinstance(value, dict):
        frozen = {str(key): _freeze_json(item) for key, item in value.items()}
        return MappingProxyType(frozen)
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _canonical_mapping(value: Mapping[str, object], *, field_name: str) -> Mapping[str, object]:
    try:
        decoded: object = json.loads(canonical_json(dict(value)))
    except (TypeError, ValueError, P3ContractError) as exc:
        raise CaseLedgerContractError(f"{field_name} is not canonically serializable") from exc
    if not isinstance(decoded, dict):
        raise CaseLedgerContractError(f"{field_name} must be a mapping")
    if any(not isinstance(key, str) for key in decoded):
        raise CaseLedgerContractError(f"{field_name} keys must be strings")
    frozen = _freeze_json(decoded)
    if not isinstance(frozen, Mapping):
        raise CaseLedgerContractError(f"{field_name} must remain a mapping")
    return cast(Mapping[str, object], frozen)


@dataclass(frozen=True, slots=True)
class CaseId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _require_exact_identifier(self.value, field_name="case_id"),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {"value": self.value}


@dataclass(frozen=True, slots=True)
class ObjectId:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _require_exact_identifier(self.value, field_name="object_id"),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {"value": self.value}


@dataclass(frozen=True, slots=True)
class ContentAddress:
    algorithm: DigestAlgorithm
    digest: str

    def __post_init__(self) -> None:
        if self.algorithm is not DigestAlgorithm.SHA256:
            raise CaseLedgerContractError(f"unsupported digest algorithm: {self.algorithm}")
        object.__setattr__(
            self,
            "digest",
            require_hex_digest(self.digest, field_name="content_address_digest"),
        )

    @classmethod
    def for_value(
        cls,
        value: object,
        *,
        algorithm: DigestAlgorithm = DigestAlgorithm.SHA256,
    ) -> ContentAddress:
        if algorithm is not DigestAlgorithm.SHA256:
            raise CaseLedgerContractError(f"unsupported digest algorithm: {algorithm}")
        return cls(algorithm=algorithm, digest=content_digest(value))

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ContentAddress:
        raw_algorithm = value.get("algorithm")
        raw_digest = value.get("digest")
        if not isinstance(raw_algorithm, str) or not isinstance(raw_digest, str):
            raise CaseLedgerContractError("content address requires algorithm and digest")
        try:
            algorithm = DigestAlgorithm(raw_algorithm)
        except ValueError as exc:
            raise CaseLedgerContractError(
                f"unsupported digest algorithm: {raw_algorithm}"
            ) from exc
        return cls(algorithm=algorithm, digest=raw_digest)

    def canonical_dict(self) -> dict[str, object]:
        return {"algorithm": self.algorithm.value, "digest": self.digest}

    def __str__(self) -> str:
        return f"{self.algorithm.value}:{self.digest}"


@dataclass(frozen=True, slots=True)
class ObjectRevision:
    object_id: ObjectId
    schema_version: str
    content: Mapping[str, object]
    revision_id: ContentAddress
    canonicalization_profile: CanonicalizationProfile = CanonicalizationProfile.LUKART_JSON_V1
    schema: str = OBJECT_REVISION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != OBJECT_REVISION_SCHEMA_V1:
            raise CaseLedgerContractError(f"unsupported object revision schema: {self.schema}")
        if self.canonicalization_profile is not CanonicalizationProfile.LUKART_JSON_V1:
            raise CaseLedgerContractError(
                f"unsupported canonicalization profile: {self.canonicalization_profile}"
            )
        object.__setattr__(
            self,
            "schema_version",
            _require_schema_token(self.schema_version, field_name="object schema_version"),
        )
        object.__setattr__(
            self,
            "content",
            _canonical_mapping(self.content, field_name="object revision content"),
        )
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        object_id: ObjectId,
        schema_version: str,
        content: Mapping[str, object],
    ) -> ObjectRevision:
        copied = _canonical_mapping(content, field_name="object revision content")
        normalized_version = _require_schema_token(
            schema_version,
            field_name="object schema_version",
        )
        body = {
            "schema": OBJECT_REVISION_SCHEMA_V1,
            "canonicalization_profile": CANONICALIZATION_PROFILE_V1,
            "object_id": object_id.value,
            "schema_version": normalized_version,
            "content": copied,
        }
        return cls(
            object_id=object_id,
            schema_version=normalized_version,
            content=copied,
            revision_id=ContentAddress.for_value(body),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ObjectRevision:
        schema = value.get("schema")
        profile = value.get("canonicalization_profile")
        object_id = value.get("object_id")
        schema_version = value.get("schema_version")
        content = value.get("content")
        revision_id = value.get("revision_id")
        if not all(isinstance(item, str) for item in (schema, profile, object_id, schema_version)):
            raise CaseLedgerContractError("invalid object revision identity fields")
        if not isinstance(content, Mapping) or not isinstance(revision_id, Mapping):
            raise CaseLedgerContractError("invalid object revision content or revision_id")
        try:
            canonicalization_profile = CanonicalizationProfile(cast(str, profile))
        except ValueError as exc:
            raise CaseLedgerContractError(
                f"unsupported canonicalization profile: {profile}"
            ) from exc
        return cls(
            object_id=ObjectId(cast(str, object_id)),
            schema_version=cast(str, schema_version),
            content=cast(Mapping[str, object], content),
            revision_id=ContentAddress.from_dict(cast(Mapping[str, object], revision_id)),
            canonicalization_profile=canonicalization_profile,
            schema=cast(str, schema),
        )

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "canonicalization_profile": self.canonicalization_profile.value,
            "object_id": self.object_id.value,
            "schema_version": self.schema_version,
            "content": self.content,
        }

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "revision_id": self.revision_id.canonical_dict()}

    def verify(self) -> None:
        expected = ContentAddress.for_value(self.canonical_body())
        if self.revision_id != expected:
            raise CaseLedgerContractError("object revision content-address mismatch")


@dataclass(frozen=True, slots=True)
class LedgerEvent:
    case_id: CaseId
    case_sequence: int
    event_type: str
    runtime_identity_digest: ContentAddress
    payload: Mapping[str, object]
    event_id: ContentAddress
    previous_event_id: ContentAddress | None = None
    object_id: ObjectId | None = None
    revision_id: ContentAddress | None = None
    canonicalization_profile: CanonicalizationProfile = CanonicalizationProfile.LUKART_JSON_V1
    schema: str = LEDGER_EVENT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != LEDGER_EVENT_SCHEMA_V1:
            raise CaseLedgerContractError(f"unsupported ledger event schema: {self.schema}")
        if self.canonicalization_profile is not CanonicalizationProfile.LUKART_JSON_V1:
            raise CaseLedgerContractError(
                f"unsupported canonicalization profile: {self.canonicalization_profile}"
            )
        if self.case_sequence < 0:
            raise CaseLedgerContractError("case_sequence cannot be negative")
        if self.case_sequence == 0 and self.previous_event_id is not None:
            raise CaseLedgerContractError("genesis case event cannot have previous_event_id")
        if self.case_sequence > 0 and self.previous_event_id is None:
            raise CaseLedgerContractError("non-genesis case event requires previous_event_id")
        object.__setattr__(
            self,
            "event_type",
            _require_exact_identifier(self.event_type, field_name="event_type"),
        )
        object.__setattr__(
            self,
            "payload",
            _canonical_mapping(self.payload, field_name="ledger event payload"),
        )
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        case_id: CaseId,
        case_sequence: int,
        event_type: str,
        runtime_identity_digest: ContentAddress,
        payload: Mapping[str, object],
        previous_event_id: ContentAddress | None,
        object_id: ObjectId | None = None,
        revision_id: ContentAddress | None = None,
    ) -> LedgerEvent:
        copied = _canonical_mapping(payload, field_name="ledger event payload")
        normalized_type = _require_exact_identifier(event_type, field_name="event_type")
        body = {
            "schema": LEDGER_EVENT_SCHEMA_V1,
            "canonicalization_profile": CANONICALIZATION_PROFILE_V1,
            "case_id": case_id.value,
            "case_sequence": case_sequence,
            "event_type": normalized_type,
            "object_id": object_id.value if object_id is not None else None,
            "revision_id": revision_id.canonical_dict() if revision_id is not None else None,
            "runtime_identity_digest": runtime_identity_digest.canonical_dict(),
            "payload": copied,
            "previous_event_id": (
                previous_event_id.canonical_dict() if previous_event_id is not None else None
            ),
        }
        return cls(
            case_id=case_id,
            case_sequence=case_sequence,
            event_type=normalized_type,
            runtime_identity_digest=runtime_identity_digest,
            payload=copied,
            event_id=ContentAddress.for_value(body),
            previous_event_id=previous_event_id,
            object_id=object_id,
            revision_id=revision_id,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> LedgerEvent:
        schema = value.get("schema")
        profile = value.get("canonicalization_profile")
        case_id = value.get("case_id")
        case_sequence = value.get("case_sequence")
        event_type = value.get("event_type")
        object_id = value.get("object_id")
        revision_id = value.get("revision_id")
        runtime_digest = value.get("runtime_identity_digest")
        payload = value.get("payload")
        previous_event_id = value.get("previous_event_id")
        event_id = value.get("event_id")
        if not isinstance(schema, str) or not isinstance(profile, str):
            raise CaseLedgerContractError("ledger event schema/profile are required")
        if not isinstance(case_id, str) or not isinstance(event_type, str):
            raise CaseLedgerContractError("ledger event case_id/event_type are required")
        if not isinstance(case_sequence, int) or isinstance(case_sequence, bool):
            raise CaseLedgerContractError("ledger event case_sequence must be an integer")
        if object_id is not None and not isinstance(object_id, str):
            raise CaseLedgerContractError("ledger event object_id must be a string or null")
        if revision_id is not None and not isinstance(revision_id, Mapping):
            raise CaseLedgerContractError("ledger event revision_id must be an object or null")
        if not isinstance(runtime_digest, Mapping) or not isinstance(payload, Mapping):
            raise CaseLedgerContractError("ledger event runtime digest/payload are invalid")
        if previous_event_id is not None and not isinstance(previous_event_id, Mapping):
            raise CaseLedgerContractError("previous_event_id must be an object or null")
        if not isinstance(event_id, Mapping):
            raise CaseLedgerContractError("event_id must be an object")
        try:
            canonicalization_profile = CanonicalizationProfile(profile)
        except ValueError as exc:
            raise CaseLedgerContractError(
                f"unsupported canonicalization profile: {profile}"
            ) from exc
        return cls(
            case_id=CaseId(case_id),
            case_sequence=case_sequence,
            event_type=event_type,
            object_id=ObjectId(object_id) if object_id is not None else None,
            revision_id=(
                ContentAddress.from_dict(cast(Mapping[str, object], revision_id))
                if revision_id is not None
                else None
            ),
            runtime_identity_digest=ContentAddress.from_dict(
                cast(Mapping[str, object], runtime_digest)
            ),
            payload=cast(Mapping[str, object], payload),
            previous_event_id=(
                ContentAddress.from_dict(cast(Mapping[str, object], previous_event_id))
                if previous_event_id is not None
                else None
            ),
            event_id=ContentAddress.from_dict(cast(Mapping[str, object], event_id)),
            canonicalization_profile=canonicalization_profile,
            schema=schema,
        )

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "canonicalization_profile": self.canonicalization_profile.value,
            "case_id": self.case_id.value,
            "case_sequence": self.case_sequence,
            "event_type": self.event_type,
            "object_id": self.object_id.value if self.object_id is not None else None,
            "revision_id": self.revision_id.canonical_dict() if self.revision_id else None,
            "runtime_identity_digest": self.runtime_identity_digest.canonical_dict(),
            "payload": self.payload,
            "previous_event_id": (
                self.previous_event_id.canonical_dict()
                if self.previous_event_id is not None
                else None
            ),
        }

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "event_id": self.event_id.canonical_dict()}

    def verify(self) -> None:
        expected = ContentAddress.for_value(self.canonical_body())
        if self.event_id != expected:
            raise CaseLedgerContractError("ledger event content-address mismatch")


@dataclass(frozen=True, slots=True)
class CaseLedgerBundle:
    case_id: CaseId
    events: tuple[LedgerEvent, ...]
    bundle_digest: ContentAddress
    canonicalization_profile: CanonicalizationProfile = CanonicalizationProfile.LUKART_JSON_V1
    schema: str = LEDGER_BUNDLE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != LEDGER_BUNDLE_SCHEMA_V1:
            raise CaseLedgerContractError(f"unsupported ledger bundle schema: {self.schema}")
        if self.canonicalization_profile is not CanonicalizationProfile.LUKART_JSON_V1:
            raise CaseLedgerContractError(
                f"unsupported canonicalization profile: {self.canonicalization_profile}"
            )
        self.verify()

    @classmethod
    def build(cls, *, case_id: CaseId, events: tuple[LedgerEvent, ...]) -> CaseLedgerBundle:
        body = cls._body(case_id=case_id, events=events)
        return cls(
            case_id=case_id,
            events=events,
            bundle_digest=ContentAddress.for_value(body),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> CaseLedgerBundle:
        schema = value.get("schema")
        profile = value.get("canonicalization_profile")
        case_id = value.get("case_id")
        events = value.get("events")
        bundle_digest = value.get("bundle_digest")
        if not isinstance(schema, str) or not isinstance(profile, str):
            raise CaseLedgerContractError("ledger bundle schema/profile are required")
        if not isinstance(case_id, str) or not isinstance(events, list):
            raise CaseLedgerContractError("ledger bundle case_id/events are invalid")
        if not isinstance(bundle_digest, Mapping):
            raise CaseLedgerContractError("ledger bundle digest is required")
        parsed_events: list[LedgerEvent] = []
        for raw_event in events:
            if not isinstance(raw_event, Mapping):
                raise CaseLedgerContractError("ledger bundle events must be objects")
            parsed_events.append(LedgerEvent.from_dict(cast(Mapping[str, object], raw_event)))
        try:
            canonicalization_profile = CanonicalizationProfile(profile)
        except ValueError as exc:
            raise CaseLedgerContractError(
                f"unsupported canonicalization profile: {profile}"
            ) from exc
        return cls(
            case_id=CaseId(case_id),
            events=tuple(parsed_events),
            bundle_digest=ContentAddress.from_dict(
                cast(Mapping[str, object], bundle_digest)
            ),
            canonicalization_profile=canonicalization_profile,
            schema=schema,
        )

    @staticmethod
    def _body(*, case_id: CaseId, events: tuple[LedgerEvent, ...]) -> dict[str, object]:
        head = events[-1].event_id.canonical_dict() if events else None
        return {
            "schema": LEDGER_BUNDLE_SCHEMA_V1,
            "canonicalization_profile": CANONICALIZATION_PROFILE_V1,
            "case_id": case_id.value,
            "event_count": len(events),
            "head_event_id": head,
            "events": [event.canonical_dict() for event in events],
        }

    @property
    def head_event_id(self) -> ContentAddress | None:
        return self.events[-1].event_id if self.events else None

    def canonical_body(self) -> dict[str, object]:
        return self._body(case_id=self.case_id, events=self.events)

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "bundle_digest": self.bundle_digest.canonical_dict()}

    def verify(self) -> None:
        previous: ContentAddress | None = None
        for expected_sequence, event in enumerate(self.events):
            event.verify()
            if event.case_id != self.case_id:
                raise CaseLedgerContractError("ledger bundle contains a different case_id")
            if event.case_sequence != expected_sequence:
                raise CaseLedgerContractError("ledger bundle case sequence discontinuity")
            if event.previous_event_id != previous:
                raise CaseLedgerContractError("ledger bundle event chain mismatch")
            previous = event.event_id
        expected = ContentAddress.for_value(self.canonical_body())
        if self.bundle_digest != expected:
            raise CaseLedgerContractError("ledger bundle content-address mismatch")
