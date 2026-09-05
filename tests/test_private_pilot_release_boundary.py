from __future__ import annotations

from scripts.local_private_pilot import PRIVATE_BLOCKED_STAGES, _private_stage_allowed


def test_private_pilot_blocks_legacy_outbound_and_release() -> None:
    assert PRIVATE_BLOCKED_STAGES == frozenset({"OUTBOUND", "RELEASE"})
    assert _private_stage_allowed("OUTBOUND") is False
    assert _private_stage_allowed("release") is False


def test_private_pilot_allows_local_analysis_stages() -> None:
    assert _private_stage_allowed(None) is True
    assert _private_stage_allowed("FACT") is True
    assert _private_stage_allowed("LAW") is True
    assert _private_stage_allowed("DOSSIER") is True
    assert _private_stage_allowed("REVIEW") is True
    assert _private_stage_allowed("FREEZE") is True
