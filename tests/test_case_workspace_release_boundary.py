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


def _stub_successful_analysis(
    workspace: CaseWorkspace,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(CaseWorkspace, "run_fact_agent", lambda self: 0)
    monkeypatch.setattr(CaseWorkspace, "run_law_agent", lambda self: 0)
    monkeypatch.setattr(CaseWorkspace, "build_authorities", lambda self: None)
    monkeypatch.setattr(CaseWorkspace, "render_dossier", lambda self, **kwargs: "ok")
    monkeypatch.setattr(
        CaseWorkspace,
        "export_dossier_txt",
        lambda self: tmp_path / "dossier.txt",
    )
    monkeypatch.setattr(CaseWorkspace, "run_review_agent", lambda self, path=None: 0)


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


def test_full_run_is_preparation_only_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    _stub_successful_analysis(workspace, monkeypatch, tmp_path)

    def unexpected_outbound(self: CaseWorkspace, **kwargs: object) -> list[Path]:
        raise AssertionError("default full run must not enter outbound boundary")

    monkeypatch.setattr(CaseWorkspace, "sync_outbound", unexpected_outbound)

    assert (
        workspace.run(
            save_snapshot=False,
            export_docx=False,
            write_note=False,
        )
        == 0
    )


def test_explicit_full_run_outbound_fails_closed_without_release_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = _workspace(tmp_path)
    _stub_successful_analysis(workspace, monkeypatch, tmp_path)

    assert (
        workspace.run(
            save_snapshot=False,
            export_docx=False,
            sync_outbound=True,
            write_note=False,
        )
        == 1
    )
    output = capsys.readouterr().out
    assert "cognitive_release_not_enforced" in output
    assert "WORKSPACE FAIL: Cognitive release" in output
