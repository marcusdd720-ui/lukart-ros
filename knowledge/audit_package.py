"""
G3 Audit Package — enterprise provenance for a case run.

Common contract derived from Golden Case (DS) + Case #2 (II_Kp):

  case identity
  graph_hash (semantic)
  versions (pipeline / registry / knowledge)
  structural counts
  agent flags
  integrity export status
  snapshot status
  dossier hash (if present)
  git provenance

Write-only artifact. Does not mutate domain or graph.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from knowledge.integrity_engine import IntegrityEngine, IntegrityReport
from knowledge.models.case_snapshot import (
    KNOWLEDGE_VERSION,
    PIPELINE_VERSION,
    REGISTRY_VERSION,
    CaseSnapshot,
    compute_graph_hash,
)
from knowledge.types import EdgeType, NodeType

AUDIT_SCHEMA = "lukart.audit.v1"


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


@dataclass(slots=True)
class AuditPackage:
    schema: str = AUDIT_SCHEMA
    generated_at: str = ""
    case_key: str = ""
    signature: str = ""
    graph_case_id: str = ""

    pipeline_version: str = PIPELINE_VERSION
    registry_version: str = REGISTRY_VERSION
    knowledge_version: str = KNOWLEDGE_VERSION
    graph_hash: str = ""

    counts: dict[str, int] = field(default_factory=dict)
    relations: dict[str, int] = field(default_factory=dict)

    flags: dict[str, bool | None] = field(default_factory=dict)
    integrity_level: str = ""
    export_status: str = ""
    snapshot_status: str = ""
    snapshot_phase: str = ""
    exit_ready: bool = False

    dossier_path: str | None = None
    dossier_sha256: str | None = None
    git_commit: str | None = None
    git_dirty: bool | None = None

    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path.resolve()


def _counts(graph: Any) -> dict[str, int]:
    return {
        "evidence": sum(1 for n in graph if n.type == NodeType.EVIDENCE),
        "facts": sum(1 for n in graph if n.type == NodeType.FACT),
        "events": sum(1 for n in graph if n.type == NodeType.EVENT),
        "issues": sum(1 for n in graph if n.type == NodeType.ISSUE),
        "arguments": sum(1 for n in graph if n.type == NodeType.ARGUMENT),
        "decisions": sum(1 for n in graph if n.type == NodeType.DECISION),
        "nodes": int(graph.node_count()),
        "edges": int(graph.edge_count()),
    }


def _relations(graph: Any) -> dict[str, int]:
    return {
        "supports": sum(1 for e in graph.edges if e.type == EdgeType.SUPPORTS),
        "references": sum(1 for e in graph.edges if e.type == EdgeType.REFERENCES),
        "raises": sum(1 for e in graph.edges if e.type == EdgeType.RAISES),
        "advances": sum(1 for e in graph.edges if e.type == EdgeType.ADVANCES),
        "resolves": sum(1 for e in graph.edges if e.type == EdgeType.RESOLVES),
        "relies_on": sum(1 for e in graph.edges if e.type == EdgeType.RELIES_ON),
    }


def build_audit_package(
    workspace: Any,
    *,
    integrity: IntegrityReport | None = None,
    snapshot: CaseSnapshot | None = None,
) -> AuditPackage:
    """Build audit package from live workspace (+ optional prior reports)."""
    if integrity is None:
        integrity = IntegrityEngine.run(workspace.graph, workspace.case)

    graph_hash = compute_graph_hash(workspace.graph)
    case = workspace.case

    dossier_path = None
    dossier_sha = None
    if snapshot is not None:
        dossier_path = snapshot.dossier_path
        dossier_sha = snapshot.dossier_sha256
        snap_status = snapshot.status
        snap_phase = snapshot.phase
        git_commit = snapshot.git_commit
        git_dirty = snapshot.git_dirty
    else:
        snap_status = ""
        snap_phase = ""
        git_commit = None
        git_dirty = None
        candidate = workspace.output_dir / "stanowisko_dossier_with_authorities.txt"
        if candidate.is_file():
            import hashlib

            dossier_path = str(candidate.as_posix())
            h = hashlib.sha256()
            with candidate.open("rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            dossier_sha = h.hexdigest()

    flags = {
        "fact": workspace.fact_ok,
        "law": workspace.law_ok,
        "review": workspace.review_ok,
    }
    exit_ready = (
        workspace.fact_ok is True
        and workspace.law_ok is True
        and workspace.review_ok is True
        and integrity.export_status.name in ("READY", "READY_WITH_WARNINGS")
        and (snap_status in ("", "READY_TO_PUBLISH", "PASS_LOCAL"))
    )

    return AuditPackage(
        generated_at=_utc_stamp(),
        case_key=str(workspace.key),
        signature=(case.signature or "").strip(),
        graph_case_id=str(workspace.graph_case_id),
        pipeline_version=PIPELINE_VERSION,
        registry_version=REGISTRY_VERSION,
        knowledge_version=KNOWLEDGE_VERSION,
        graph_hash=graph_hash,
        counts=_counts(workspace.graph),
        relations=_relations(workspace.graph),
        flags=flags,
        integrity_level=integrity.level.name,
        export_status=integrity.export_status.name,
        snapshot_status=snap_status,
        snapshot_phase=snap_phase,
        exit_ready=exit_ready,
        dossier_path=dossier_path,
        dossier_sha256=dossier_sha,
        git_commit=git_commit,
        git_dirty=git_dirty,
        meta={
            "display_title": case.display_title(),
            "domain_summary": case.summary(),
        },
    )


def save_audit_package(
    workspace: Any,
    *,
    snapshot: CaseSnapshot | None = None,
    filename: str = "audit_package.json",
) -> Path:
    """Write audit package under output/cases/<key>/."""
    if snapshot is None and workspace.last_snapshot_path:
        try:
            snapshot = CaseSnapshot.load(workspace.last_snapshot_path)
        except Exception:  # noqa: BLE001
            snapshot = None

    pkg = build_audit_package(workspace, snapshot=snapshot)
    path = Path(workspace.output_dir) / filename
    return pkg.write(path)


def main() -> int:
    from knowledge.models.case_workspace import open_ds_3960, open_ii_kp_459_26

    for open_fn, name in ((open_ds_3960, "DS"), (open_ii_kp_459_26, "II")):
        ws = open_fn()
        path = save_audit_package(ws)
        print(name, path)
        data = json.loads(path.read_text(encoding="utf-8"))
        print(
            " ",
            data["graph_hash"],
            data["export_status"],
            data["counts"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())