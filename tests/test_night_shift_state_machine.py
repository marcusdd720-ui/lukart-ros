from __future__ import annotations

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.state_machine import require_initial_phase, require_transition


def test_normal_transition_is_allowed() -> None:
    require_transition(from_state="READY", to_state="LEASED")
    require_transition(from_state="LEASED", to_state="RUNNING")


def test_skipping_validation_chain_is_rejected() -> None:
    with pytest.raises(NightShiftContractError, match="transition not allowed"):
        require_transition(from_state="READY", to_state="CLOSED_PASS")


def test_terminal_state_cannot_transition() -> None:
    with pytest.raises(NightShiftContractError, match="terminal workflow phase"):
        require_transition(from_state="CLOSED_PASS", to_state="READY")


def test_control_state_can_recover_to_ready() -> None:
    require_transition(from_state="BLOCKED", to_state="READY")


def test_unknown_state_fails_closed() -> None:
    with pytest.raises(NightShiftContractError, match="unknown workflow phase"):
        require_transition(from_state="READY", to_state="NOT_A_STATE")


def test_initial_phase_is_bounded() -> None:
    require_initial_phase("DISCOVERED")
    require_initial_phase("READY")
    with pytest.raises(NightShiftContractError, match="initial phase"):
        require_initial_phase("CLOSED_PASS")
