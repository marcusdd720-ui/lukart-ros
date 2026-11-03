"""Bounded external deterministic worker using native Hermes ownership APIs."""

from __future__ import annotations

if not __debug__:
    raise RuntimeError("Optimized execution is forbidden for this guarded worker")

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(1, str(Path.home() / "AppData/Local/hermes/hermes-agent"))
import hermes_bootstrap  # noqa: F401,E402
from hermes_cli import kanban_db as kb  # noqa: E402
from hermes_cli import kanban_db_connect as kbc  # noqa: E402

from core.night_shift.authority import AuthorityBudgetStore  # noqa: E402
from core.night_shift.journal import DurableEventJournal  # noqa: E402
from scripts.integrations.ros_outbox import event_key  # noqa: E402
from scripts.integrations.ros_outbox_reconcile import accepted_task_ids  # noqa: E402

BOARD = "lukart-outbox-e2e-20261103"


def main():
    task_id, source_key, output, source_id = sys.argv[1:5]
    assert source_id.startswith("synthetic_outbox_e2e_20261103_")
    receipt = Path(output)
    directory = receipt.parent
    manifest = json.loads((directory / "accept.json").read_text(encoding="utf-8"))
    journal = DurableEventJournal(directory / "journal.sqlite3")
    authority = AuthorityBudgetStore(directory / "authority.sqlite3")
    assert source_id in accepted_task_ids(journal, authority=authority)
    accepted = journal.verify_chain(workflow_id="accepted-task:" + source_id)[0]
    assert manifest["task_id"] == source_id
    assert manifest["source_event_hash"] == accepted.event_hash
    assert manifest["task_capsule_digest"] == accepted.payload["task_digest"]
    expected = manifest["expected_sha256"]
    assert accepted.payload["task"]["objective"].endswith("expected=" + expected)
    canary = directory / "canary.txt"
    assert hashlib.sha256(canary.read_bytes()).hexdigest() == expected
    assert source_key == "lukart-ros-outbox-" + event_key(source_id)[:32]
    conn = kbc.connect(board=BOARD)
    try:
        task = kb.get_task(conn, task_id)
        assert task is not None, "unknown native task"
        row = conn.execute("SELECT idempotency_key FROM tasks WHERE id=?", (task_id,)).fetchone()
        assert row["idempotency_key"] == source_key, "source key mismatch"
        if task.status == "done":
            saved = json.loads(task.result)
            assert saved["task_id"] == task_id and saved["source_key"] == source_key
            assert saved["sha256"] == expected and saved["source_id"] == source_id
            receipt.write_text(json.dumps(saved, indent=2), encoding="utf-8")
            print(json.dumps({"replayed": True, "duplicate_execution": False, **saved}))
            return
        repository = Path(__file__).resolve().parents[1]
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository, text=True
        ).strip()
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=repository, text=True
        ).strip()
        remote = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], cwd=repository, text=True
        ).strip()
        assert remote.rstrip("/").removesuffix(".git") in {
            "https://github.com/marcusdd720-ui/lukart-ros",
            "git@github.com:marcusdd720-ui/lukart-ros",
        }, "repository identity differs"
        assert head == manifest["source_sha"] == accepted.payload["state"]["head_sha"], (
            "candidate changed"
        )
        assert branch == accepted.payload["state"]["branch"], "branch changed"
        assert accepted.payload["state"]["repository"] == "marcusdd720-ui/lukart-ros"
        assert manifest["fixture_scope"] == "EXTERNAL_SYNTHETIC_INPUT_NO_REPO_WRITES"
        assert accepted.payload["task"]["allowed_paths"] == ["external-fixture/canary.txt"]
        assert (
            "external-fixture:" + str(canary.resolve())
            in accepted.payload["state"]["evidence_refs"]
        )
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=repository,
            text=True,
        ).strip()
        assert not dirty, "candidate checkout is dirty"
        now = int(time.time())
        assert now < accepted.payload["state"]["expires_at_epoch"], "stale execution state"
        assert now < accepted.payload["envelope"]["expires_at_epoch"], "expired authority"
        assert accepted.payload["task"]["risk_class"] == "R0"
        if task.status in {"blocked", "todo"}:
            ok, reason = kb.promote_task(
                conn,
                task_id,
                actor="ChatGPT-E2E-Coordinator",
                reason="Owner-authorized bounded synthetic deterministic worker",
            )
            assert ok, reason
        claimed = kb.claim_task(conn, task_id, ttl_seconds=120)
        assert claimed is not None, "native claim refused; do not force"
        child_code = (
            "import hashlib,json,sys; from pathlib import Path; "
            "p=Path(sys.argv[1]).read_bytes(); "
            "print(json.dumps({'sha256':hashlib.sha256(p).hexdigest(),'bytes':len(p)}))"
        )
        child = subprocess.run(
            [sys.executable, "-c", child_code, str(canary)],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        actual = json.loads(child.stdout)
        assert actual == {"sha256": expected, "bytes": manifest["canary_bytes"]}
        result = {
            "board": BOARD,
            "task_id": task_id,
            "source_id": source_id,
            "source_key": source_key,
            "run_id": claimed.current_run_id,
            "worker_kind": "native-Hermes-claim/external-deterministic-subprocess",
            "child_exit_code": child.returncode,
            "sha256": actual["sha256"],
            "bytes": actual["bytes"],
            "paid_api_calls": 0,
        }
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(result, indent=2), encoding="utf-8")
        ok = kb.complete_task(
            conn,
            task_id,
            result=json.dumps(result),
            summary="Synthetic SHA256 completed; native claim and source binding verified.",
            metadata=result,
            expected_run_id=claimed.current_run_id,
        )
        assert ok, "native completion gate refused"
        assert kb.get_task(conn, task_id).status == "done"
        print(json.dumps(result))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
