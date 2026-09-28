"""Provider-neutral durable workflow engine contract and local journal adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .contracts import NightShiftContractError
from .journal import DurableEventJournal
from .state_machine import require_initial_phase, require_transition


@dataclass(frozen=True, slots=True)
class WorkflowState:
    workflow_id: str
    state: str


class DurableWorkflowEngine(Protocol):
    def start(
        self,
        *,
        workflow_id: str,
        initial_state: str,
        created_at_epoch: int,
    ) -> WorkflowState:
        ...

    def transition(
        self,
        *,
        workflow_id: str,
        event_id: str,
        to_state: str,
        created_at_epoch: int,
    ) -> WorkflowState:
        ...

    def state(self, *, workflow_id: str) -> WorkflowState:
        ...
class LocalJournalWorkflowEngine:
    """Minimal durable adapter backed by the append-only event journal."""

    def __init__(self, path: str | Path) -> None:
        self.journal = DurableEventJournal(path)

    @staticmethod
    def _text(value: str, *, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise NightShiftContractError(f"{field_name} is required")
        return normalized

    def start(
        self,
        *,
        workflow_id: str,
        initial_state: str,
        created_at_epoch: int,
    ) -> WorkflowState:
        workflow_id = self._text(workflow_id, field_name="workflow_id")
        initial_state = self._text(initial_state, field_name="initial_state")
        require_initial_phase(initial_state)
        event_id = f"{workflow_id}:start"

        existing = self.journal.events(workflow_id=workflow_id)
        if existing:
            first = existing[0]
            if (
                first.event_type != "STATE_TRANSITION"
                or first.payload.get("to_state") != initial_state
            ):
                raise NightShiftContractError(
                    "workflow restart conflicts with original initial state"
                )
            state = self.journal.replay_state(
                workflow_id=workflow_id,
                initial_state=initial_state,
            )
            return WorkflowState(workflow_id, state)

        self.journal.append_event(
            event_id=event_id,
            workflow_id=workflow_id,
            event_type="STATE_TRANSITION",
            payload={"to_state": initial_state},
            created_at_epoch=created_at_epoch,
        )
        return WorkflowState(workflow_id, initial_state)
    def transition(
        self,
        *,
        workflow_id: str,
        event_id: str,
        to_state: str,
        created_at_epoch: int,
    ) -> WorkflowState:
        workflow_id = self._text(workflow_id, field_name="workflow_id")
        event_id = self._text(event_id, field_name="event_id")
        to_state = self._text(to_state, field_name="to_state")
        if not self.journal.events(workflow_id=workflow_id):
            raise NightShiftContractError("workflow has not been started")

        current_state = self.journal.replay_state(workflow_id=workflow_id)
        require_transition(from_state=current_state, to_state=to_state)

        self.journal.append_event(
            event_id=event_id,
            workflow_id=workflow_id,
            event_type="STATE_TRANSITION",
            payload={"to_state": to_state},
            created_at_epoch=created_at_epoch,
        )
        return WorkflowState(
            workflow_id,
            self.journal.replay_state(workflow_id=workflow_id),
        )

    def state(self, *, workflow_id: str) -> WorkflowState:
        workflow_id = self._text(workflow_id, field_name="workflow_id")
        events = self.journal.events(workflow_id=workflow_id)
        if not events:
            raise NightShiftContractError("workflow has not been started")
        return WorkflowState(
            workflow_id,
            self.journal.replay_state(workflow_id=workflow_id),
        )
