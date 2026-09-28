"""Lease, fencing-token and compare-and-swap controls for Night Shift."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .contracts import NightShiftContractError


@dataclass(frozen=True, slots=True)
class TaskLease:
    task_id: str
    lease_id: str
    worker_id: str
    fencing_token: int
    expires_at_epoch: int
    version: int


@dataclass(frozen=True, slots=True)
class TaskState:
    task_id: str
    state: str
    version: int
    fencing_token: int


class LeaseStore:
    """SQLite-backed single-owner task leases with monotonic fencing tokens."""
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
                CREATE TABLE IF NOT EXISTS lease_counters (
                    task_id TEXT PRIMARY KEY,
                    last_fencing_token INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS leases (
                    task_id TEXT PRIMARY KEY,
                    lease_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    fencing_token INTEGER NOT NULL,
                    expires_at_epoch INTEGER NOT NULL,
                    version INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_states (
                    task_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    fencing_token INTEGER NOT NULL
                );
                """
            )

    @staticmethod
    def _text(value: str, *, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise NightShiftContractError(f"{field_name} is required")
        return normalized

    def acquire(
        self,
        *,
        task_id: str,
        lease_id: str,
        worker_id: str,
        now_epoch: int,
        ttl_seconds: int,
    ) -> TaskLease:
        task_id = self._text(task_id, field_name="task_id")
        lease_id = self._text(lease_id, field_name="lease_id")
        worker_id = self._text(worker_id, field_name="worker_id")
        if now_epoch < 0:
            raise NightShiftContractError("now_epoch cannot be negative")
        if ttl_seconds < 1:
            raise NightShiftContractError("ttl_seconds must be positive")

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT expires_at_epoch FROM leases WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if current is not None and current["expires_at_epoch"] > now_epoch:
                raise NightShiftContractError("task already has an active lease")

            counter = connection.execute(
                "SELECT last_fencing_token FROM lease_counters WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            token = 1 if counter is None else int(counter["last_fencing_token"]) + 1
            if counter is None:
                connection.execute(
                    """
                    INSERT INTO lease_counters(task_id, last_fencing_token)
                    VALUES (?, ?)
                    """,
                    (task_id, token),
                )
            else:
                connection.execute(
                    """
                    UPDATE lease_counters SET last_fencing_token = ?
                    WHERE task_id = ?
                    """,
                    (token, task_id),
                )

            expires_at = now_epoch + ttl_seconds
            connection.execute(
                """
                INSERT INTO leases(
                    task_id, lease_id, worker_id, fencing_token,
                    expires_at_epoch, version
                ) VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(task_id) DO UPDATE SET
                    lease_id = excluded.lease_id,
                    worker_id = excluded.worker_id,
                    fencing_token = excluded.fencing_token,
                    expires_at_epoch = excluded.expires_at_epoch,
                    version = leases.version + 1
                """,
                (task_id, lease_id, worker_id, token, expires_at),
            )
            row = connection.execute(
                "SELECT * FROM leases WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        if row is None:
            raise NightShiftContractError("lease acquisition failed")
        return TaskLease(
            task_id=row["task_id"],
            lease_id=row["lease_id"],
            worker_id=row["worker_id"],
            fencing_token=row["fencing_token"],
            expires_at_epoch=row["expires_at_epoch"],
            version=row["version"],
        )

    def require_current(
        self,
        *,
        task_id: str,
        lease_id: str,
        fencing_token: int,
        now_epoch: int,
    ) -> TaskLease:
        task_id = self._text(task_id, field_name="task_id")
        lease_id = self._text(lease_id, field_name="lease_id")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM leases WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            raise NightShiftContractError("task lease is missing")
        if (
            row["lease_id"] != lease_id
            or int(row["fencing_token"]) != fencing_token
        ):
            raise NightShiftContractError("stale lease or fencing token")
        if now_epoch >= int(row["expires_at_epoch"]):
            raise NightShiftContractError("task lease expired")
        return TaskLease(
            task_id=row["task_id"],
            lease_id=row["lease_id"],
            worker_id=row["worker_id"],
            fencing_token=row["fencing_token"],
            expires_at_epoch=row["expires_at_epoch"],
            version=row["version"],
        )

    def heartbeat(
        self,
        *,
        task_id: str,
        lease_id: str,
        fencing_token: int,
        now_epoch: int,
        ttl_seconds: int,
    ) -> TaskLease:
        current = self.require_current(
            task_id=task_id,
            lease_id=lease_id,
            fencing_token=fencing_token,
            now_epoch=now_epoch,
        )
        if ttl_seconds < 1:
            raise NightShiftContractError("ttl_seconds must be positive")
        new_expiry = now_epoch + ttl_seconds
        with self._connect() as connection:
            updated = connection.execute(
                """
                UPDATE leases
                SET expires_at_epoch = ?, version = version + 1
                WHERE task_id = ? AND lease_id = ? AND fencing_token = ? AND version = ?
                """,
                (
                    new_expiry,
                    current.task_id,
                    current.lease_id,
                    current.fencing_token,
                    current.version,
                ),
            ).rowcount
            if updated != 1:
                raise NightShiftContractError("lease heartbeat CAS conflict")
        return self.require_current(
            task_id=task_id,
            lease_id=lease_id,
            fencing_token=fencing_token,
            now_epoch=now_epoch,
        )
    def initialize_state(
        self,
        *,
        task_id: str,
        state: str,
        lease_id: str,
        fencing_token: int,
        now_epoch: int,
    ) -> TaskState:
        task_id = self._text(task_id, field_name="task_id")
        lease_id = self._text(lease_id, field_name="lease_id")
        state = self._text(state, field_name="state")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            lease_row = connection.execute(
                "SELECT * FROM leases WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if lease_row is None:
                raise NightShiftContractError("task lease is missing")
            if (
                lease_row["lease_id"] != lease_id
                or int(lease_row["fencing_token"]) != fencing_token
            ):
                raise NightShiftContractError("stale lease or fencing token")
            if now_epoch >= int(lease_row["expires_at_epoch"]):
                raise NightShiftContractError("task lease expired")
            try:
                connection.execute(
                    """
                    INSERT INTO task_states(task_id, state, version, fencing_token)
                    VALUES (?, ?, 1, ?)
                    """,
                    (task_id, state, fencing_token),
                )
            except sqlite3.IntegrityError as exc:
                raise NightShiftContractError("task state already initialized") from exc
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return TaskState(task_id, state, 1, fencing_token)
    def compare_and_swap_state(
        self,
        *,
        task_id: str,
        expected_version: int,
        new_state: str,
        lease_id: str,
        fencing_token: int,
        now_epoch: int,
    ) -> TaskState:
        task_id = self._text(task_id, field_name="task_id")
        lease_id = self._text(lease_id, field_name="lease_id")
        new_state = self._text(new_state, field_name="new_state")
        if expected_version < 1:
            raise NightShiftContractError("expected_version must be positive")

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            lease_row = connection.execute(
                "SELECT * FROM leases WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if lease_row is None:
                raise NightShiftContractError("task lease is missing")
            if (
                lease_row["lease_id"] != lease_id
                or int(lease_row["fencing_token"]) != fencing_token
            ):
                raise NightShiftContractError("stale lease or fencing token")
            if now_epoch >= int(lease_row["expires_at_epoch"]):
                raise NightShiftContractError("task lease expired")

            updated = connection.execute(
                """
                UPDATE task_states
                SET state = ?, version = version + 1, fencing_token = ?
                WHERE task_id = ? AND version = ?
                """,
                (new_state, fencing_token, task_id, expected_version),
            ).rowcount
            if updated != 1:
                raise NightShiftContractError("task state CAS conflict")
            row = connection.execute(
                "SELECT * FROM task_states WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        if row is None:
            raise NightShiftContractError("task state missing after CAS")
        return TaskState(
            task_id=row["task_id"],
            state=row["state"],
            version=row["version"],
            fencing_token=row["fencing_token"],
        )

    def get_state(self, *, task_id: str) -> TaskState | None:
        task_id = self._text(task_id, field_name="task_id")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM task_states WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return TaskState(
            task_id=row["task_id"],
            state=row["state"],
            version=row["version"],
            fencing_token=row["fencing_token"],
        )
