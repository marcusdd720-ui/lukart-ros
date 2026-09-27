"""Durable autonomy-envelope task budget enforcement."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .contracts import AuthorityReservation, AutonomyEnvelope, NightShiftContractError


class AuthorityBudgetStore:
    """Atomically enforce unique-task consumption of an AutonomyEnvelope."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        return connection
    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS envelope_usage (
                    envelope_digest TEXT PRIMARY KEY,
                    consumed_tasks INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS authority_reservations (
                    envelope_digest TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    PRIMARY KEY(envelope_digest, task_id),
                    UNIQUE(envelope_digest, ordinal)
                );
                """
            )

    @staticmethod
    def _task_id(value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise NightShiftContractError("task_id is required")
        return normalized

    def reserve_task(
        self,
        *,
        envelope: AutonomyEnvelope,
        task_id: str,
        now_epoch: int,
    ) -> AuthorityReservation:
        task_id = self._task_id(task_id)
        if now_epoch < envelope.issued_at_epoch:
            raise NightShiftContractError("current time precedes authority issuance")
        if now_epoch >= envelope.expires_at_epoch:
            raise NightShiftContractError("authority envelope expired")

        digest = envelope.digest()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT ordinal FROM authority_reservations
                WHERE envelope_digest = ? AND task_id = ?
                """,
                (digest, task_id),
            ).fetchone()
            if existing is not None:
                connection.commit()
                return AuthorityReservation(digest, task_id, int(existing["ordinal"]))

            usage = connection.execute(
                """
                SELECT consumed_tasks FROM envelope_usage
                WHERE envelope_digest = ?
                """,
                (digest,),
            ).fetchone()
            consumed = 0 if usage is None else int(usage["consumed_tasks"])
            if consumed >= envelope.max_tasks:
                raise NightShiftContractError("autonomy envelope task budget exhausted")
            ordinal = consumed + 1
            if usage is None:
                connection.execute(
                    """
                    INSERT INTO envelope_usage(envelope_digest, consumed_tasks)
                    VALUES (?, ?)
                    """,
                    (digest, ordinal),
                )
            else:
                updated = connection.execute(
                    """
                    UPDATE envelope_usage
                    SET consumed_tasks = ?
                    WHERE envelope_digest = ? AND consumed_tasks = ?
                    """,
                    (ordinal, digest, consumed),
                ).rowcount
                if updated != 1:
                    raise NightShiftContractError("authority budget CAS conflict")

            connection.execute(
                """
                INSERT INTO authority_reservations(envelope_digest, task_id, ordinal)
                VALUES (?, ?, ?)
                """,
                (digest, task_id, ordinal),
            )
            connection.commit()
            return AuthorityReservation(digest, task_id, ordinal)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
