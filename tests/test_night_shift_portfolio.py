import pytest

from core.night_shift.contracts import NightShiftContractError, RiskClass
from core.night_shift.portfolio import PortfolioSnapshot, ProjectState

H = "a" * 40


def test_candidate_staleness_blocks_project() -> None:
    state = ProjectState(
        "L", "repo", H, "task", 90, RiskClass.R3, "b" * 40, "c" * 40, (), ("github:pr",)
    )
    assert state.candidate_stale
    assert not state.ready


def test_snapshot_expiry_fails_closed() -> None:
    snap = PortfolioSnapshot(
        "s",
        1,
        2,
        (ProjectState("A", "repo", H, "task", 50, RiskClass.R1, evidence_refs=("git:main",)),),
    )
    with pytest.raises(NightShiftContractError, match="stale"):
        snap.require_fresh(now_epoch=2)
