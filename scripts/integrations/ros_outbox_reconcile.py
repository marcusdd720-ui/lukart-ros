"""Replay accepted control-journal tasks into the existing durable Hermes outbox."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from core.night_shift.authority import AuthorityBudgetStore
from core.night_shift.contracts import (
    AuthorityReservation,
    AutonomyEnvelope,
    ExecutionDecision,
    LiveStateSnapshot,
    NightShiftContractError,
    PolicyRef,
    PromotionMode,
    RiskClass,
    TaskCapsule,
    authorize_task,
)
from core.night_shift.journal import DurableEventJournal
from core.night_shift.task_intake import ACCEPTED, task_workflow
from scripts.integrations.ros_outbox import enqueue_task


def object_map(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise NightShiftContractError("accepted task object invalid")
    return dict(value)


def accepted_task_ids(
    journal: DurableEventJournal,
    *,
    authority: AuthorityBudgetStore,
    limit: int = 1000,
) -> tuple[str, ...]:
    """Verify every accepted event before enqueueing ANY; no partial tampered replay."""
    if not 1 <= limit <= 10000:
        raise ValueError("replay limit must be 1..10000")
    with closing(sqlite3.connect(journal.path)) as connection:
        rows = connection.execute(
            "SELECT DISTINCT workflow_id FROM events WHERE event_type=? "
            "ORDER BY workflow_id LIMIT ?",
            (ACCEPTED, limit + 1),
        ).fetchall()
    if len(rows) > limit:
        raise NightShiftContractError("accepted task replay bound exceeded")
    result = []
    for (workflow_id,) in rows:
        events = journal.verify_chain(workflow_id=workflow_id)
        accepted = [event for event in events if event.event_type == ACCEPTED]
        if len(accepted) != 1:
            raise NightShiftContractError("accepted task cardinality invalid")
        event = accepted[0]
        payload = event.payload
        if payload.get("schema_version") != 1:
            raise NightShiftContractError("unknown accepted task schema")
        raw = object_map(payload["task"])
        raw["risk_class"] = RiskClass(raw["risk_class"])
        for name in ("allowed_paths", "forbidden_paths", "acceptance_checks"):
            raw[name] = tuple(raw[name])
        task = TaskCapsule(**raw)
        if workflow_id != task_workflow(task.task_id) or payload["task_digest"] != task.digest():
            raise NightShiftContractError("accepted task identity mismatch")
        raw_state = object_map(payload["state"])
        raw_state["evidence_refs"] = tuple(raw_state["evidence_refs"])
        state = LiveStateSnapshot(**raw_state)
        raw_envelope = object_map(payload["envelope"])
        raw_envelope["repositories"] = tuple(raw_envelope["repositories"])
        raw_envelope["allowed_risk_classes"] = tuple(
            RiskClass(risk) for risk in raw_envelope["allowed_risk_classes"]
        )
        raw_envelope["promotion_mode"] = PromotionMode(raw_envelope["promotion_mode"])
        decision = authorize_task(
            policy=PolicyRef(**object_map(payload["policy"])),
            state=state,
            task=task,
            envelope=AutonomyEnvelope(**raw_envelope),
            reservation=AuthorityReservation(**object_map(payload["reservation"])),
            reservation_verifier=authority,
            now_epoch=event.created_at_epoch,
            decision_id=workflow_id,
        )
        stored = ExecutionDecision(**object_map(payload["decision"]))
        if decision != stored or payload["decision_digest"] != decision.digest():
            raise NightShiftContractError("accepted task authorization mismatch")
        result.append(task.task_id)
    return tuple(result)


def reconcile(
    *,
    journal: DurableEventJournal,
    authority: AuthorityBudgetStore,
    outbox_path: Path,
    limit: int = 1000,
) -> dict[str, int]:
    """Replay the source, including rows previously enqueued.

    No fragile watermark is advanced: a crash between source commit, enqueue or
    final acknowledgement leaves an immutable accepted event to replay.
    The legacy outbox's unique event key collapses every duplicate.
    """
    task_ids = accepted_task_ids(journal, authority=authority, limit=limit)
    inserted = sum(enqueue_task(task_id, db_path=outbox_path) for task_id in task_ids)
    return {"accepted": len(task_ids), "enqueued": inserted, "existing": len(task_ids) - inserted}
