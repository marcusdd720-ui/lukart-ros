from __future__ import annotations

from pathlib import Path

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.engine import LocalJournalWorkflowEngine


def test_engine_resumes_after_restart(tmp_path: Path) -> None:
    db = tmp_path / "engine.db"
    first = LocalJournalWorkflowEngine(db)
    first.start(workflow_id="wf-1", initial_state="READY", created_at_epoch=1)
    first.transition(
        workflow_id="wf-1",
        event_id="wf-1:leased",
        to_state="LEASED",
        created_at_epoch=2,
    )
    first.transition(
        workflow_id="wf-1",
        event_id="wf-1:running",
        to_state="RUNNING",
        created_at_epoch=3,
    )

    second = LocalJournalWorkflowEngine(db)
    assert second.state(workflow_id="wf-1").state == "RUNNING"


def test_transition_requires_started_workflow(tmp_path: Path) -> None:
    engine = LocalJournalWorkflowEngine(tmp_path / "engine.db")
    with pytest.raises(NightShiftContractError, match="has not been started"):
        engine.transition(
            workflow_id="wf-missing",
            event_id="evt",
            to_state="RUNNING",
            created_at_epoch=1,
        )


def test_restart_with_conflicting_initial_state_fails_closed(tmp_path: Path) -> None:
    db = tmp_path / "engine.db"
    engine = LocalJournalWorkflowEngine(db)
    engine.start(workflow_id="wf-1", initial_state="READY", created_at_epoch=1)

    with pytest.raises(
        NightShiftContractError,
        match="conflicts with original initial state",
    ):
        LocalJournalWorkflowEngine(db).start(
            workflow_id="wf-1",
            initial_state="DISCOVERED",
            created_at_epoch=2,
        )


def test_illegal_state_jump_fails_closed(tmp_path: Path) -> None:
    engine = LocalJournalWorkflowEngine(tmp_path / "engine.db")
    engine.start(workflow_id="wf-1", initial_state="READY", created_at_epoch=1)

    with pytest.raises(NightShiftContractError, match="transition not allowed"):
        engine.transition(
            workflow_id="wf-1",
            event_id="wf-1:skip",
            to_state="CLOSED_PASS",
            created_at_epoch=2,
        )
