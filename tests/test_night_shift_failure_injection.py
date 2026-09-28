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
