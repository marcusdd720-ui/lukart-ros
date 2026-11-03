"""Accepted Night Shift tasks persisted in the existing canonical control journal.

Acceptance is bounded by the existing policy/state/capsule/envelope authority gate.
The CASE ledger and execution leases are not used as task-creation authorities.
"""

from __future__ import annotations

import re

from .authority import AuthorityBudgetStore
from .contracts import (
    AutonomyEnvelope,
    LiveStateSnapshot,
    NightShiftContractError,
    PolicyRef,
    TaskCapsule,
    authorize_task,
)
from .journal import DurableEventJournal

ACCEPTED = "TASK_ACCEPTED_V1"
OPAQUE_TASK_ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z", re.ASCII)


def task_workflow(task_id: str) -> str:
    if not isinstance(task_id, str) or not OPAQUE_TASK_ID.fullmatch(task_id):
        raise NightShiftContractError("accepted task requires an opaque task ID")
    return "accepted-task:" + task_id


def accept_task(
    *,
    journal: DurableEventJournal,
    authority: AuthorityBudgetStore,
    policy: PolicyRef,
    state: LiveStateSnapshot,
    task: TaskCapsule,
    envelope: AutonomyEnvelope,
    now_epoch: int,
) -> bool:
    """Commit one immutable accepted task, or reconcile an identical retry.

    Durable journal append is the authoritative commit boundary. A caller crash
    after this method commits cannot lose delivery: the reconciler replays this
    event, without trusting an in-memory task or an enqueue callback.
    """
    workflow_id = task_workflow(task.task_id)
    # Validate BEFORE consuming a bounded authority reservation.
    state.require_fresh(now_epoch=now_epoch)
    envelope.require_authorized(
        repository=task.repository,
        risk_class=task.risk_class,
        now_epoch=now_epoch,
    )
    if task.repository != state.repository or task.state_snapshot_digest != state.digest():
        raise NightShiftContractError("accepted task state binding mismatch")
    if task.policy_digest != policy.policy_digest:
        raise NightShiftContractError("accepted task policy binding mismatch")
    reservation = authority.reserve_task(
        envelope=envelope,
        task_id=task.task_id,
        now_epoch=now_epoch,
    )
    decision = authorize_task(
        policy=policy,
        state=state,
        task=task,
        envelope=envelope,
        reservation=reservation,
        reservation_verifier=authority,
        now_epoch=now_epoch,
        decision_id=workflow_id,
    )
    payload = {
        "schema_version": 1,
        "task": task.canonical_dict(),
        "task_digest": task.digest(),
        "decision": decision.canonical_dict(),
        "decision_digest": decision.digest(),
        "policy": policy.canonical_dict(),
        "state": state.canonical_dict(),
        "envelope": envelope.canonical_dict(),
        "reservation": reservation.canonical_dict(),
    }
    existing = journal.verify_chain(workflow_id=workflow_id)
    if existing:
        accepted = [event for event in existing if event.event_type == ACCEPTED]
        if len(accepted) != 1 or accepted[0].payload != payload:
            raise NightShiftContractError("accepted task ID reused with conflicting content")
        return False
    return journal.append_event(
        event_id=workflow_id,
        workflow_id=workflow_id,
        event_type=ACCEPTED,
        payload=payload,
        created_at_epoch=now_epoch,
    )
