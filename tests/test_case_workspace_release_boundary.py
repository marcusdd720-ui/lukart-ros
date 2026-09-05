from __future__ import annotations

from pathlib import Path

import pytest

from knowledge.models.case_workspace import CaseWorkspace


def _workspace(tmp_path: Path) -> CaseWorkspace:
    return CaseWorkspace(
        key="CASE-TEST",
        graph_case_id="CASE-TEST",
        case=object(),  # type: ignore[arg-type]
        graph=object(),  # type: ignore[arg-type]
        root=tmp_path,
    )


def test_direct_sync_outbound_fails_closed_when_release_not_enforced(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)

    with pytest.raises(PermissionError, match="cognitive_release_not_enforced"):
        workspace.sync_outbound()

    assert not workspace.outbound_dir.exists()


def test_direct_release_stage_fails_closed_when_release_not_enforced(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = _workspace(tmp_path)

    assert workspace.run_stage("RELEASE") == 1
    assert "cognitive_release_not_enforced" in capsys.readouterr().out


def test_analysis_stage_does_not_require_cognitive_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    monkeypatch.setattr(CaseWorkspace, "run_fact_agent", lambda self: 0)

    assert workspace.run_stage("FACT") == 0


def test_enforced_release_without_binding_remains_blocked(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    workspace.cognitive_release_enforced = True

    with pytest.raises(PermissionError, match="release_binding_missing"):
        workspace.sync_outbound()
