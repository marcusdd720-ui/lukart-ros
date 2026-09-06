"""E6 transactional provenance, backup and recovery controls."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from core.p3.contracts import canonical_json, content_digest

from .contracts import EnterpriseContractError

_GENESIS = "0" * 64


@dataclass(frozen=True, slots=True)
class DurableRecord:
    sequence: int
    stream_id: str
    event_type: str
    payload: Mapping[str, object]
    payload_digest: str
    previous_digest: str
    record_digest: str

    def canonical_body(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "stream_id": self.stream_id,
            "event_type": self.event_type,
            "payload": dict(self.payload),
            "payload_digest": self.payload_digest,
            "previous_digest": self.previous_digest,
        }


class SQLiteProvenanceStore:
    """Single-file transactional ledger with WAL, FULL sync and hash-chain verification."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS provenance (
                sequence INTEGER PRIMARY KEY,
                stream_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_digest TEXT NOT NULL,
                previous_digest TEXT NOT NULL,
                record_digest TEXT NOT NULL UNIQUE
            )
            """
        )

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> SQLiteProvenanceStore:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @staticmethod
    def _decode_row(row: tuple[object, ...]) -> DurableRecord:
        sequence, stream_id, event_type, payload_json, payload_digest, previous, record = row
        if not isinstance(sequence, int):
            raise EnterpriseContractError("durable provenance sequence must be an integer")
        try:
            payload = json.loads(str(payload_json))
        except json.JSONDecodeError as exc:
            raise EnterpriseContractError("corrupt durable provenance payload JSON") from exc
        if not isinstance(payload, dict):
            raise EnterpriseContractError("durable provenance payload must be an object")
        return DurableRecord(
            sequence=sequence,
            stream_id=str(stream_id),
            event_type=str(event_type),
            payload=payload,
            payload_digest=str(payload_digest),
            previous_digest=str(previous),
            record_digest=str(record),
        )

    def records(self) -> tuple[DurableRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT sequence, stream_id, event_type, payload_json, payload_digest,
                   previous_digest, record_digest
            FROM provenance ORDER BY sequence ASC
            """
        ).fetchall()
        return tuple(self._decode_row(tuple(row)) for row in rows)

    def verify(self) -> tuple[DurableRecord, ...]:
        records = self.records()
        previous = _GENESIS
        for expected_sequence, record in enumerate(records):
            if record.sequence != expected_sequence:
                raise EnterpriseContractError("durable provenance sequence discontinuity")
            if record.previous_digest != previous:
                raise EnterpriseContractError("durable provenance hash-chain mismatch")
            if record.payload_digest != content_digest(record.payload):
                raise EnterpriseContractError("durable provenance payload digest mismatch")
            if record.record_digest != content_digest(record.canonical_body()):
                raise EnterpriseContractError("durable provenance record digest mismatch")
            previous = record.record_digest
        return records

    def head_digest(self) -> str:
        records = self.verify()
        return records[-1].record_digest if records else _GENESIS

    def append(
        self,
        *,
        stream_id: str,
        event_type: str,
        payload: Mapping[str, object],
    ) -> DurableRecord:
        stream_id = stream_id.strip()
        event_type = event_type.strip()
        if not stream_id or not event_type:
            raise EnterpriseContractError("stream_id and event_type are required")
        copied = dict(payload)
        payload_digest = content_digest(copied)
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                rows = self.records()
                previous = rows[-1].record_digest if rows else _GENESIS
                sequence = len(rows)
                body = {
                    "sequence": sequence,
                    "stream_id": stream_id,
                    "event_type": event_type,
                    "payload": copied,
                    "payload_digest": payload_digest,
                    "previous_digest": previous,
                }
                record_digest = content_digest(body)
                self._connection.execute(
                    """
                    INSERT INTO provenance (
                        sequence, stream_id, event_type, payload_json, payload_digest,
                        previous_digest, record_digest
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sequence,
                        stream_id,
                        event_type,
                        canonical_json(copied),
                        payload_digest,
                        previous,
                        record_digest,
                    ),
                )
                self._connection.execute("COMMIT")
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
        self.verify()
        return DurableRecord(
            sequence=sequence,
            stream_id=stream_id,
            event_type=event_type,
            payload=copied,
            payload_digest=payload_digest,
            previous_digest=previous,
            record_digest=record_digest,
        )

    def backup_to(self, snapshot_path: str | Path) -> str:
        with self._lock:
            source_head = self.head_digest()
            destination_path = Path(snapshot_path)
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            if destination_path.exists():
                destination_path.unlink()
            destination = sqlite3.connect(destination_path)
            try:
                self._connection.backup(destination)
                destination.commit()
            finally:
                destination.close()
        with SQLiteProvenanceStore(destination_path) as restored:
            restored_head = restored.head_digest()
        if restored_head != source_head:
            raise EnterpriseContractError("backup verification head digest mismatch")
        return source_head

    @classmethod
    def restore_verified(
        cls,
        snapshot_path: str | Path,
        destination_path: str | Path,
    ) -> SQLiteProvenanceStore:
        snapshot = cls(snapshot_path)
        try:
            expected_head = snapshot.head_digest()
            destination = Path(destination_path)
            if destination.exists():
                destination.unlink()
            target = cls(destination)
            try:
                snapshot._connection.backup(target._connection)
                target._connection.commit()
                if target.head_digest() != expected_head:
                    raise EnterpriseContractError("restore verification head digest mismatch")
                return target
            except BaseException:
                target.close()
                raise
        finally:
            snapshot.close()
