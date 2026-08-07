"""
CaseSnapshot — immutable, reproducible run record.

schema: lukart.snapshot.v1
Phases: OPEN | FREEZE | RELEASE

graph_hash is semantic (type|name|description + edge endpoints),
not dependent on runtime UUIDs.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "lukart.snapshot.v1"
LEGAL_SEED_DEFAULT = "2026.08"
PIPELINE_VERSION = "1.5.0"
REGISTRY_VERSION = "1.0.0"
KNOWLEDGE_VERSION = "2026.08"
PHASES = ("OPEN", "FREEZE", "RELEASE")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_graph_hash(graph: Any) -> str:
    """
    Deterministic fingerprint independent of runtime UUIDs.

    Nodes:  type|name|description_prefix
    Edges:  src_label|edge_type|tgt_label
    """
    by_id = {n.id: n for n in graph}

    def _label(n: Any) -> str:
        t = getattr(n.type, "name", str(n.type))
        name = (n.name or "").strip()
        desc = (n.description or "").strip()[:80]
        return f"{t}|{name}|{desc}"

    node_lines = sorted(_label(n) for n in graph)
    edge_lines: list[str] = []
    for e in graph.edges:
        src = by_id.get(e.source)
        tgt = by_id.get(e.target)
        if src is None or tgt is None:
            continue
        et = getattr(e.type, "name", str(e.type))
        edge_lines.append(f"{_label(src)}|{et}|{_label(tgt)}")
    edge_lines.sort()
    payload = "NODES\n" + "\n".join(node_lines) + "\nEDGES\n" + "\n".join(edge_lines)
    return _sha256_text(payload)[:16]


def _git_info(repo: Path) -> tuple[str | None, bool | None]:
    try:
        import subprocess

        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=repo,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        dirty = bool(status.strip())
        return commit, dirty
    except Exception:  # noqa: BLE001
        return None, None


@dataclass(slots=True)
class CaseSnapshot:
    schema: str = SCHEMA
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = ""
    phase: str = "FREEZE"
    case_key: str = ""
    graph_case_id: str = ""
    legal_seed: str = LEGAL_SEED_DEFAULT
    knowledge_version: str = KNOWLEDGE_VERSION
    registry_version: str = REGISTRY_VERSION
    pipeline_version: str = PIPELINE_VERSION
    graph_hash: str = ""
    graph_node_count: int = 0
    graph_edge_count: int = 0
    legal_issue_count: int = 0
    argument_count: int = 0
    fact_node_count: int = 0
    evidence_node_count: int = 0
    event_node_count: int = 0
    decision_node_count: int = 0
    raises_count: int = 0
    advances_count: int = 0
    resolves_count: int = 0
    supports_count: int = 0
    references_count: int = 0
    fact_pass: bool | None = None
    law_pass: bool | None = None
    review_pass: bool | None = None
    workspace_pass: bool | None = None
    dossier_path: str | None = None
    dossier_sha256: str | None = None
    git_commit: str | None = None
    git_dirty: bool | None = None
    status: str = "UNKNOWN"
    meta: dict[str, Any] = field(default_factory=dict)

    def compute_status(self) -> str:
        flags = [self.fact_pass, self.law_pass, self.review_pass]
        if any(f is False for f in flags):
            self.status = "FAILED"
            return self.status
        if any(f is None for f in flags):
            self.status = "INCOMPLETE"
            return self.status
        if not self.dossier_path or not self.dossier_sha256:
            self.status = "PASS_LOCAL"
            return self.status
        if self.workspace_pass is False:
            self.status = "FAILED"
            return self.status
        self.status = "READY_TO_PUBLISH"
        return self.status

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

    @classmethod
    def load(cls, path: Path) -> CaseSnapshot:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema") != SCHEMA:
            raise ValueError(
                f"Unsupported snapshot schema: {data.get('schema')!r} "
                f"(expected {SCHEMA})"
            )
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


def build_snapshot_from_workspace(
    workspace: Any,
    *,
    repo_root: Path | None = None,
    phase: str = "FREEZE",
) -> CaseSnapshot:
    from knowledge.types import EdgeType, NodeType

    phase_u = (phase or "FREEZE").strip().upper()
    if phase_u not in PHASES:
        raise ValueError(f"Unknown snapshot phase: {phase!r}. Known: {PHASES}")

    root = Path(repo_root) if repo_root is not None else Path(workspace.root)
    ts = _utc_now()
    stamp = ts.strftime("%Y-%m-%dT%H-%M-%SZ")

    dossier_path: str | None = None
    dossier_hash: str | None = None
    out_candidate = workspace.output_dir / "stanowisko_dossier_with_authorities.txt"
    if out_candidate.is_file():
        dossier_path = str(out_candidate.as_posix())
        dossier_hash = _sha256_file(out_candidate)

    commit, dirty = _git_info(root)
    graph_hash = compute_graph_hash(workspace.graph)

    issue_count = len(getattr(workspace.case, "legal_issues", []) or [])
    argument_count = len(getattr(workspace.case, "arguments", []) or [])

    fact_node_count = sum(1 for n in workspace.graph if n.type == NodeType.FACT)
    evidence_node_count = sum(
        1 for n in workspace.graph if n.type == NodeType.EVIDENCE
    )
    event_node_count = sum(1 for n in workspace.graph if n.type == NodeType.EVENT)
    decision_node_count = sum(
        1 for n in workspace.graph if n.type == NodeType.DECISION
    )
    raises_count = sum(1 for e in workspace.graph.edges if e.type == EdgeType.RAISES)
    advances_count = sum(
        1 for e in workspace.graph.edges if e.type == EdgeType.ADVANCES
    )
    resolves_count = sum(
        1 for e in workspace.graph.edges if e.type == EdgeType.RESOLVES
    )
    supports_count = sum(
        1 for e in workspace.graph.edges if e.type == EdgeType.SUPPORTS
    )
    references_count = sum(
        1 for e in workspace.graph.edges if e.type == EdgeType.REFERENCES
    )

    snap = CaseSnapshot(
        timestamp=stamp,
        phase=phase_u,
        case_key=str(workspace.key),
        graph_case_id=str(workspace.graph_case_id),
        legal_seed=LEGAL_SEED_DEFAULT,
        knowledge_version=KNOWLEDGE_VERSION,
        registry_version=REGISTRY_VERSION,
        pipeline_version=PIPELINE_VERSION,
        graph_hash=graph_hash,
        graph_node_count=int(workspace.graph.node_count()),
        graph_edge_count=int(workspace.graph.edge_count()),
        legal_issue_count=issue_count,
        argument_count=argument_count,
        fact_node_count=fact_node_count,
        evidence_node_count=evidence_node_count,
        event_node_count=event_node_count,
        decision_node_count=decision_node_count,
        raises_count=raises_count,
        advances_count=advances_count,
        resolves_count=resolves_count,
        supports_count=supports_count,
        references_count=references_count,
        fact_pass=workspace.fact_ok,
        law_pass=workspace.law_ok,
        review_pass=workspace.review_ok,
        workspace_pass=(
            True
            if workspace.fact_ok and workspace.law_ok and workspace.review_ok
            else False
            if workspace.fact_ok is False
            or workspace.law_ok is False
            or workspace.review_ok is False
            else None
        ),
        dossier_path=dossier_path,
        dossier_sha256=dossier_hash,
        git_commit=commit,
        git_dirty=dirty,
        meta={
            "display_title": workspace.case.display_title(),
            "phase": phase_u,
            "graph_hash": graph_hash,
            "pipeline_version": PIPELINE_VERSION,
            "registry_version": REGISTRY_VERSION,
            "knowledge_version": KNOWLEDGE_VERSION,
        },
    )
    snap.compute_status()
    return snap


def save_workspace_snapshot(
    workspace: Any,
    *,
    repo_root: Path | None = None,
    phase: str = "FREEZE",
) -> Path:
    snap = build_snapshot_from_workspace(
        workspace, repo_root=repo_root, phase=phase
    )
    out_dir = Path(workspace.output_dir) / "snapshots"
    filename = f"{snap.timestamp}_{snap.phase}_{snap.snapshot_id[:8]}.json"
    path = out_dir / filename
    snap.write(path)
    payload = json.dumps(snap.to_dict(), ensure_ascii=False, indent=2) + "\n"
    (out_dir / "latest.json").write_text(payload, encoding="utf-8")
    (out_dir / f"latest_{snap.phase.lower()}.json").write_text(
        payload, encoding="utf-8"
    )
    return path.resolve()


def main() -> int:
    from knowledge.models.case_workspace import open_ds_3960

    ws = open_ds_3960()
    open_path = save_workspace_snapshot(ws, phase="OPEN")
    s = CaseSnapshot.load(open_path)
    print("graph_hash:", s.graph_hash)
    print("stable:", s.graph_hash == compute_graph_hash(ws.graph))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())