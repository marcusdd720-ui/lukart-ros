from __future__ import annotations

import pytest

from core.night_shift.causal import (
    CausalGateGraph,
    CausalRemediationPlan,
    GateResult,
    GateState,
    RootCauseImpact,
    actionable_failures,
    build_remediation_plan,
)
from core.night_shift.contracts import NightShiftContractError

STATE = "a" * 64
OTHER_STATE = "b" * 64


def test_blocked_downstream_is_not_actionable() -> None:
    results = (
        GateResult("SEC.PII.001", GateState.FAIL_LOCAL),
        GateResult("STAGE0", GateState.BLOCKED_BY, "SEC.PII.001"),
        GateResult("CASE", GateState.BLOCKED_BY, "SEC.PII.001"),
    )
    assert [
        item.gate_id
        for item in actionable_failures(
            results,
            state_snapshot_digest=STATE,
        )
    ] == ["SEC.PII.001"]


def test_missing_root_cause_fails_closed() -> None:
    with pytest.raises(NightShiftContractError, match="missing local root failure"):
        actionable_failures(
            (GateResult("CASE", GateState.BLOCKED_BY, "SEC.PII.404"),),
            state_snapshot_digest=STATE,
        )


def test_duplicate_gate_id_fails_closed() -> None:
    with pytest.raises(NightShiftContractError, match="duplicate gate_id"):
        actionable_failures(
            (
                GateResult("ROOT", GateState.FAIL_LOCAL),
                GateResult("ROOT", GateState.PASS),
            ),
            state_snapshot_digest=STATE,
        )


def test_gate_cannot_block_itself() -> None:
    with pytest.raises(NightShiftContractError, match="itself"):
        GateResult("ROOT", GateState.BLOCKED_BY, "ROOT")


def test_remediation_plan_is_deterministic_and_content_addressed() -> None:
    a = (
        GateResult("ROOT.B", GateState.FAIL_LOCAL),
        GateResult("SYM.2", GateState.BLOCKED_BY, "ROOT.B"),
        GateResult("ROOT.A", GateState.FAIL_LOCAL),
        GateResult("SYM.1", GateState.BLOCKED_BY, "ROOT.A"),
        GateResult("PASS", GateState.PASS),
    )
    b = tuple(reversed(a))
    plan_a = build_remediation_plan(a, state_snapshot_digest=STATE)
    plan_b = build_remediation_plan(b, state_snapshot_digest=STATE)
    assert plan_a.actionable_root_ids == ("ROOT.A", "ROOT.B")
    assert plan_a.digest() == plan_b.digest()
    assert plan_a.state_snapshot_digest == STATE
    assert plan_a.impacts[0].blocked_gate_ids == ("SYM.1",)
    assert plan_a.impacts[1].blocked_gate_ids == ("SYM.2",)


def test_nonlocal_state_cannot_be_used_as_blocked_root() -> None:
    with pytest.raises(NightShiftContractError, match="missing local root failure"):
        actionable_failures(
            (
                GateResult("EXTERNAL", GateState.WAITING_EXTERNAL),
                GateResult("CASE", GateState.BLOCKED_BY, "EXTERNAL"),
            ),
            state_snapshot_digest=STATE,
        )


def test_remediation_plan_rejects_invalid_graph_digest() -> None:
    with pytest.raises(NightShiftContractError, match="graph_digest"):
        CausalRemediationPlan(
            "not-a-digest",
            STATE,
            (RootCauseImpact("ROOT", ("SYM",)),),
        )


def test_causal_graph_rejects_invalid_state_snapshot_digest() -> None:
    with pytest.raises(NightShiftContractError, match="state_snapshot_digest"):
        CausalGateGraph(
            "not-a-digest",
            (GateResult("ROOT", GateState.FAIL_LOCAL),),
        )


def test_state_snapshot_identity_changes_graph_and_plan_identity() -> None:
    results = (
        GateResult("ROOT", GateState.FAIL_LOCAL),
        GateResult("SYM", GateState.BLOCKED_BY, "ROOT"),
    )
    graph_a = CausalGateGraph(STATE, results)
    graph_b = CausalGateGraph(OTHER_STATE, results)
    plan_a = graph_a.remediation_plan()
    plan_b = graph_b.remediation_plan()
    assert graph_a.digest() != graph_b.digest()
    assert plan_a.digest() != plan_b.digest()
    assert plan_a.state_snapshot_digest == STATE
    assert plan_b.state_snapshot_digest == OTHER_STATE
