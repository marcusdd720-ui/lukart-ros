"""Native Hermes completion readback bound to the immutable accepted source."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path

from core.night_shift.authority import AuthorityBudgetStore
from core.night_shift.contracts import NightShiftContractError
from core.night_shift.journal import DurableEventJournal
from core.night_shift.task_intake import task_workflow
from scripts.integrations.ros_outbox import event_key
from scripts.integrations.ros_outbox_reconcile import accepted_task_ids

BOARD = "lukart-outbox-e2e-20261103"


def acknowledge(*, directory: Path, hermes_cli: str, kanban_task_id: str) -> dict[str, object]:
    journal = DurableEventJournal(directory / "journal.sqlite3")
    authority = AuthorityBudgetStore(directory / "authority.sqlite3")
    manifest = json.loads((directory / "accept.json").read_text(encoding="utf-8"))
    source_id = manifest["task_id"]
    if source_id not in accepted_task_ids(journal, authority=authority):
        raise NightShiftContractError("ACK has no accepted source")
    workflow_id = task_workflow(source_id)
    accepted = journal.verify_chain(workflow_id=workflow_id)[0]
    if accepted.payload["task_digest"] != manifest["task_capsule_digest"]:
        raise NightShiftContractError("ACK manifest differs from accepted capsule")
    if accepted.event_hash != manifest["source_event_hash"]:
        raise NightShiftContractError("ACK source event identity mismatch")
    readback = subprocess.run(
        [hermes_cli, "kanban", "--board", BOARD, "show", kanban_task_id, "--json"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=25,
    )
    document = json.loads(readback.stdout)
    native = document["task"]
    if native["id"] != kanban_task_id or native["status"] != "done":
        raise NightShiftContractError("native consumer has not completed")
    result = json.loads(native["result"])
    key = "lukart-ros-outbox-" + event_key(source_id)[:32]
    if (
        result["source_key"] != key
        or result["source_id"] != source_id
        or result["task_id"] != kanban_task_id
        or result["board"] != BOARD
        or result["child_exit_code"] != 0
        or result["paid_api_calls"] != 0
        or result["sha256"] != manifest["expected_sha256"]
        or result["bytes"] != manifest["canary_bytes"]
        or type(result["run_id"]) is not int
        or result["run_id"] < 1
    ):
        raise NightShiftContractError("native result is not bound to accepted canary")
    database = Path.home() / "AppData/Local/hermes/kanban/boards" / BOARD / "kanban.db"
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        stored = connection.execute(
            "SELECT idempotency_key FROM tasks WHERE id=?", (kanban_task_id,)
        ).fetchone()
    if stored is None or stored[0] != key:
        raise NightShiftContractError("native task idempotency key mismatch")
    verify_completed_run(document, result)
    task = accepted.payload["task"]
    if not isinstance(task, dict) or not str(task["objective"]).endswith(
        "expected=" + result["sha256"]
    ):
        raise NightShiftContractError("worker output was not accepted by original capsule")
    payload = {
        "schema_version": 1,
        "source_event_hash": accepted.event_hash,
        "task_capsule_digest": accepted.payload["task_digest"],
        "kanban_task_id": kanban_task_id,
        "source_key": key,
        "run_id": result["run_id"],
        "sha256": result["sha256"],
        "worker_kind": result["worker_kind"],
        "board": BOARD,
    }
    existing = [
        e for e in journal.verify_chain(workflow_id=workflow_id) if e.event_type == "WORKER_ACK_V1"
    ]
    if existing:
        if len(existing) != 1 or existing[0].payload != payload:
            raise NightShiftContractError("conflicting worker ACK")
        return {"acknowledged": True, "replayed": True, **payload}
    journal.append_event(
        event_id=workflow_id + ":worker-ack",
        workflow_id=workflow_id,
        event_type="WORKER_ACK_V1",
        payload=payload,
        created_at_epoch=int(native["completed_at"]),
    )
    return {"acknowledged": True, "replayed": False, **payload}


def verify_completed_run(document: dict, result: dict) -> None:
    """A result's claimed run ID must be the actual completed native run."""
    if type(result.get("run_id")) is not int:
        raise NightShiftContractError("native run ID must be integer")
    runs = [run for run in document.get("runs", []) if run.get("id") == result["run_id"]]
    if len(runs) != 1 or runs[0].get("outcome") != "completed":
        raise NightShiftContractError("native run is not uniquely completed")
    metadata = runs[0].get("metadata")
    if not isinstance(metadata, dict) or any(
        metadata.get(key) != result[key]
        for key in (
            "task_id",
            "source_id",
            "source_key",
            "run_id",
            "sha256",
            "child_exit_code",
            "board",
            "bytes",
            "paid_api_calls",
            "worker_kind",
        )
    ):
        raise NightShiftContractError("native completed run metadata mismatch")
