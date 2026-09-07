"""Canonical Case Ledger v1 over the existing Enterprise durable provenance backend.

This module is the logical write authority for canonical case history.  It does
not introduce a third persistence system: the existing SQLiteProvenanceStore is
used strictly as the transactional durability backend.  Canonical event identity
is backend-independent and is verified separately from the backend hash chain.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from threading import RLock

from core.enterprise.contracts import EnterpriseContractError
from core.enterprise.durability import DurableRecord, SQLiteProvenanceStore
from core.p3.contracts import RuntimeIdentity, canonical_json

from .contracts import (
    CaseId,
    CaseLedgerBundle,
    CaseLedgerContractError,
    ContentAddress,
    DigestAlgorithm,
    LedgerEvent,
    ObjectId,
    ObjectRevision,
)

_BACKEND_GENESIS = "0" * 64
_STREAM_PREFIX = "canonical-case-ledger:"
_BACKEND_EVENT_TYPE = "canonical.case-ledger.event.v1"
OBJECT_REVISION_PUBLISHED_V1 = "object.revision.published.v1"
DEFAULT_MAX_CASE_EVENTS = 10_000


class CanonicalCaseLedger:
    """Single authoritative append-only case ledger with exact-head writes.

    Each case has an independent canonical event chain.  The underlying durable
    backend may contain multiple case streams and therefore maintains its own
    global tamper-evident record chain.  A write succeeds only when both the
    caller-provided canonical case head and the exact backend stream head still
    match the snapshot used to build the new event.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._store = SQLiteProvenanceStore(self.path)
        self._lock = RLock()

    def close(self) -> None:
        self._store.close()

    def __enter__(self) -> CanonicalCaseLedger:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @staticmethod
    def _stream_id(case_id: CaseId) -> str:
        return f"{_STREAM_PREFIX}{case_id.value}"

    @staticmethod
    def _runtime_address(runtime_identity: RuntimeIdentity) -> ContentAddress:
        return ContentAddress(
            algorithm=DigestAlgorithm.SHA256,
            digest=runtime_identity.digest(),
        )

    @staticmethod
    def _validate_limit(max_events: int) -> int:
        if max_events < 1:
            raise CaseLedgerContractError("max_events must be positive")
        return max_events

    @staticmethod
    def _decode_case_records(
        *,
        case_id: CaseId,
        records: tuple[DurableRecord, ...],
        max_events: int,
    ) -> tuple[LedgerEvent, ...]:
        if len(records) > max_events:
            raise CaseLedgerContractError("canonical case ledger event limit exceeded")
        expected_previous: ContentAddress | None = None
        events: list[LedgerEvent] = []
        for expected_sequence, record in enumerate(records):
            if record.event_type != _BACKEND_EVENT_TYPE:
                raise CaseLedgerContractError(
                    "non-canonical record detected inside canonical case stream"
                )
            event = LedgerEvent.from_dict(record.payload)
            if event.case_id != case_id:
                raise CaseLedgerContractError("canonical case stream contains wrong case_id")
            if event.case_sequence != expected_sequence:
                raise CaseLedgerContractError("canonical case sequence discontinuity")
            if event.previous_event_id != expected_previous:
                raise CaseLedgerContractError("canonical case event chain mismatch")
            events.append(event)
            expected_previous = event.event_id
        return tuple(events)

    def _snapshot(
        self,
        case_id: CaseId,
        *,
        max_events: int,
    ) -> tuple[tuple[LedgerEvent, ...], str]:
        limit = self._validate_limit(max_events)
        stream_id = self._stream_id(case_id)
        try:
            verified = self._store.verify()
        except EnterpriseContractError as exc:
            raise CaseLedgerContractError("durable backend verification failed") from exc
        matching = tuple(record for record in verified if record.stream_id == stream_id)
        events = self._decode_case_records(
            case_id=case_id,
            records=matching,
            max_events=limit,
        )
        backend_head = matching[-1].record_digest if matching else _BACKEND_GENESIS
        return events, backend_head

    @staticmethod
    def _verified_export(
        value: Mapping[str, object],
        *,
        max_events: int | None = None,
    ) -> CaseLedgerBundle:
        """Parse one serialized bundle and reject any unbound serialized fields."""

        raw_events = value.get("events")
        if not isinstance(raw_events, list):
            raise CaseLedgerContractError("ledger bundle events are invalid")
        if max_events is not None and len(raw_events) > max_events:
            raise CaseLedgerContractError("canonical case ledger event limit exceeded")

        bundle = CaseLedgerBundle.from_dict(value)
        try:
            serialized = canonical_json(dict(value))
            reconstructed = canonical_json(bundle.canonical_dict())
        except (TypeError, ValueError) as exc:
            raise CaseLedgerContractError("ledger bundle is not canonically serializable") from exc
        if serialized != reconstructed:
            raise CaseLedgerContractError(
                "serialized ledger bundle contains unbound or inconsistent fields"
            )
        return bundle

    def events(
        self,
        case_id: CaseId,
        *,
        max_events: int = DEFAULT_MAX_CASE_EVENTS,
    ) -> tuple[LedgerEvent, ...]:
        events, _backend_head = self._snapshot(case_id, max_events=max_events)
        return events

    def head(
        self,
        case_id: CaseId,
        *,
        max_events: int = DEFAULT_MAX_CASE_EVENTS,
    ) -> ContentAddress | None:
        events = self.events(case_id, max_events=max_events)
        return events[-1].event_id if events else None

    def append_event(
        self,
        *,
        case_id: CaseId,
        event_type: str,
        runtime_identity: RuntimeIdentity,
        payload: Mapping[str, object],
        expected_head: ContentAddress | None,
        object_id: ObjectId | None = None,
        revision_id: ContentAddress | None = None,
        max_events: int = DEFAULT_MAX_CASE_EVENTS,
    ) -> LedgerEvent:
        """Append exactly one immutable event or fail without accepting stale state."""

        limit = self._validate_limit(max_events)
        if revision_id is not None and object_id is None:
            raise CaseLedgerContractError("revision_id requires object_id")

        with self._lock:
            events, backend_head = self._snapshot(case_id, max_events=limit)
            actual_head = events[-1].event_id if events else None
            if actual_head != expected_head:
                raise CaseLedgerContractError("canonical case head mismatch")
            if len(events) >= limit:
                raise CaseLedgerContractError("canonical case ledger event limit exceeded")

            event = LedgerEvent.build(
                case_id=case_id,
                case_sequence=len(events),
                event_type=event_type,
                runtime_identity_digest=self._runtime_address(runtime_identity),
                payload=payload,
                previous_event_id=actual_head,
                object_id=object_id,
                revision_id=revision_id,
            )
            try:
                self._store.append(
                    stream_id=self._stream_id(case_id),
                    event_type=_BACKEND_EVENT_TYPE,
                    payload=event.canonical_dict(),
                    expected_stream_head=backend_head,
                )
            except EnterpriseContractError as exc:
                raise CaseLedgerContractError(
                    "canonical case append lost exact backend head"
                ) from exc

            verified, _new_backend_head = self._snapshot(case_id, max_events=limit)
            if len(verified) != len(events) + 1 or verified[-1] != event:
                raise CaseLedgerContractError("canonical case append verification mismatch")
            return event

    def publish_revision(
        self,
        *,
        case_id: CaseId,
        revision: ObjectRevision,
        runtime_identity: RuntimeIdentity,
        expected_head: ContentAddress | None,
        max_events: int = DEFAULT_MAX_CASE_EVENTS,
    ) -> LedgerEvent:
        """Publish one immutable object revision into the authoritative case history."""

        revision.verify()
        return self.append_event(
            case_id=case_id,
            event_type=OBJECT_REVISION_PUBLISHED_V1,
            runtime_identity=runtime_identity,
            payload={"revision": revision.canonical_dict()},
            expected_head=expected_head,
            object_id=revision.object_id,
            revision_id=revision.revision_id,
            max_events=max_events,
        )

    def export_case(
        self,
        case_id: CaseId,
        *,
        max_events: int = DEFAULT_MAX_CASE_EVENTS,
    ) -> CaseLedgerBundle:
        """Create a content-addressed bundle verifiable without the database file."""

        return CaseLedgerBundle.build(
            case_id=case_id,
            events=self.events(case_id, max_events=max_events),
        )

    def restore_case(
        self,
        case_id: CaseId,
        value: Mapping[str, object],
        *,
        max_events: int = DEFAULT_MAX_CASE_EVENTS,
    ) -> CaseLedgerBundle:
        """Atomically restore one verified portable bundle into an empty case stream.

        Canonical event identities are preserved exactly.  Backend record identities
        are intentionally regenerated because they belong to the durability layer,
        not to the Product epistemic authority.  Existing target case history is
        never merged or overwritten.
        """

        limit = self._validate_limit(max_events)
        bundle = self._verified_export(value, max_events=limit)
        if bundle.case_id != case_id:
            raise CaseLedgerContractError("restore bundle case_id does not match target case_id")

        stream_id = self._stream_id(case_id)
        with self._lock:
            existing, backend_head = self._snapshot(case_id, max_events=limit)
            if existing:
                raise CaseLedgerContractError("restore target case stream is not empty")

            if bundle.events:
                batch = tuple(
                    (stream_id, _BACKEND_EVENT_TYPE, event.canonical_dict())
                    for event in bundle.events
                )
                try:
                    inserted = self._store.append_batch(
                        batch,
                        expected_stream_heads={stream_id: backend_head},
                    )
                except Exception as exc:
                    raise CaseLedgerContractError(
                        "canonical case restore transaction failed"
                    ) from exc
                if len(inserted) != len(bundle.events):
                    raise CaseLedgerContractError("canonical case restore record-count mismatch")

            restored = self.export_case(case_id, max_events=limit)
            if restored != bundle:
                raise CaseLedgerContractError("canonical case restore verification mismatch")
            return restored

    @staticmethod
    def verify_export(value: Mapping[str, object]) -> CaseLedgerBundle:
        """Fail-closed offline verification of a serialized case bundle."""

        return CanonicalCaseLedger._verified_export(value)
