"""Causal failure graph for root-cause-first remediation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .contracts import NightShiftContractError


class GateState(StrEnum):
    PASS = "PASS"
    FAIL_LOCAL = "FAIL_LOCAL"
    BLOCKED_BY = "BLOCKED_BY"
    WAITING_EXTERNAL = "WAITING_EXTERNAL"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class GateResult:
    gate_id: str
    state: GateState
    root_cause_id: str | None = None

    def __post_init__(self) -> None:
        gate_id = self.gate_id.strip()
        if not gate_id:
            raise NightShiftContractError("gate_id is required")
        object.__setattr__(self, "gate_id", gate_id)
        if self.state is GateState.BLOCKED_BY and not self.root_cause_id:
            raise NightShiftContractError("BLOCKED_BY requires root_cause_id")
        if self.state is not GateState.BLOCKED_BY and self.root_cause_id:
            raise NightShiftContractError(
                "root_cause_id is only valid for BLOCKED_BY"
            )


def root_failures(results: tuple[GateResult, ...]) -> tuple[GateResult, ...]:
    return tuple(
        sorted(
            (item for item in results if item.state is GateState.FAIL_LOCAL),
            key=lambda item: item.gate_id,
        )
    )


def actionable_failures(results: tuple[GateResult, ...]) -> tuple[GateResult, ...]:
    """Return only local root failures; blocked downstream symptoms are excluded."""
    roots = {item.gate_id for item in root_failures(results)}
    for item in results:
        if item.state is GateState.BLOCKED_BY and item.root_cause_id not in roots:
            raise NightShiftContractError(
                "BLOCKED_BY references a missing local root failure"
            )
    return root_failures(results)
