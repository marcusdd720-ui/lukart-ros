from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.night_shift.authority import AuthorityBudgetStore
from core.night_shift.contracts import (
    AutonomyEnvelope,
    NightShiftContractError,
    PromotionMode,
    RiskClass,
)
from core.night_shift.engine import LocalJournalWorkflowEngine
from core.night_shift.journal import DurableEventJournal
from core.night_shift.leases import LeaseStore


def _envelope() -> AutonomyEnvelope:
    return AutonomyEnvelope(
        envelope_id="fi-night",
        issued_at_epoch=1,
        expires_at_epoch=100,
        repositories=("repo",),
        allowed_risk_classes=(RiskClass.R1,),
        max_tasks=1,
        promotion_mode=PromotionMode.PREAUTHORIZED,
    )


def test_scheduler_restart_replays_last_committed_state(tmp_path: Path) -> None:
    db = tmp_path / "engine.db"
    first = LocalJournalWorkflowEngine(db)
    first.start(workflow_id="wf", initial_state="READY", created_at_epoch=1)
    first.transition(
        workflow_id="wf",
        event_id="wf:leased",
        to_state="LEASED",
        created_at_epoch=2,
    )
    first.transition(
        workflow_id="wf",
        event_id="wf:running",
        to_state="RUNNING",
        created_at_epoch=3,
    )

    restarted = LocalJournalWorkflowEngine(db)
    assert restarted.state(workflow_id="wf").state == "RUNNING"


def test_duplicate_event_delivery_is_idempotent(tmp_path: Path) -> None:
    journal = DurableEventJournal(tmp_path / "journal.db")
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
    assert first is True
    assert second is False


def test_stale_worker_cannot_mutate_after_lease_replacement(tmp_path: Path) -> None:
    store = LeaseStore(tmp_path / "leases.db")
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
    store.acquire(
        task_id="task",
        lease_id="new",
        worker_id="worker-b",
        now_epoch=3,
        ttl_seconds=10,
    )

    with pytest.raises(NightShiftContractError, match="stale lease or fencing token"):
        store.compare_and_swap_state(
            task_id="task",
            expected_version=1,
            new_state="RUNNING",
            lease_id=old.lease_id,
            fencing_token=old.fencing_token,
            now_epoch=4,
        )


def test_corrupted_journal_is_detected_on_replay(tmp_path: Path) -> None:
    journal = DurableEventJournal(tmp_path / "journal.db")
    journal.append_event(
        event_id="evt-1",
        workflow_id="wf",
        event_type="STATE_TRANSITION",
        payload={"to_state": "READY"},
        created_at_epoch=1,
    )

    connection = sqlite3.connect(journal.path)
    try:
        connection.execute(
            "UPDATE events SET previous_hash = ? WHERE event_id = ?",
            ("f" * 64, "evt-1"),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(NightShiftContractError, match="hash chain is broken"):
        journal.verify_chain(workflow_id="wf")


def test_authority_budget_remains_closed_after_restart(tmp_path: Path) -> None:
    db = tmp_path / "authority.db"
    first = AuthorityBudgetStore(db)
    envelope = _envelope()
    first.reserve_task(envelope=envelope, task_id="task-1", now_epoch=10)

    restarted = AuthorityBudgetStore(db)
    with pytest.raises(NightShiftContractError, match="task budget exhausted"):
        restarted.reserve_task(
            envelope=envelope,
            task_id="task-2",
            now_epoch=11,
        )


def test_worker_termination_during_validation_replays_validation_state(
    tmp_path: Path,
) -> None:
    db = tmp_path / "validation-restart.db"
    first = LocalJournalWorkflowEngine(db)
    first.start(workflow_id="wf", initial_state="READY", created_at_epoch=1)
    first.transition(
        workflow_id="wf",
        event_id="wf:leased",
        to_state="LEASED",
        created_at_epoch=2,
    )
    first.transition(
        workflow_id="wf",
        event_id="wf:running",
        to_state="RUNNING",
        created_at_epoch=3,
    )
    first.transition(
        workflow_id="wf",
        event_id="wf:validating",
        to_state="VALIDATING",
        created_at_epoch=4,
    )
    restarted = LocalJournalWorkflowEngine(db)
    assert restarted.state(workflow_id="wf").state == "VALIDATING"


def test_stale_worker_resume_is_rejected(tmp_path: Path) -> None:
    store = LeaseStore(tmp_path / "stale-resume.db")
    old = store.acquire(
        task_id="task",
        lease_id="old",
        worker_id="worker-a",
        now_epoch=1,
        ttl_seconds=2,
    )
    store.acquire(
        task_id="task",
        lease_id="new",
        worker_id="worker-b",
        now_epoch=3,
        ttl_seconds=10,
    )
    with pytest.raises(NightShiftContractError, match="stale lease or fencing token"):
        store.require_current(
            task_id="task",
            lease_id=old.lease_id,
            fencing_token=old.fencing_token,
            now_epoch=4,
        )


def test_network_loss_preserves_single_pending_outbox_action(tmp_path: Path) -> None:
    db = tmp_path / "network-loss.db"
    journal = DurableEventJournal(db)
    payload = {"branch": "night-shift/task", "sha": "a" * 40}
    assert journal.enqueue_outbox(
        idempotency_key="push:task",
        action_type="PUSH_BRANCH",
        payload=payload,
    )
    restarted = DurableEventJournal(db)
    assert restarted.pending_outbox() == (
        ("push:task", "PUSH_BRANCH", payload),
    )
    assert not restarted.enqueue_outbox(
        idempotency_key="push:task",
        action_type="PUSH_BRANCH",
        payload=payload,
    )


def test_delayed_ci_enters_waiting_external_without_promotion(tmp_path: Path) -> None:
    db = tmp_path / "delayed-ci.db"
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
    assert restarted.state(workflow_id="wf").state == "WAITING_EXTERNAL"


def test_v213_failure_suite_executes_all_required_scenarios(
    tmp_path: Path,
) -> None:
    from core.night_shift.failure_gate import (
        FailureOutcome,
        load_required_failure_scenarios,
    )
    from core.night_shift.failure_injection import run_failure_injection_suite

    policy_path = Path("docs/execution_profiles/NIGHT_SHIFT_POLICY_V2.yaml")
    required = load_required_failure_scenarios(policy_path)
    report = run_failure_injection_suite(
        root=tmp_path / "suite",
        subject_sha="c" * 40,
        state_snapshot_digest="d" * 64,
        task_capsule_digest="e" * 64,
        policy_digest="a" * 64,
        suite_profile_digest="b" * 64,
        now_epoch=10,
        ttl_seconds=100,
    )
    report.require_passed(
        required_scenarios=required,
        expected_subject_sha="c" * 40,
        expected_state_snapshot_digest="d" * 64,
        expected_task_capsule_digest="e" * 64,
        expected_policy_digest="a" * 64,
        expected_suite_profile_digest="b" * 64,
        now_epoch=10,
        expected_report_digest=report.digest(),
    )
    assert len(report.evidence) == 11
    assert all(
        item.outcome is not FailureOutcome.UNSAFE
        for item in report.evidence
    )
