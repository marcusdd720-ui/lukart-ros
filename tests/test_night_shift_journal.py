from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.journal import DurableEventJournal


def _journal(tmp_path: Path) -> DurableEventJournal:
    return DurableEventJournal(tmp_path / "night_shift.db")


def test_event_append_is_idempotent_and_replayable(tmp_path: Path) -> None:
    journal = _journal(tmp_path)

    assert journal.append_event(
        event_id="evt-1",
        workflow_id="wf-1",
        event_type="STATE_TRANSITION",
        payload={"to_state": "READY"},
        created_at_epoch=10,
    )
    assert not journal.append_event(
        event_id="evt-1",
        workflow_id="wf-1",
        event_type="STATE_TRANSITION",
        payload={"to_state": "READY"},
        created_at_epoch=10,
    )
    assert journal.append_event(
        event_id="evt-2",
        workflow_id="wf-1",
        event_type="STATE_TRANSITION",
        payload={"to_state": "RUNNING"},
        created_at_epoch=11,
    )

    assert journal.replay_state(workflow_id="wf-1") == "RUNNING"
    assert len(journal.verify_chain(workflow_id="wf-1")) == 2


def test_conflicting_event_id_fails_closed(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    journal.append_event(
        event_id="evt-conflict",
        workflow_id="wf-1",
        event_type="STATE_TRANSITION",
        payload={"to_state": "READY"},
        created_at_epoch=10,
    )

    with pytest.raises(NightShiftContractError, match="conflicting content"):
        journal.append_event(
            event_id="evt-conflict",
            workflow_id="wf-1",
            event_type="STATE_TRANSITION",
            payload={"to_state": "FAILED"},
            created_at_epoch=10,
        )
def test_replay_detects_tampered_payload(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    journal.append_event(
        event_id="evt-tamper",
        workflow_id="wf-1",
        event_type="STATE_TRANSITION",
        payload={"to_state": "READY"},
        created_at_epoch=10,
    )

    connection = sqlite3.connect(journal.path)
    try:
        connection.execute(
            "UPDATE events SET payload_json = ? WHERE event_id = ?",
            ('{"to_state":"CLOSED_PASS"}', "evt-tamper"),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(NightShiftContractError, match="event hash mismatch"):
        journal.verify_chain(workflow_id="wf-1")


def test_inbox_deduplicates_and_rejects_conflict(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    assert journal.record_inbox(
        idempotency_key="gh-123",
        source="github",
        payload={"run_id": 123},
    )
    assert not journal.record_inbox(
        idempotency_key="gh-123",
        source="github",
        payload={"run_id": 123},
    )

    with pytest.raises(NightShiftContractError, match="inbox idempotency conflict"):
        journal.record_inbox(
            idempotency_key="gh-123",
            source="github",
            payload={"run_id": 999},
        )


def test_outbox_is_idempotent_and_single_send(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    payload = {"repository": "marcusdd720-ui/lukart-ros", "branch": "task-1"}

    assert journal.enqueue_outbox(
        idempotency_key="push-task-1",
        action_type="PUSH_BRANCH",
        payload=payload,
    )
    assert not journal.enqueue_outbox(
        idempotency_key="push-task-1",
        action_type="PUSH_BRANCH",
        payload=payload,
    )

    pending = journal.pending_outbox()
    assert pending == (("push-task-1", "PUSH_BRANCH", payload),)

    journal.mark_outbox_sent(idempotency_key="push-task-1")
    assert journal.pending_outbox() == ()

    with pytest.raises(NightShiftContractError, match="missing or already sent"):
        journal.mark_outbox_sent(idempotency_key="push-task-1")


def test_invalid_state_transition_payload_fails_during_replay(tmp_path: Path) -> None:
    journal = _journal(tmp_path)
    journal.append_event(
        event_id="evt-invalid-state",
        workflow_id="wf-1",
        event_type="STATE_TRANSITION",
        payload={"unexpected": "value"},
        created_at_epoch=10,
    )

    with pytest.raises(NightShiftContractError, match="lacks to_state"):
        journal.replay_state(workflow_id="wf-1")
