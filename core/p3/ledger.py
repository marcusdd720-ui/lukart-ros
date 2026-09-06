"""P3-02 persistent append-only replay and provenance ledger."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from .contracts import P3ContractError, RuntimeIdentity, canonical_json, content_digest

_GENESIS = "0" * 64


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    sequence: int
    case_id: str
    event_type: str
    runtime_identity_digest: str
    payload: Mapping[str, object]
    payload_digest: str
    previous_record_digest: str
    record_digest: str

    def canonical_body(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "case_id": self.case_id,
            "event_type": self.event_type,
            "runtime_identity_digest": self.runtime_identity_digest,
            "payload": dict(self.payload),
            "payload_digest": self.payload_digest,
            "previous_record_digest": self.previous_record_digest,
        }

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "record_digest": self.record_digest}

    @classmethod
    def build(
        cls,
        *,
        sequence: int,
        case_id: str,
        event_type: str,
        runtime_identity: RuntimeIdentity,
        payload: Mapping[str, object],
        previous_record_digest: str,
    ) -> ProvenanceRecord:
        if sequence < 0:
            raise P3ContractError("provenance sequence cannot be negative")
        case_id = case_id.strip()
        event_type = event_type.strip()
        if not case_id or not event_type:
            raise P3ContractError("case_id and event_type are required")
        if len(previous_record_digest) != 64:
            raise P3ContractError("previous record digest must be SHA-256")
        copied = dict(payload)
        payload_digest = content_digest(copied)
        body = {
            "sequence": sequence,
            "case_id": case_id,
            "event_type": event_type,
            "runtime_identity_digest": runtime_identity.digest(),
            "payload": copied,
            "payload_digest": payload_digest,
            "previous_record_digest": previous_record_digest,
        }
        return cls(
            sequence=sequence,
            case_id=case_id,
            event_type=event_type,
            runtime_identity_digest=runtime_identity.digest(),
            payload=copied,
            payload_digest=payload_digest,
            previous_record_digest=previous_record_digest,
            record_digest=content_digest(body),
        )


class AppendOnlyReplayLedger:
    """JSONL hash-chain ledger.

    A record is serialized to one canonical line and appended with one OS write.
    The class is thread-safe within a process.  Multi-process deployments must
    place a single-writer service or external transactional store in front of it.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = RLock()

    def _decode(self, raw: str) -> ProvenanceRecord:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise P3ContractError("corrupt provenance JSON") from exc
        if not isinstance(parsed, dict):
            raise P3ContractError("provenance record must be an object")
        payload = parsed.get("payload")
        if not isinstance(payload, dict):
            raise P3ContractError("provenance payload must be an object")
        try:
            return ProvenanceRecord(
                sequence=int(parsed["sequence"]),
                case_id=str(parsed["case_id"]),
                event_type=str(parsed["event_type"]),
                runtime_identity_digest=str(parsed["runtime_identity_digest"]),
                payload=payload,
                payload_digest=str(parsed["payload_digest"]),
                previous_record_digest=str(parsed["previous_record_digest"]),
                record_digest=str(parsed["record_digest"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise P3ContractError("invalid provenance record schema") from exc

    def records(self) -> tuple[ProvenanceRecord, ...]:
        if not self.path.exists():
            return ()
        raw = self.path.read_text(encoding="utf-8")
        if raw and not raw.endswith("\n"):
            raise P3ContractError("partial provenance write detected")
        return tuple(self._decode(line) for line in raw.splitlines() if line)

    def verify(self) -> tuple[ProvenanceRecord, ...]:
        records = self.records()
        previous = _GENESIS
        for expected_sequence, record in enumerate(records):
            if record.sequence != expected_sequence:
                raise P3ContractError("provenance sequence discontinuity")
            if record.previous_record_digest != previous:
                raise P3ContractError("provenance hash-chain mismatch")
            if record.payload_digest != content_digest(record.payload):
                raise P3ContractError("provenance payload digest mismatch")
            if record.record_digest != content_digest(record.canonical_body()):
                raise P3ContractError("provenance record digest mismatch")
            previous = record.record_digest
        return records

    def append(
        self,
        *,
        case_id: str,
        event_type: str,
        runtime_identity: RuntimeIdentity,
        payload: Mapping[str, object],
    ) -> ProvenanceRecord:
        with self._lock:
            records = self.verify()
            previous = records[-1].record_digest if records else _GENESIS
            record = ProvenanceRecord.build(
                sequence=len(records),
                case_id=case_id,
                event_type=event_type,
                runtime_identity=runtime_identity,
                payload=payload,
                previous_record_digest=previous,
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = (canonical_json(record.canonical_dict()) + "\n").encode("utf-8")
            flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
            descriptor = os.open(self.path, flags, 0o600)
            try:
                written = os.write(descriptor, data)
                if written != len(data):
                    raise P3ContractError("partial provenance append")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            self.verify()
            return record

    def head_digest(self) -> str:
        records = self.verify()
        return records[-1].record_digest if records else _GENESIS
