"""Explicit owner-authorized, synthetic-only integration admission and replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path

from core.night_shift.authority import AuthorityBudgetStore
from core.night_shift.contracts import (
    AutonomyEnvelope,
    LiveStateSnapshot,
    PolicyRef,
    PromotionMode,
    RiskClass,
    TaskCapsule,
)
from core.night_shift.journal import DurableEventJournal
from core.night_shift.task_intake import accept_task
from core.p3.contracts import content_digest
from scripts.integrations.ros_outbox import drain, event_key
from scripts.integrations.ros_outbox_ack import acknowledge
from scripts.integrations.ros_outbox_reconcile import accepted_task_ids, reconcile

CANARY = b"LUKART_SYNTHETIC_OUTBOX_E2E_20261103\n"
TASK_ID = "synthetic_outbox_e2e_20261103_001"
BOARD = "lukart-outbox-e2e-20261103"


def recover_acceptance_fixture(root, journal, authority, task_id):
    """Rebuild fixture metadata from the committed source without fresh admission."""
    if task_id not in accepted_task_ids(journal, authority=authority):
        raise ValueError("No verified committed task acceptance")
    event = journal.verify_chain(workflow_id="accepted-task:" + task_id)[0]
    capsule = event.payload["task"]
    expected = hashlib.sha256(CANARY).hexdigest()
    if not capsule["objective"].endswith("expected=" + expected):
        raise ValueError("Committed task is not this bounded synthetic canary")
    if capsule["allowed_paths"] != ["external-fixture/canary.txt"]:
        raise ValueError("Committed task fixture scope differs")
    (root / "canary.txt").write_bytes(CANARY)
    return {
        "schema_version": 1,
        "fixture_scope": "EXTERNAL_SYNTHETIC_INPUT_NO_REPO_WRITES",
        "source_event_hash": event.event_hash,
        "canary_bytes": len(CANARY),
        "source_key": "lukart-ros-outbox-" + event_key(task_id)[:32],
        "accepted": True,
        "task_id": task_id,
        "event_id": event_key(task_id),
        "expected_sha256": expected,
        "source_sha": event.payload["state"]["head_sha"],
        "board": BOARD,
        "task_capsule_digest": event.payload["task_digest"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--step", choices=("accept", "reconcile", "deliver", "ack"), required=True)
    parser.add_argument("--hermes-cli")
    parser.add_argument("--kanban-task-id")
    parser.add_argument("--task-id", default=TASK_ID)
    parser.add_argument("--fault-after-source-commit", action="store_true")
    args = parser.parse_args()
    root = args.directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    journal = DurableEventJournal(root / "journal.sqlite3")
    authority = AuthorityBudgetStore(root / "authority.sqlite3")
    result: Mapping[str, object]
    if args.step == "accept" and journal.verify_chain(workflow_id="accepted-task:" + args.task_id):
        result = recover_acceptance_fixture(root, journal, authority, args.task_id)
    elif args.step == "accept":
        now = int(time.time())
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        policy_digest = content_digest(
            {
                "scope": "OWNER_20261103_EMERGENCY_E2E",
                "data": "SYNTHETIC",
                "operation": "sha256 canary",
                "main_merge": False,
                "paid_api": False,
            }
        )
        policy = PolicyRef("OWNER_20261103_EMERGENCY_E2E", "v1", policy_digest)
        state = LiveStateSnapshot(
            "outbox-integration-20261103",
            "marcusdd720-ui/lukart-ros",
            "fix/ros-accepted-task-outbox-e2e-20261103",
            sha,
            sha,
            now,
            now + 3600,
            (
                "owner-request:20261103",
                "git:HEAD",
                "external-fixture:" + str((root / "canary.txt").resolve()),
            ),
        )
        expected = hashlib.sha256(CANARY).hexdigest()
        task = TaskCapsule(
            args.task_id,
            state.repository,
            state.digest(),
            policy.policy_digest,
            "Hash the exact synthetic canary bytes with SHA256; expected=" + expected,
            RiskClass.R0,
            ("external-fixture/canary.txt",),
            ("core/**", ".github/**"),
            ("native worker subprocess hash", "durable ACK"),
        )
        envelope = AutonomyEnvelope(
            "OWNER_20261103_EMERGENCY_E2E",
            now,
            now + 3600,
            (task.repository,),
            (RiskClass.R0,),
            1,
            PromotionMode.HUMAN,
        )
        accept_task(
            journal=journal,
            authority=authority,
            policy=policy,
            state=state,
            task=task,
            envelope=envelope,
            now_epoch=now,
        )
        if args.fault_after_source_commit:
            os._exit(91)  # Deliberate isolated crash before manifest/canary writes.
        result = recover_acceptance_fixture(root, journal, authority, args.task_id)
    elif args.step == "reconcile":
        result = reconcile(
            journal=journal, authority=authority, outbox_path=root / "outbox.sqlite3"
        )
    elif args.step == "ack":
        if not args.hermes_cli or not args.kanban_task_id:
            parser.error("--hermes-cli and --kanban-task-id required for ack")
        result = acknowledge(
            directory=root, hermes_cli=args.hermes_cli, kanban_task_id=args.kanban_task_id
        )
    else:
        if not args.hermes_cli:
            parser.error("--hermes-cli required for deliver")
        result = drain(
            hermes_cli=args.hermes_cli,
            db_path=root / "outbox.sqlite3",
            limit=1,
            board=BOARD,
        )
    text = json.dumps(result, sort_keys=True)
    (root / (args.step + ".json")).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
