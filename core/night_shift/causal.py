"""Deterministic causal gate graph for root-cause-first remediation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.p3.contracts import content_digest, require_hex_digest

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
        root = self.root_cause_id.strip() if self.root_cause_id is not None else None
        if not gate_id:
            raise NightShiftContractError("gate_id is required")
        if self.state is GateState.BLOCKED_BY:
            if not root:
                raise NightShiftContractError("BLOCKED_BY requires root_cause_id")
            if root == gate_id:
                raise NightShiftContractError("gate cannot be BLOCKED_BY itself")
        elif root:
            raise NightShiftContractError(
                "root_cause_id is only valid for BLOCKED_BY"
            )
        object.__setattr__(self, "gate_id", gate_id)
        object.__setattr__(self, "root_cause_id", root)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "gate_id": self.gate_id,
            "state": self.state.value,
            "root_cause_id": self.root_cause_id,
        }


@dataclass(frozen=True, slots=True)
class RootCauseImpact:
    root_cause_id: str
    blocked_gate_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        root = self.root_cause_id.strip()
        blocked = tuple(sorted({item.strip() for item in self.blocked_gate_ids}))
        if not root or any(not item for item in blocked):
            raise NightShiftContractError("root-cause impact identifiers must be nonblank")
        if root in blocked:
            raise NightShiftContractError("root cause cannot be its own blocked symptom")
        object.__setattr__(self, "root_cause_id", root)
        object.__setattr__(self, "blocked_gate_ids", blocked)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "root_cause_id": self.root_cause_id,
            "blocked_gate_ids": list(self.blocked_gate_ids),
        }


@dataclass(frozen=True, slots=True)
class CausalRemediationPlan:
    graph_digest: str
    state_snapshot_digest: str
    impacts: tuple[RootCauseImpact, ...]

    def __post_init__(self) -> None:
        try:
            graph_digest = require_hex_digest(
                self.graph_digest,
                field_name="graph_digest",
            )
        except ValueError as exc:
            raise NightShiftContractError(str(exc)) from exc
        try:
            state_snapshot_digest = require_hex_digest(
                self.state_snapshot_digest,
                field_name="state_snapshot_digest",
            )
        except ValueError as exc:
            raise NightShiftContractError(str(exc)) from exc
        impacts = tuple(sorted(self.impacts, key=lambda item: item.root_cause_id))
        roots = [item.root_cause_id for item in impacts]
        if len(roots) != len(set(roots)):
            raise NightShiftContractError("duplicate root cause in remediation plan")
        object.__setattr__(self, "graph_digest", graph_digest)
        object.__setattr__(self, "state_snapshot_digest", state_snapshot_digest)
        object.__setattr__(self, "impacts", impacts)

    @property
    def actionable_root_ids(self) -> tuple[str, ...]:
        return tuple(item.root_cause_id for item in self.impacts)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": "night-shift-causal-remediation-plan/v1",
            "graph_digest": self.graph_digest,
            "state_snapshot_digest": self.state_snapshot_digest,
            "impacts": [item.canonical_dict() for item in self.impacts],
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class CausalGateGraph:
    state_snapshot_digest: str
    results: tuple[GateResult, ...]

    def __post_init__(self) -> None:
        try:
            state_snapshot_digest = require_hex_digest(
                self.state_snapshot_digest,
                field_name="state_snapshot_digest",
            )
        except ValueError as exc:
            raise NightShiftContractError(str(exc)) from exc
        ordered = tuple(sorted(self.results, key=lambda item: item.gate_id))
        ids = [item.gate_id for item in ordered]
        if len(ids) != len(set(ids)):
            raise NightShiftContractError("duplicate gate_id in causal graph")

        roots = {
            item.gate_id
            for item in ordered
            if item.state is GateState.FAIL_LOCAL
        }
        for item in ordered:
            if item.state is GateState.BLOCKED_BY:
                if item.root_cause_id not in roots:
                    raise NightShiftContractError(
                        "BLOCKED_BY references a missing local root failure"
                    )
        object.__setattr__(self, "state_snapshot_digest", state_snapshot_digest)
        object.__setattr__(self, "results", ordered)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": "night-shift-causal-gate-graph/v1",
            "state_snapshot_digest": self.state_snapshot_digest,
            "results": [item.canonical_dict() for item in self.results],
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())

    def root_failures(self) -> tuple[GateResult, ...]:
        return tuple(
            item for item in self.results if item.state is GateState.FAIL_LOCAL
        )

    def blocked_for_root(self, root_cause_id: str) -> tuple[GateResult, ...]:
        root = root_cause_id.strip()
        if not root:
            raise NightShiftContractError("root_cause_id is required")
        if root not in {item.gate_id for item in self.root_failures()}:
            raise NightShiftContractError("unknown local root failure")
        return tuple(
            item
            for item in self.results
            if item.state is GateState.BLOCKED_BY
            and item.root_cause_id == root
        )

    def remediation_plan(self) -> CausalRemediationPlan:
        impacts = tuple(
            RootCauseImpact(
                root_cause_id=root.gate_id,
                blocked_gate_ids=tuple(
                    item.gate_id for item in self.blocked_for_root(root.gate_id)
                ),
            )
            for root in self.root_failures()
        )
        return CausalRemediationPlan(
            self.digest(),
            self.state_snapshot_digest,
            impacts,
        )


def root_failures(
    results: tuple[GateResult, ...],
    *,
    state_snapshot_digest: str,
) -> tuple[GateResult, ...]:
    return CausalGateGraph(state_snapshot_digest, results).root_failures()


def actionable_failures(
    results: tuple[GateResult, ...],
    *,
    state_snapshot_digest: str,
) -> tuple[GateResult, ...]:
    """Return only local root failures; downstream symptoms are excluded."""
    return CausalGateGraph(state_snapshot_digest, results).root_failures()


def build_remediation_plan(
    results: tuple[GateResult, ...],
    *,
    state_snapshot_digest: str,
) -> CausalRemediationPlan:
    return CausalGateGraph(state_snapshot_digest, results).remediation_plan()
