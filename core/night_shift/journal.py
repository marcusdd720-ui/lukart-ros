"""Durable append-only event journal for Night Shift workflows."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from core.p3.contracts import canonical_json, content_digest

from .contracts import NightShiftContractError

GENESIS_HASH = "0" * 64


@dataclass(frozen=True, slots=True)
class JournalEvent:
    sequence: int
    event_id: str
    workflow_id: str
    event_type: str
    payload: dict[str, object]
    created_at_epoch: int
    previous_hash: str
    event_hash: str
class DurableEventJournal:
    """SQLite-backed journal with idempotent append and hash-chain replay."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    workflow_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    created_at_epoch INTEGER NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );

                CREATE INDEX IF NOT EXISTS idx_events_workflow_sequence
                    ON events(workflow_id, sequence);

                CREATE TABLE IF NOT EXISTS inbox (
                    idempotency_key TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    payload_digest TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS outbox (
                    idempotency_key TEXT PRIMARY KEY,
                    action_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('PENDING', 'SENT'))
                );
                """
            )
    @staticmethod
    def _require_text(value: str, *, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise NightShiftContractError(f"{field_name} is required")
        return normalized

    def append_event(
        self,
        *,
        event_id: str,
        workflow_id: str,
        event_type: str,
        payload: Mapping[str, object],
        created_at_epoch: int,
    ) -> bool:
        """Append once. Return False for an exact duplicate; reject conflicting reuse."""

        event_id = self._require_text(event_id, field_name="event_id")
        workflow_id = self._require_text(workflow_id, field_name="workflow_id")
        event_type = self._require_text(event_type, field_name="event_type")
        if created_at_epoch < 0:
            raise NightShiftContractError("created_at_epoch cannot be negative")

        payload_json = canonical_json(payload)
        payload_digest = content_digest(payload)
        with self._transaction() as connection:
            existing = connection.execute(
                """
                SELECT workflow_id, event_type, payload_digest, created_at_epoch
                FROM events WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()
            if existing is not None:
                same = (
                    existing["workflow_id"] == workflow_id
                    and existing["event_type"] == event_type
                    and existing["payload_digest"] == payload_digest
                    and existing["created_at_epoch"] == created_at_epoch
                )
                if same:
                    return False
                raise NightShiftContractError("event_id reused with conflicting content")

            previous = connection.execute(
                """
                SELECT event_hash FROM events
                WHERE workflow_id = ?
                ORDER BY sequence DESC LIMIT 1
                """,
                (workflow_id,),
            ).fetchone()
            previous_hash = previous["event_hash"] if previous else GENESIS_HASH
            event_hash = content_digest(
                {
                    "event_id": event_id,
                    "workflow_id": workflow_id,
                    "event_type": event_type,
                    "payload_digest": payload_digest,
                    "created_at_epoch": created_at_epoch,
                    "previous_hash": previous_hash,
                }
            )
            connection.execute(
                """
                INSERT INTO events(
                    event_id, workflow_id, event_type, payload_json, payload_digest,
                    created_at_epoch, previous_hash, event_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    workflow_id,
                    event_type,
                    payload_json,
                    payload_digest,
                    created_at_epoch,
                    previous_hash,
                    event_hash,
                ),
            )
        return True
    def events(self, *, workflow_id: str) -> tuple[JournalEvent, ...]:
        workflow_id = self._require_text(workflow_id, field_name="workflow_id")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT sequence, event_id, workflow_id, event_type, payload_json,
                       created_at_epoch, previous_hash, event_hash
                FROM events
                WHERE workflow_id = ?
                ORDER BY sequence
                """,
                (workflow_id,),
            ).fetchall()

        return tuple(
            JournalEvent(
                sequence=row["sequence"],
                event_id=row["event_id"],
                workflow_id=row["workflow_id"],
                event_type=row["event_type"],
                payload=json.loads(row["payload_json"]),
                created_at_epoch=row["created_at_epoch"],
                previous_hash=row["previous_hash"],
                event_hash=row["event_hash"],
            )
            for row in rows
        )
    def verify_chain(self, *, workflow_id: str) -> tuple[JournalEvent, ...]:
        events = self.events(workflow_id=workflow_id)
        previous_hash = GENESIS_HASH
        for event in events:
            if event.previous_hash != previous_hash:
                raise NightShiftContractError("journal hash chain is broken")
            payload_digest = content_digest(event.payload)
            expected_hash = content_digest(
                {
                    "event_id": event.event_id,
                    "workflow_id": event.workflow_id,
                    "event_type": event.event_type,
                    "payload_digest": payload_digest,
                    "created_at_epoch": event.created_at_epoch,
                    "previous_hash": previous_hash,
                }
            )
            if event.event_hash != expected_hash:
                raise NightShiftContractError("journal event hash mismatch")
            previous_hash = event.event_hash
        return events

    def replay_state(
        self,
        *,
        workflow_id: str,
        initial_state: str = "DISCOVERED",
    ) -> str:
        state = self._require_text(initial_state, field_name="initial_state")
        for event in self.verify_chain(workflow_id=workflow_id):
            if event.event_type == "STATE_TRANSITION":
                to_state = event.payload.get("to_state")
                if not isinstance(to_state, str) or not to_state.strip():
                    raise NightShiftContractError("state transition lacks to_state")
                state = to_state.strip()
        return state

    def record_inbox(
        self,
        *,
        idempotency_key: str,
        source: str,
        payload: Mapping[str, object],
    ) -> bool:
        key = self._require_text(idempotency_key, field_name="idempotency_key")
        source = self._require_text(source, field_name="source")
        digest = content_digest(payload)
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT source, payload_digest FROM inbox WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
            if row is not None:
                if row["source"] == source and row["payload_digest"] == digest:
                    return False
                raise NightShiftContractError("inbox idempotency conflict")
            connection.execute(
                "INSERT INTO inbox(idempotency_key, source, payload_digest) VALUES (?, ?, ?)",
                (key, source, digest),
            )
        return True
    def enqueue_outbox(
        self,
        *,
        idempotency_key: str,
        action_type: str,
        payload: Mapping[str, object],
    ) -> bool:
        key = self._require_text(idempotency_key, field_name="idempotency_key")
        action_type = self._require_text(action_type, field_name="action_type")
        payload_json = canonical_json(payload)
        digest = content_digest(payload)
        with self._transaction() as connection:
            row = connection.execute(
                """
                SELECT action_type, payload_digest
                FROM outbox WHERE idempotency_key = ?
                """,
                (key,),
            ).fetchone()
            if row is not None:
                if row["action_type"] == action_type and row["payload_digest"] == digest:
                    return False
                raise NightShiftContractError("outbox idempotency conflict")
            connection.execute(
                """
                INSERT INTO outbox(
                    idempotency_key, action_type, payload_json, payload_digest, status
                ) VALUES (?, ?, ?, ?, 'PENDING')
                """,
                (key, action_type, payload_json, digest),
            )
        return True
    def pending_outbox(self) -> tuple[tuple[str, str, dict[str, object]], ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT idempotency_key, action_type, payload_json
                FROM outbox WHERE status = 'PENDING'
                ORDER BY rowid
                """
            ).fetchall()
        return tuple(
            (
                row["idempotency_key"],
                row["action_type"],
                json.loads(row["payload_json"]),
            )
            for row in rows
        )

    def mark_outbox_sent(self, *, idempotency_key: str) -> None:
        key = self._require_text(idempotency_key, field_name="idempotency_key")
        with self._transaction() as connection:
            updated = connection.execute(
                """
                UPDATE outbox SET status = 'SENT'
                WHERE idempotency_key = ? AND status = 'PENDING'
                """,
                (key,),
            ).rowcount
            if updated != 1:
                raise NightShiftContractError("outbox item is missing or already sent")
