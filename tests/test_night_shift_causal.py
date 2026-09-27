from __future__ import annotations

import pytest

from core.night_shift.causal import (
    GateResult,
    GateState,
    actionable_failures,
)
from core.night_shift.contracts import NightShiftContractError


def test_blocked_downstream_is_not_actionable() -> None:
    results = (
        GateResult("SEC.PII.001", GateState.FAIL_LOCAL),
        GateResult("STAGE0", GateState.BLOCKED_BY, "SEC.PII.001"),
        GateResult("CASE", GateState.BLOCKED_BY, "SEC.PII.001"),
    )
    assert [item.gate_id for item in actionable_failures(results)] == ["SEC.PII.001"]


def test_missing_root_cause_fails_closed() -> None:
    with pytest.raises(NightShiftContractError, match="missing local root failure"):
        actionable_failures(
            (GateResult("CASE", GateState.BLOCKED_BY, "SEC.PII.404"),)
        )
