"""Real local subprocess and negative tests; no API calls or paid provider."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from core.night_shift.child_process_bridge import (
    ChildLaunchPlan,
    ChildProcessBridge,
)
from core.night_shift.contracts import NightShiftContractError
from core.night_shift.journal import DurableEventJournal
from core.night_shift.leases import LeaseStore

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX/WSL bridge")


@pytest.fixture()
def rig(tmp_path: Path):
    root = tmp_path / "agent-worktree"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "baseline.txt").write_text("baseline", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git", "-C", str(root),
            "-c", "user.name=Test",
            "-c", "user.email=synthetic.invalid",
            "commit", "-qm", "baseline",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "checkout", "-qb", "night-shift/bridge-fixture"],
        check=True,
    )
    head = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    state = tmp_path / "night-shift.db"
    leases = LeaseStore(state)
    journal = DurableEventJournal(state)
    now = int(time.time())
    lease = leases.acquire(
        task_id="TASK-346-SYNTHETIC",
        lease_id="lease-346",
        worker_id="bridge-test",
        now_epoch=now,
        ttl_seconds=90,
    )
    executable = Path(sys.executable).resolve()
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    plan = ChildLaunchPlan(
        task_id=lease.task_id,
        worker_id=lease.worker_id,
        lease_id=lease.lease_id,
        fencing_token=lease.fencing_token,
        role="BUILDER",
        executable=executable,
        executable_sha256=digest,
        arguments=("-c", "from pathlib import Path; Path('result.txt').write_text('ran')"),
        worktree=root,
        base_sha=head,
        heartbeat_seconds=0.1,
        no_progress_seconds=1,
        timeout_seconds=2,
    )
    return leases, journal, plan


def bridge(rig, *, admit=True, reviewer=False):
    leases, journal, _ = rig
    return ChildProcessBridge(
        leases=leases,
        journal=journal,
        admission_checker=(lambda plan: True) if admit else None,
        reviewer_isolation_checker=(lambda plan: True) if reviewer else None,
    )


def test_real_child_runs_in_task_worktree_and_journals_exit(rig):
    _, journal, plan = rig
    evidence = bridge(rig).execute(plan)
    assert evidence.status == "EXITED_ZERO"
    assert evidence.exit_code == 0
    assert (plan.worktree / "result.txt").read_text() == "ran"
    events = journal.events(workflow_id=f"child-bridge:{plan.task_id}")
    assert [e.event_type for e in events] == [
        "CHILD_LAUNCH_INTENT", "CHILD_STARTED", "CHILD_EXIT"
    ]
    assert evidence.plan_digest == events[-1].payload["plan_digest"]


def test_replay_cannot_launch_child_twice(rig):
    runner = bridge(rig)
    plan = rig[2]
    runner.execute(plan)
    with pytest.raises(NightShiftContractError, match="reconcile first"):
        runner.execute(plan)


def test_no_untrusted_or_implicit_admission(rig):
    with pytest.raises(NightShiftContractError, match="trusted execution admission"):
        bridge(rig, admit=False).execute(rig[2])
    assert not (rig[2].worktree / "result.txt").exists()
    assert rig[1].events(workflow_id=f"child-bridge:{rig[2].task_id}") == ()


def test_binary_identity_change_fails_before_intent(rig):
    tampered = replace(rig[2], executable_sha256="0" * 64)
    with pytest.raises(NightShiftContractError, match="identity mismatch"):
        bridge(rig).execute(tampered)
    assert rig[1].events(workflow_id=f"child-bridge:{tampered.task_id}") == ()


def test_stale_lease_is_not_taken_over(rig):
    plan = replace(rig[2], lease_id="foreign-lease")
    with pytest.raises(NightShiftContractError, match="stale lease"):
        bridge(rig).execute(plan)


def test_existing_hermes_lease_is_never_preempted(tmp_path: Path, rig):
    leases, _, plan = rig
    lease = leases.acquire(
        task_id="HERMES-TASK",
        lease_id="hermes-running",
        worker_id="Hermes",
        now_epoch=int(time.time()),
        ttl_seconds=90,
    )
    assert lease.worker_id == "Hermes"
    forbidden = replace(
        plan, task_id="HERMES-TASK", lease_id="bridge-pretend",
        fencing_token=lease.fencing_token
    )
    with pytest.raises(NightShiftContractError, match="stale lease"):
        bridge(rig).execute(forbidden)
    current = leases.require_current(
        task_id="HERMES-TASK",
        lease_id="hermes-running",
        fencing_token=lease.fencing_token,
        now_epoch=int(time.time()),
    )
    assert current.worker_id == "Hermes"


def test_unknown_reviewer_sandbox_refuses_execution(rig):
    reviewer = replace(rig[2], role="REVIEWER")
    with pytest.raises(NightShiftContractError, match="isolation is not attested"):
        bridge(rig).execute(reviewer)
    assert rig[1].events(workflow_id=f"child-bridge:{reviewer.task_id}") == ()


def test_separately_attested_reviewer_uses_same_fenced_runtime(rig):
    plan = replace(
        rig[2], role="REVIEWER",
        arguments=("-c", "from pathlib import Path; Path('baseline.txt').read_text()"),
    )
    evidence = bridge(rig, reviewer=True).execute(plan)
    assert evidence.role == "REVIEWER"
    assert evidence.status == "EXITED_ZERO"


def test_child_timeout_is_killed_and_requires_reconciliation(rig):
    plan = replace(
        rig[2],
        arguments=("-c", "import time; time.sleep(2)"),
        timeout_seconds=0.65,
        no_progress_seconds=0.65,
    )
    runner = bridge(rig)
    with pytest.raises(NightShiftContractError, match="timeout"):
        runner.execute(plan)
    events = rig[1].events(workflow_id=f"child-bridge:{plan.task_id}")
    assert [e.event_type for e in events][-1] == "CHILD_ABORTED"
    with pytest.raises(NightShiftContractError, match="reconcile first"):
        runner.execute(plan)


def test_no_progress_timeout_is_fail_closed(rig):
    plan = replace(
        rig[2],
        arguments=("-c", "import time; time.sleep(2)"),
        timeout_seconds=1.5,
        no_progress_seconds=0.55,
    )
    with pytest.raises(NightShiftContractError, match="without meaningful progress"):
        bridge(rig).execute(plan)


def test_synthetic_content_progress_writes_only_digest_to_journal(rig):
    program = (
        "from pathlib import Path; import time; "
        "p=Path('.night-shift-progress'); "
        "p.write_text('one'); time.sleep(0.3); "
        "p.write_text('two'); time.sleep(0.3)"
    )
    plan = replace(
        rig[2],
        arguments=("-c", program),
        no_progress_seconds=1.2,
        timeout_seconds=2,
    )
    evidence = bridge(rig).execute(plan)
    assert evidence.status == "EXITED_ZERO"
    assert len(evidence.progress_digest or "") == 64
    progress = [
        e for e in rig[1].events(workflow_id=f"child-bridge:{plan.task_id}")
        if e.event_type == "CHILD_PROGRESS"
    ]
    assert progress and all("sha256" in e.payload for e in progress)
    assert all("one" not in str(e.payload) for e in progress)


def test_prior_crashed_launch_intent_blocks_blind_restart(rig):
    _, journal, plan = rig
    journal.append_event(
        event_id=f"child-bridge:{plan.task_id}:intent",
        workflow_id=f"child-bridge:{plan.task_id}",
        event_type="CHILD_LAUNCH_INTENT",
        payload={"plan_digest": plan.digest(), "role": plan.role},
        created_at_epoch=int(time.time()),
    )
    with pytest.raises(NightShiftContractError, match="reconcile first"):
        bridge(rig).execute(plan)
    assert not (plan.worktree / "result.txt").exists()


def test_parallel_claim_same_task_creates_at_most_one_child(rig):
    plan = replace(
        rig[2],
        arguments=("-c", "import time; time.sleep(0.3)"),
        no_progress_seconds=1,
    )
    runner = bridge(rig)
    def invoke():
        try:
            return runner.execute(plan).status
        except NightShiftContractError:
            return "BLOCKED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: invoke(), range(2)))
    assert sorted(results) == ["BLOCKED", "EXITED_ZERO"]
    events = rig[1].events(workflow_id=f"child-bridge:{plan.task_id}")
    assert sum(e.event_type == "CHILD_STARTED" for e in events) == 1


def test_refuses_non_task_branch_even_at_same_sha(rig):
    plan = rig[2]
    subprocess.run(
        ["git", "-C", str(plan.worktree), "checkout", "-qb", "main"],
        check=True,
    )
    with pytest.raises(NightShiftContractError, match="dedicated night-shift"):
        bridge(rig).execute(plan)
    assert rig[1].events(workflow_id=f"child-bridge:{plan.task_id}") == ()


def test_refuses_dirty_task_worktree_without_launch(rig):
    plan = rig[2]
    (plan.worktree / "unowned.txt").write_text("other work")
    with pytest.raises(NightShiftContractError, match="not clean"):
        bridge(rig).execute(plan)
    assert not (plan.worktree / "result.txt").exists()


def test_refuses_head_drift(rig):
    plan = rig[2]
    (plan.worktree / "fresh.txt").write_text("new revision")
    subprocess.run(
        ["git", "-C", str(plan.worktree), "add", "."], check=True
    )
    subprocess.run(
        [
            "git", "-C", str(plan.worktree),
            "-c", "user.name=Test", "-c", "user.email=synthetic.invalid",
            "commit", "-qm", "candidate drift",
        ],
        check=True,
    )
    with pytest.raises(NightShiftContractError, match="SHA drift"):
        bridge(rig).execute(plan)


def test_lease_loss_between_intent_and_spawn_blocks_child(rig, monkeypatch):
    leases, journal, plan = rig
    real_append = journal.append_event

    def expire_after_intent(**kwargs):
        accepted = real_append(**kwargs)
        if kwargs["event_type"] == "CHILD_LAUNCH_INTENT":
            with sqlite3.connect(leases.path) as con:
                con.execute(
                    "UPDATE leases SET expires_at_epoch=0 WHERE task_id=?",
                    (plan.task_id,),
                )
        return accepted

    monkeypatch.setattr(journal, "append_event", expire_after_intent)
    with pytest.raises(NightShiftContractError, match="expired"):
        bridge(rig).execute(plan)
    assert not (plan.worktree / "result.txt").exists()
    events = journal.events(workflow_id=f"child-bridge:{plan.task_id}")
    assert [e.event_type for e in events] == ["CHILD_LAUNCH_INTENT"]


def test_worker_identity_mismatch_cannot_impersonate_owner(rig):
    _, journal, plan = rig
    forged = replace(plan, worker_id="impersonator")
    with pytest.raises(NightShiftContractError, match="worker identity"):
        bridge(rig).execute(forged)
    assert journal.events(workflow_id=f"child-bridge:{plan.task_id}") == ()
    assert not (plan.worktree / "result.txt").exists()
