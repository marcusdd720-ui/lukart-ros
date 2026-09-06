"""E6/H7 transactional provenance, backup, rollback and recovery controls."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from core.p3.contracts import canonical_json, content_digest, require_hex_digest

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


@dataclass(frozen=True, slots=True)
class RecoveryIdentity:
    """Versioned durable-state identity used to verify restore and rollback results."""

    record_count: int
    head_digest: str
    semantic_digest: str
    schema: str = "lukart.recovery-identity.v1"

    def __post_init__(self) -> None:
        if self.record_count < 0:
            raise EnterpriseContractError("recovery identity record_count cannot be negative")
        if self.schema != "lukart.recovery-identity.v1":
            raise EnterpriseContractError(f"unsupported recovery identity schema: {self.schema}")
        require_hex_digest(self.head_digest, field_name="recovery_head_digest")
        require_hex_digest(self.semantic_digest, field_name="recovery_semantic_digest")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "record_count": self.record_count,
            "head_digest": self.head_digest,
            "semantic_digest": self.semantic_digest,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


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

    @staticmethod
    def _cleanup_sidecars(path: Path) -> None:
        for suffix in ("-wal", "-shm"):
            Path(f"{path}{suffix}").unlink(missing_ok=True)

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

    def state_identity(self) -> RecoveryIdentity:
        records = self.verify()
        semantic_digest = content_digest(
            [
                {
                    "sequence": record.sequence,
                    "stream_id": record.stream_id,
                    "event_type": record.event_type,
                    "payload": dict(record.payload),
                }
                for record in records
            ]
        )
        return RecoveryIdentity(
            record_count=len(records),
            head_digest=records[-1].record_digest if records else _GENESIS,
            semantic_digest=semantic_digest,
        )

    def append_batch(
        self,
        events: Sequence[tuple[str, str, Mapping[str, object]]],
    ) -> tuple[DurableRecord, ...]:
        """Atomically append a bounded logical batch; validation failure writes nothing."""

        if not events:
            raise EnterpriseContractError("durable append batch cannot be empty")
        prepared: list[tuple[str, str, dict[str, object], str]] = []
        for raw_stream_id, raw_event_type, raw_payload in events:
            stream_id = raw_stream_id.strip()
            event_type = raw_event_type.strip()
            if not stream_id or not event_type:
                raise EnterpriseContractError("stream_id and event_type are required")
            copied = json.loads(canonical_json(dict(raw_payload)))
            if not isinstance(copied, dict):
                raise EnterpriseContractError("durable provenance payload must be an object")
            prepared.append((stream_id, event_type, copied, content_digest(copied)))

        inserted: list[DurableRecord] = []
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                rows = self.records()
                previous = rows[-1].record_digest if rows else _GENESIS
                sequence = len(rows)
                for stream_id, event_type, copied, payload_digest in prepared:
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
                    record = DurableRecord(
                        sequence=sequence,
                        stream_id=stream_id,
                        event_type=event_type,
                        payload=copied,
                        payload_digest=payload_digest,
                        previous_digest=previous,
                        record_digest=record_digest,
                    )
                    inserted.append(record)
                    previous = record_digest
                    sequence += 1
                self._connection.execute("COMMIT")
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
        self.verify()
        return tuple(inserted)

    def append(
        self,
        *,
        stream_id: str,
        event_type: str,
        payload: Mapping[str, object],
    ) -> DurableRecord:
        return self.append_batch(((stream_id, event_type, payload),))[0]

    def backup_to(self, snapshot_path: str | Path) -> str:
        with self._lock:
            source_identity = self.state_identity()
            destination_path = Path(snapshot_path)
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            if destination_path.exists():
                destination_path.unlink()
            self._cleanup_sidecars(destination_path)
            destination = sqlite3.connect(destination_path)
            try:
                self._connection.backup(destination)
                destination.commit()
            finally:
                destination.close()
        with SQLiteProvenanceStore(destination_path) as restored:
            restored_identity = restored.state_identity()
        if restored_identity != source_identity:
            raise EnterpriseContractError("backup verification state identity mismatch")
        return source_identity.head_digest

    @classmethod
    def restore_verified(
        cls,
        snapshot_path: str | Path,
        destination_path: str | Path,
        *,
        max_records: int | None = None,
    ) -> SQLiteProvenanceStore:
        """Verify in a staging database before replacing destination; never accept partial restore."""

        if max_records is not None and max_records < 1:
            raise EnterpriseContractError("restore max_records must be positive")
        snapshot = cls(snapshot_path)
        staging_path: Path | None = None
        try:
            expected_identity = snapshot.state_identity()
            if max_records is not None and expected_identity.record_count > max_records:
                raise EnterpriseContractError("restore blast-radius record limit exceeded")

            destination = Path(destination_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                prefix=f".{destination.name}.restore-",
                suffix=".db",
                dir=destination.parent,
                delete=False,
            ) as handle:
                staging_path = Path(handle.name)
            staging_path.unlink(missing_ok=True)

            staged = cls(staging_path)
            try:
                snapshot._connection.backup(staged._connection)
                staged._connection.commit()
                if staged.state_identity() != expected_identity:
                    raise EnterpriseContractError("restore staging state identity mismatch")
            finally:
                staged.close()

            cls._cleanup_sidecars(staging_path)
            os.replace(staging_path, destination)
            staging_path = None
            cls._cleanup_sidecars(destination)

            restored = cls(destination)
            try:
                if restored.state_identity() != expected_identity:
                    raise EnterpriseContractError("restore verification state identity mismatch")
                return restored
            except BaseException:
                restored.close()
                raise
        finally:
            snapshot.close()
            if staging_path is not None:
                staging_path.unlink(missing_ok=True)
                cls._cleanup_sidecars(staging_path)
