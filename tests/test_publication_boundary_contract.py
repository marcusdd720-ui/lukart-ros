from __future__ import annotations

from pathlib import Path

from knowledge.graph import KnowledgeGraph
from knowledge.models.case import Case
from knowledge.models.case_snapshot import CaseSnapshot
from knowledge.models.case_workspace import CaseWorkspace


def _ready_workspace(tmp_path: Path) -> CaseWorkspace:
    workspace = CaseWorkspace(
        key="CASE-READY",
        graph_case_id="case:CASE-READY",
        case=Case(id="CASE-READY", title="", working_title="Ready Case"),
        graph=KnowledgeGraph(),
        root=tmp_path,
    )
    workspace.fact_ok = True
    workspace.law_ok = True
    workspace.review_ok = True

    workspace.output_dir.mkdir(parents=True, exist_ok=True)
    (workspace.output_dir / "stanowisko_dossier_with_authorities.txt").write_text(
        "local dossier\n",
        encoding="utf-8",
    )

    snapshot_path = workspace.save_snapshot(phase="FREEZE")
    snapshot = CaseSnapshot.load(snapshot_path)
    assert snapshot.status == "READY_TO_PUBLISH"
    return workspace


def test_ready_to_publish_is_preparation_only_without_release_authorization(
    tmp_path: Path,
) -> None:
    workspace = _ready_workspace(tmp_path)

    assert workspace.cognitive_release_enforced is False

    assert workspace.run_stage("OUTBOUND") == 1
    assert not workspace.outbound_dir.exists()

    assert workspace.run_stage("RELEASE") == 1
    assert not (workspace.output_dir / "snapshots" / "latest_release.json").exists()
