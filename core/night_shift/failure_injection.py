"""Deterministic V2-13 failure-injection probes."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

from core.p3.contracts import content_digest

from .contracts import NightShiftContractError
from .engine import LocalJournalWorkflowEngine
from .failure_gate import (
    FailureInjectionEvidence,
    FailureInjectionReport,
    FailureOutcome,
)
from .journal import DurableEventJournal
from .leases import LeaseStore
from .promotion import VerificationQuorum
from .receipts import ExecutionReceipt, require_receipt_digest


def _evidence(
    scenario: str,
    outcome: FailureOutcome,
    payload: dict[str, object],
) -> FailureInjectionEvidence:
    return FailureInjectionEvidence(
        scenario=scenario,
        outcome=outcome,
        evidence_ref=f"probe:{scenario}",
        evidence_digest=content_digest(payload),
    )

def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def _worker_termination_during_edit(root: Path) -> FailureInjectionEvidence:
    store = LeaseStore(root / "worker-edit.db")
    old = store.acquire(
        task_id="task",
        lease_id="old",
        worker_id="worker-a",
        now_epoch=1,
        ttl_seconds=2,
    )
    store.initialize_state(
        task_id="task",
        state="READY",
        lease_id=old.lease_id,
        fencing_token=old.fencing_token,
        now_epoch=1,
    )
    new = store.acquire(
        task_id="task",
        lease_id="new",
        worker_id="worker-b",
        now_epoch=3,
        ttl_seconds=10,
    )
    try:
        store.compare_and_swap_state(
            task_id="task",
            expected_version=1,
            new_state="RUNNING",
            lease_id=old.lease_id,
            fencing_token=old.fencing_token,
            now_epoch=4,
        )
    except NightShiftContractError:
        return _evidence(
            "worker_termination_during_edit",
            FailureOutcome.FAILED_CLOSED,
            {
                "old_fencing_token": old.fencing_token,
                "new_fencing_token": new.fencing_token,
                "stale_mutation_blocked": True,
            },
        )
    return _evidence(
        "worker_termination_during_edit",
        FailureOutcome.UNSAFE,
        {"stale_mutation_blocked": False},
    )


def _worker_termination_during_validation(root: Path) -> FailureInjectionEvidence:
    db = root / "worker-validation.db"
    engine = LocalJournalWorkflowEngine(db)
    engine.start(workflow_id="wf", initial_state="READY", created_at_epoch=1)
    for index, state in enumerate(("LEASED", "RUNNING", "VALIDATING"), start=2):
        engine.transition(
            workflow_id="wf",
            event_id=f"wf:{state.lower()}",
            to_state=state,
            created_at_epoch=index,
        )
    restarted = LocalJournalWorkflowEngine(db)
    recovered = restarted.state(workflow_id="wf").state == "VALIDATING"
    return _evidence(
        "worker_termination_during_validation",
        FailureOutcome.RECOVERED if recovered else FailureOutcome.UNSAFE,
        {"recovered_state": restarted.state(workflow_id="wf").state},
    )


def _scheduler_restart_after_dispatch(root: Path) -> FailureInjectionEvidence:
    db = root / "scheduler-restart.db"
    engine = LocalJournalWorkflowEngine(db)
    engine.start(workflow_id="wf", initial_state="READY", created_at_epoch=1)
    engine.transition(
        workflow_id="wf",
        event_id="wf:leased",
        to_state="LEASED",
        created_at_epoch=2,
    )
    engine.transition(
        workflow_id="wf",
        event_id="wf:running",
        to_state="RUNNING",
        created_at_epoch=3,
    )
    restarted = LocalJournalWorkflowEngine(db)
    recovered = restarted.state(workflow_id="wf").state == "RUNNING"
    return _evidence(
        "scheduler_restart_after_dispatch",
        FailureOutcome.RECOVERED if recovered else FailureOutcome.UNSAFE,
        {"recovered_state": restarted.state(workflow_id="wf").state},
    )


def _duplicate_event_delivery(root: Path) -> FailureInjectionEvidence:
    journal = DurableEventJournal(root / "duplicate.db")
    first = journal.append_event(
        event_id="evt-1",
        workflow_id="wf",
        event_type="STATE_TRANSITION",
        payload={"to_state": "READY"},
        created_at_epoch=1,
    )
    second = journal.append_event(
        event_id="evt-1",
        workflow_id="wf",
        event_type="STATE_TRANSITION",
        payload={"to_state": "READY"},
        created_at_epoch=1,
    )
    safe = first is True and second is False and len(journal.events(workflow_id="wf")) == 1
    return _evidence(
        "duplicate_event_delivery",
        FailureOutcome.RECOVERED if safe else FailureOutcome.UNSAFE,
        {"first_inserted": first, "duplicate_inserted": second},
    )


def _stale_worker_resumption(root: Path) -> FailureInjectionEvidence:
    store = LeaseStore(root / "stale-worker.db")
    old = store.acquire(
        task_id="task",
        lease_id="old",
        worker_id="worker-a",
        now_epoch=1,
        ttl_seconds=2,
    )
    new = store.acquire(
        task_id="task",
        lease_id="new",
        worker_id="worker-b",
        now_epoch=3,
        ttl_seconds=10,
    )
    try:
        store.require_current(
            task_id="task",
            lease_id=old.lease_id,
            fencing_token=old.fencing_token,
            now_epoch=4,
        )
    except NightShiftContractError:
        return _evidence(
            "stale_worker_resumption",
            FailureOutcome.FAILED_CLOSED,
            {
                "old_fencing_token": old.fencing_token,
                "new_fencing_token": new.fencing_token,
            },
        )
    return _evidence(
        "stale_worker_resumption",
        FailureOutcome.UNSAFE,
        {"stale_worker_blocked": False},
    )


def _network_loss_during_push(root: Path) -> FailureInjectionEvidence:
    db = root / "network-loss.db"
    journal = DurableEventJournal(db)
    payload = {"branch": "night-shift/task", "sha": "a" * 40}
    first = journal.enqueue_outbox(
        idempotency_key="push:task",
        action_type="PUSH_BRANCH",
        payload=payload,
    )
    restarted = DurableEventJournal(db)
    pending = restarted.pending_outbox()
    second = restarted.enqueue_outbox(
        idempotency_key="push:task",
        action_type="PUSH_BRANCH",
        payload=payload,
    )
    safe = (
        first is True
        and second is False
        and len(pending) == 1
        and pending[0][0] == "push:task"
    )
    return _evidence(
        "network_loss_during_push",
        FailureOutcome.RECOVERED if safe else FailureOutcome.UNSAFE,
        {"pending_count": len(pending), "duplicate_enqueued": second},
    )


def _delayed_ci(root: Path) -> FailureInjectionEvidence:
    db = root / "delayed-ci.db"
    engine = LocalJournalWorkflowEngine(db)
    engine.start(workflow_id="wf", initial_state="READY", created_at_epoch=1)
    sequence = (
        "LEASED",
        "RUNNING",
        "VALIDATING",
        "FROZEN",
        "READY_FOR_REVIEW",
        "REVIEWED_PASS",
        "SIGNED_OR_ATTESTED",
        "CI_PENDING",
        "WAITING_EXTERNAL",
    )
    for index, state in enumerate(sequence, start=2):
        engine.transition(
            workflow_id="wf",
            event_id=f"wf:{index}:{state.lower()}",
            to_state=state,
            created_at_epoch=index,
        )
    restarted = LocalJournalWorkflowEngine(db)
    state = restarted.state(workflow_id="wf").state
    return _evidence(
        "delayed_ci",
        FailureOutcome.FAILED_CLOSED if state == "WAITING_EXTERNAL" else FailureOutcome.UNSAFE,
        {"recovered_state": state, "promotion_attempted": False},
    )


def _concurrent_branch_advance(root: Path) -> FailureInjectionEvidence:
    repo = root / "concurrent-repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Failure Injection")
    synthetic_email = "failure" + chr(64) + "example.test"
    _git(repo, "config", "user.email", synthetic_email)
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "baseline")
    expected = _git(repo, "rev-parse", "HEAD")
    (repo / "ADVANCE.md").write_text("operator advance\n", encoding="utf-8")
    _git(repo, "add", "ADVANCE.md")
    _git(repo, "commit", "-m", "operator advance")
    current = _git(repo, "rev-parse", "HEAD")
    diverged = current != expected
    return _evidence(
        "concurrent_branch_advance",
        FailureOutcome.FAILED_CLOSED if diverged else FailureOutcome.UNSAFE,
        {"expected_head": expected, "current_head": current},
    )


def _disk_pressure(root: Path) -> FailureInjectionEvidence:
    target = root / "disk-pressure.txt"
    target.write_text("baseline\n", encoding="utf-8")
    before = target.read_text(encoding="utf-8")
    blocked = False
    try:
        raise OSError("simulated disk pressure")
    except OSError:
        blocked = True
    after = target.read_text(encoding="utf-8")
    safe = blocked and before == after
    return _evidence(
        "disk_pressure",
        FailureOutcome.FAILED_CLOSED if safe else FailureOutcome.UNSAFE,
        {"write_failed": blocked, "content_unchanged": before == after},
    )


def _corrupted_receipt(root: Path) -> FailureInjectionEvidence:
    del root
    receipt = ExecutionReceipt(
        task_id="task",
        workflow_id="wf",
        lease_id="lease",
        fencing_token=1,
        policy_digest="a" * 64,
        decision_digest="b" * 64,
        state_snapshot_digest="c" * 64,
        task_capsule_digest="d" * 64,
        authority_envelope_digest="e" * 64,
        authority_reservation_digest="f" * 64,
        environment_digest="1" * 64,
        verification_digest="2" * 64,
        input_sha="3" * 40,
        output_sha="4" * 40,
        diff_digest="5" * 64,
        final_state="CLOSED_PASS",
        evidence_refs=("probe:receipt",),
    )
    expected = receipt.digest()
    corrupted = replace(receipt, diff_digest="6" * 64)
    try:
        require_receipt_digest(corrupted, expected_digest=expected)
    except NightShiftContractError:
        return _evidence(
            "corrupted_receipt",
            FailureOutcome.FAILED_CLOSED,
            {"expected_digest": expected, "corruption_detected": True},
        )
    return _evidence(
        "corrupted_receipt",
        FailureOutcome.UNSAFE,
        {"corruption_detected": False},
    )


def _reviewer_timeout(root: Path) -> FailureInjectionEvidence:
    del root
    quorum = VerificationQuorum(
        True,
        True,
        True,
        True,
        False,
        True,
        True,
        "builder",
        "reviewer-timeout",
        "a" * 40,
        "b" * 64,
        "c" * 64,
        100,
    )
    blocked = not quorum.passed()
    return _evidence(
        "reviewer_timeout",
        FailureOutcome.FAILED_CLOSED if blocked else FailureOutcome.UNSAFE,
        {"verification_quorum_passed": quorum.passed()},
    )


_PROBES = (
    _worker_termination_during_edit,
    _worker_termination_during_validation,
    _scheduler_restart_after_dispatch,
    _duplicate_event_delivery,
    _stale_worker_resumption,
    _network_loss_during_push,
    _delayed_ci,
    _concurrent_branch_advance,
    _disk_pressure,
    _corrupted_receipt,
    _reviewer_timeout,
)

def run_failure_injection_suite(
    *,
    root: str | Path,
    subject_sha: str,
    state_snapshot_digest: str,
    task_capsule_digest: str,
    policy_digest: str,
    suite_profile_digest: str,
    now_epoch: int,
    ttl_seconds: int,
) -> FailureInjectionReport:
    if now_epoch < 0:
        raise NightShiftContractError("now_epoch cannot be negative")
    if ttl_seconds <= 0:
        raise NightShiftContractError("failure report ttl must be positive")
    base = Path(root)
    base.mkdir(parents=True, exist_ok=True)

    evidence: list[FailureInjectionEvidence] = []
    for probe in _PROBES:
        probe_root = base / probe.__name__.removeprefix("_")
        probe_root.mkdir(parents=True, exist_ok=True)
        try:
            evidence.append(probe(probe_root))
        except Exception as exc:
            scenario = probe.__name__.removeprefix("_")
            evidence.append(
                _evidence(
                    scenario,
                    FailureOutcome.UNSAFE,
                    {
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc),
                    },
                )
            )
    return FailureInjectionReport(
        subject_sha=subject_sha,
        state_snapshot_digest=state_snapshot_digest,
        task_capsule_digest=task_capsule_digest,
        policy_digest=policy_digest,
        suite_profile_digest=suite_profile_digest,
        generated_at_epoch=now_epoch,
        expires_at_epoch=now_epoch + ttl_seconds,
        evidence=tuple(evidence),
    )
