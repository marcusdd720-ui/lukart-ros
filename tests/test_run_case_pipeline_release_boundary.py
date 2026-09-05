from __future__ import annotations

from pathlib import Path

from knowledge.graph import KnowledgeGraph
from knowledge.models.case import Case
from knowledge.models.case_workspace import CaseWorkspace
from scripts.run_case_pipeline import _configure_release_boundary


def _workspace(tmp_path: Path) -> CaseWorkspace:
    return CaseWorkspace(
        key="CASE-1",
        graph_case_id="case:CASE-1",
        case=Case(id="CASE-1", title="", working_title="Case One"),
        graph=KnowledgeGraph(),
        root=tmp_path,
    )


def test_full_local_pipeline_disables_legacy_outbound(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    kwargs: dict[str, object] = {}

    _configure_release_boundary(workspace, None, kwargs)

    assert kwargs["sync_outbound"] is False
    assert workspace.cognitive_release_enforced is False


def test_explicit_outbound_enables_fail_closed_cognitive_guard(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    kwargs: dict[str, object] = {}

    _configure_release_boundary(workspace, "OUTBOUND", kwargs)

    assert workspace.cognitive_release_enforced is True
    assert workspace.run_stage("OUTBOUND") == 1


def test_explicit_release_enables_fail_closed_cognitive_guard(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    kwargs: dict[str, object] = {}

    _configure_release_boundary(workspace, "release", kwargs)

    assert workspace.cognitive_release_enforced is True
    assert workspace.run_stage("RELEASE") == 1


def test_analysis_stage_does_not_enable_release_guard(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    kwargs: dict[str, object] = {}

    _configure_release_boundary(workspace, "FACT", kwargs)

    assert workspace.cognitive_release_enforced is False
    assert "sync_outbound" not in kwargs
