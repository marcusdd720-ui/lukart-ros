"""Fail-closed Night Shift workflow state machine."""

from __future__ import annotations

from enum import StrEnum

from .contracts import NightShiftContractError


class WorkflowPhase(StrEnum):
    DISCOVERED = "DISCOVERED"
    LIVE_STATE_VERIFIED = "LIVE_STATE_VERIFIED"
    READY = "READY"
    LEASED = "LEASED"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    FROZEN = "FROZEN"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    REVIEWED_PASS = "REVIEWED_PASS"
    SIGNED_OR_ATTESTED = "SIGNED_OR_ATTESTED"
    CI_PENDING = "CI_PENDING"
    READY_FOR_PROMOTION = "READY_FOR_PROMOTION"
    READY_FOR_HUMAN = "READY_FOR_HUMAN"
    LANDING = "LANDING"
    POST_LANDING_VERIFY = "POST_LANDING_VERIFY"
    CLOSED_PASS = "CLOSED_PASS"
    WAITING_EXTERNAL = "WAITING_EXTERNAL"
    BLOCKED = "BLOCKED"
    BLOCKED_BY = "BLOCKED_BY"
    FAILED = "FAILED"
    QUARANTINED = "QUARANTINED"
    SUPERSEDED = "SUPERSEDED"
    PAUSED = "PAUSED"


_NORMAL_NEXT: dict[WorkflowPhase, frozenset[WorkflowPhase]] = {
    WorkflowPhase.DISCOVERED: frozenset({WorkflowPhase.LIVE_STATE_VERIFIED}),
    WorkflowPhase.LIVE_STATE_VERIFIED: frozenset({WorkflowPhase.READY}),
    WorkflowPhase.READY: frozenset({WorkflowPhase.LEASED}),
    WorkflowPhase.LEASED: frozenset({WorkflowPhase.RUNNING}),
    WorkflowPhase.RUNNING: frozenset({WorkflowPhase.VALIDATING}),
    WorkflowPhase.VALIDATING: frozenset({WorkflowPhase.FROZEN}),
    WorkflowPhase.FROZEN: frozenset({WorkflowPhase.READY_FOR_REVIEW}),
    WorkflowPhase.READY_FOR_REVIEW: frozenset({WorkflowPhase.REVIEWED_PASS}),
    WorkflowPhase.REVIEWED_PASS: frozenset({WorkflowPhase.SIGNED_OR_ATTESTED}),
    WorkflowPhase.SIGNED_OR_ATTESTED: frozenset({WorkflowPhase.CI_PENDING}),
    WorkflowPhase.CI_PENDING: frozenset({WorkflowPhase.READY_FOR_PROMOTION}),
    WorkflowPhase.READY_FOR_PROMOTION: frozenset(
        {WorkflowPhase.READY_FOR_HUMAN, WorkflowPhase.LANDING}
    ),
    WorkflowPhase.READY_FOR_HUMAN: frozenset({WorkflowPhase.LANDING}),
    WorkflowPhase.LANDING: frozenset({WorkflowPhase.POST_LANDING_VERIFY}),
    WorkflowPhase.POST_LANDING_VERIFY: frozenset({WorkflowPhase.CLOSED_PASS}),
}

_CONTROL_TARGETS = frozenset(
    {
        WorkflowPhase.WAITING_EXTERNAL,
        WorkflowPhase.BLOCKED,
        WorkflowPhase.BLOCKED_BY,
        WorkflowPhase.FAILED,
        WorkflowPhase.QUARANTINED,
        WorkflowPhase.SUPERSEDED,
        WorkflowPhase.PAUSED,
    }
)

_RECOVERY_NEXT: dict[WorkflowPhase, frozenset[WorkflowPhase]] = {
    WorkflowPhase.WAITING_EXTERNAL: frozenset({WorkflowPhase.READY}),
    WorkflowPhase.BLOCKED: frozenset({WorkflowPhase.READY}),
    WorkflowPhase.BLOCKED_BY: frozenset({WorkflowPhase.READY}),
    WorkflowPhase.PAUSED: frozenset({WorkflowPhase.READY}),
}

_TERMINAL = frozenset(
    {
        WorkflowPhase.CLOSED_PASS,
        WorkflowPhase.FAILED,
        WorkflowPhase.QUARANTINED,
        WorkflowPhase.SUPERSEDED,
    }
)


def parse_phase(value: str) -> WorkflowPhase:
    try:
        return WorkflowPhase(value.strip())
    except ValueError as exc:
        raise NightShiftContractError(f"unknown workflow phase: {value!r}") from exc


def require_transition(*, from_state: str, to_state: str) -> None:
    source = parse_phase(from_state)
    target = parse_phase(to_state)

    if source in _TERMINAL:
        raise NightShiftContractError("terminal workflow phase cannot transition")

    allowed = set(_NORMAL_NEXT.get(source, frozenset()))
    allowed.update(_RECOVERY_NEXT.get(source, frozenset()))
    if source not in _CONTROL_TARGETS:
        allowed.update(_CONTROL_TARGETS)

    if target not in allowed:
        raise NightShiftContractError(
            f"workflow transition not allowed: {source.value} -> {target.value}"
        )


def require_initial_phase(state: str) -> None:
    phase = parse_phase(state)
    if phase not in {WorkflowPhase.DISCOVERED, WorkflowPhase.READY}:
        raise NightShiftContractError(
            "workflow initial phase must be DISCOVERED or READY"
        )
