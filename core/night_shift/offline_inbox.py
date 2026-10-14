"""Crash-safe, metadata-only inbox for already-authorized Night Shift tasks.

This is a replayable cache, NOT an authorization source or agent launcher.
Persistent task execution state and fencing remain in LeaseStore. In particular,
a cached task is never proof that an agent is alive or that GitHub is current.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from .continuous_dispatcher import DispatchTask, select_next_task
from .contracts import NightShiftContractError
from .leases import LeaseStore

_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SOURCE = re.compile(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(?:issues|pull)/[1-9][0-9]*\Z")
_TASK_FIELDS = frozenset(DispatchTask.__dataclass_fields__)


def _canonical(value: dict) -> str:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    )


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    obj: dict = {}
    for key, value in pairs:
        if key in obj:
            raise NightShiftContractError("duplicate inbox JSON key")
        obj[key] = value
    return obj


@dataclass(frozen=True, slots=True)
class InboxCapsule:
    """Reference-only cache of a task already admitted by a trusted host.

    source_digest binds the observed GitHub task contract, not just its URL;
    git_sha identifies the code baseline. Neither grants execution authority.
    """

    task: DispatchTask
    source_ref: str
    source_digest: str
    git_sha: str
    policy_digest: str
    observed_at_epoch: int
    max_age_seconds: int = 3600

    def __post_init__(self) -> None:
        if not _SOURCE.fullmatch(self.source_ref):
            raise NightShiftContractError("source_ref must point to a GitHub issue or PR")
        if not _HEX64.fullmatch(self.source_digest) or not _HEX64.fullmatch(self.policy_digest):
            raise NightShiftContractError("source and policy digests must be SHA-256")
        if not _HEX40.fullmatch(self.git_sha):
            raise NightShiftContractError("git_sha must be an exact Git SHA-1")
        if type(self.observed_at_epoch) is not int or self.observed_at_epoch < 0:
            raise NightShiftContractError("invalid observation epoch")
        if type(self.max_age_seconds) is not int or not 1 <= self.max_age_seconds <= 3600:
            raise NightShiftContractError("invalid cache freshness window")
        if not isinstance(self.task, DispatchTask):
            raise NightShiftContractError("task must be a DispatchTask")
        if self.task.privacy_class not in {"SYNTHETIC", "PUBLIC"}:
            raise NightShiftContractError("private task metadata cannot enter offline inbox")
        if not isinstance(self.task.priority, int) or isinstance(self.task.priority, bool):
            raise NightShiftContractError("invalid task priority")
        if not isinstance(self.task.write_task, bool) or not isinstance(self.task.human_gate, bool):
            raise NightShiftContractError("invalid task gates")
        if not isinstance(self.task.external_gate, bool):
            raise NightShiftContractError("invalid external gate")

    def payload(self) -> dict:
        return {
            "task": asdict(self.task),
            "source_ref": self.source_ref,
            "source_digest": self.source_digest,
            "git_sha": self.git_sha,
            "policy_digest": self.policy_digest,
            "observed_at_epoch": self.observed_at_epoch,
            "max_age_seconds": self.max_age_seconds,
        }

    def serialized(self) -> str:
        return _canonical(self.payload())

    def digest(self) -> str:
        return hashlib.sha256(self.serialized().encode("utf-8")).hexdigest()

    @classmethod
    def parse(cls, raw: str) -> InboxCapsule:
        try:
            value = json.loads(raw, object_pairs_hook=_no_duplicate_keys)
            if not isinstance(value, dict) or set(value) != {
                "task", "source_ref", "source_digest", "git_sha",
                "policy_digest", "observed_at_epoch", "max_age_seconds",
            }:
                raise NightShiftContractError("unknown inbox capsule contract")
            task = value["task"]
            if not isinstance(task, dict) or set(task) != _TASK_FIELDS:
                raise NightShiftContractError("unknown dispatch task fields")
            if not isinstance(task["depends_on"], list) or any(
                not isinstance(item, str) for item in task["depends_on"]
            ):
                raise NightShiftContractError("invalid dependency list")
            if not isinstance(task["task_id"], str) or not task["task_id"].strip():
                raise NightShiftContractError("invalid task ID")
            return cls(task=DispatchTask(**{**task, "depends_on": tuple(task["depends_on"])}),
                       **{key: entry for key, entry in value.items() if key != "task"})
        except (ValueError, TypeError, KeyError) as exc:
            raise NightShiftContractError("corrupted inbox capsule") from exc


class OfflineTaskInbox:
    """Durable metadata spool; never asserts execution or mints authority."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.leases = LeaseStore(self.path)  # reuse the exact authoritative state DB
        with closing(self._connect()) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS offline_task_capsules (
                task_id TEXT PRIMARY KEY,
                capsule_json TEXT NOT NULL,
                capsule_sha256 TEXT NOT NULL,
                recorded_at_epoch INTEGER NOT NULL
            )""")
            con.commit()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=FULL")
        return con

    def enqueue(self, capsule: InboxCapsule, *, now_epoch: int) -> str:
        """Immutable/idempotent ingestion; caller must verify GitHub authorization."""
        if (
            type(now_epoch) is not int
            or not 0 <= now_epoch - capsule.observed_at_epoch <= capsule.max_age_seconds
        ):
            raise NightShiftContractError("task source snapshot is stale or future-dated")
        raw = capsule.serialized()
        sha = capsule.digest()
        with closing(self._connect()) as con:
            try:
                con.execute("BEGIN IMMEDIATE")
                row = con.execute(
                    "SELECT capsule_sha256 FROM offline_task_capsules WHERE task_id=?",
                    (capsule.task.task_id,),
                ).fetchone()
                if row is not None:
                    if row["capsule_sha256"] != sha:
                        raise NightShiftContractError(
                            "task identity conflict: new task ID required"
                        )
                else:
                    con.execute("""INSERT INTO offline_task_capsules (
                        task_id, capsule_json, capsule_sha256, recorded_at_epoch
                    ) VALUES (?, ?, ?, ?)""", (capsule.task.task_id, raw, sha, now_epoch))
                con.commit()
            except Exception:
                con.rollback()
                raise
        return sha

    def snapshot(self) -> tuple[InboxCapsule, ...]:
        """Rehydrate intact capsules; fail closed on modification or disk corruption."""
        with closing(self._connect()) as con:
            rows = con.execute("SELECT * FROM offline_task_capsules ORDER BY task_id").fetchall()
        result = []
        for row in rows:
            value = InboxCapsule.parse(row["capsule_json"])
            if value.task.task_id != row["task_id"] or value.digest() != row["capsule_sha256"]:
                raise NightShiftContractError("tampered offline task capsule")
            result.append(value)
        return tuple(result)

    def next_safe_local_probe(self, *, now_epoch: int) -> DispatchTask | None:
        """Select ONLY synthetic/public, non-mutating cached probes.

        Any historical lease is reserved for reconciliation, including expired
        leases: an ambiguous external side effect must never be blind-retried.
        No AI, network or code-writing operations are launched here.
        """
        if type(now_epoch) is not int or now_epoch < 0:
            raise NightShiftContractError("invalid dispatch epoch")
        capsules = self.snapshot()
        projected: list[DispatchTask] = []
        with closing(self._connect()) as con:
            for capsule in capsules:
                task = capsule.task
                lease = con.execute(
                    "SELECT 1 FROM leases WHERE task_id=?", (task.task_id,)
                ).fetchone()
                state = con.execute(
                    "SELECT state FROM task_states WHERE task_id=?", (task.task_id,)
                ).fetchone()
                if state is not None and state["state"] == "DONE" and lease:
                    # Only authoritative lease-state evidence may satisfy dependencies.
                    projected.append(replace(task, status="DONE"))
                elif (
                    lease is not None
                    or state is not None
                    or not 0 <= now_epoch - capsule.observed_at_epoch <= capsule.max_age_seconds
                    or task.write_task
                    or task.human_gate
                    or task.external_gate
                    or task.status != "READY"
                ):
                    projected.append(replace(task, status="QUARANTINED"))
                else:
                    projected.append(task)
        return select_next_task(tuple(projected), now_epoch=now_epoch)
