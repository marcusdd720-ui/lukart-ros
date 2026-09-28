"""Crash/restart pilot for durable workflow adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .engine import DurableWorkflowEngine


@dataclass(frozen=True, slots=True)
class RuntimePilotResult:
    workflow_id: str
    state_before_restart: str
    state_after_restart: str
    final_state: str

    @property
    def passed(self) -> bool:
        return (
            self.state_before_restart == "RUNNING"
            and self.state_after_restart == "RUNNING"
            and self.final_state == "VALIDATING"
        )


def run_restart_pilot(
    factory: Callable[[], DurableWorkflowEngine], *, workflow_id: str = "runtime-pilot"
) -> RuntimePilotResult:
    first = factory()
    first.start(workflow_id=workflow_id, initial_state="READY", created_at_epoch=1)
    first.transition(
        workflow_id=workflow_id,
        event_id=f"{workflow_id}:lease",
        to_state="LEASED",
        created_at_epoch=2,
    )
    before = first.transition(
        workflow_id=workflow_id,
        event_id=f"{workflow_id}:run",
        to_state="RUNNING",
        created_at_epoch=3,
    )
    second = factory()
    after = second.state(workflow_id=workflow_id)
    final = second.transition(
        workflow_id=workflow_id,
        event_id=f"{workflow_id}:validate",
        to_state="VALIDATING",
        created_at_epoch=4,
    )
    return RuntimePilotResult(workflow_id, before.state, after.state, final.state)
