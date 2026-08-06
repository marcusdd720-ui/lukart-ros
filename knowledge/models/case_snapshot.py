"""
CaseSnapshot v1 – immutable run record for a case workspace.

schema: lukart.snapshot.v1
Phases: OPEN | FREEZE | RELEASE
JSON = machine contract (not a human pleading).
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
    """Versioned snapshot of one workspace run / phase."""

    schema: str = SCHEMA
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = ""
    phase: str = "FREEZE"  # OPEN | FREEZE | RELEASE
    case_key: str = ""
    graph_case_id: str = ""
    legal_seed: str = LEGAL_SEED_DEFAULT
    graph_node_count: int = 0
    graph_edge_count: int = 0
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

    snap = CaseSnapshot(
        timestamp=stamp,
        phase=phase_u,
        case_key=str(workspace.key),
        graph_case_id=str(workspace.graph_case_id),
        legal_seed=LEGAL_SEED_DEFAULT,
        graph_node_count=int(workspace.graph.node_count()),
        graph_edge_count=int(workspace.graph.edge_count()),
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
    """Write immutable snapshot under output/cases/<key>/snapshots/."""
    snap = build_snapshot_from_workspace(
        workspace, repo_root=repo_root, phase=phase
    )
    out_dir = Path(workspace.output_dir) / "snapshots"
    filename = f"{snap.timestamp}_{snap.phase}_{snap.snapshot_id[:8]}.json"
    path = out_dir / filename
    snap.write(path)

    # latest pointers (overwritten on purpose – history stays in dated files)
    latest = out_dir / "latest.json"
    latest.write_text(
        json.dumps(snap.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    phase_latest = out_dir / f"latest_{snap.phase.lower()}.json"
    phase_latest.write_text(
        json.dumps(snap.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path.resolve()


def main() -> int:
    from knowledge.models.case_workspace import open_ds_3960

    ws = open_ds_3960()
    open_path = save_workspace_snapshot(ws, phase="OPEN")
    print("OPEN:", open_path)

    code = ws.run(
        author_name="Mariusz Brodziszewski",
        place="Poznań",
        subject=(
            "Stanowisko procesowe wraz z analizą materiału dowodowego "
            "— pojazd Volkswagen Transporter"
        ),
        recipient_lines=["Prokuratura Rejonowa Poznań-Wilda"],
        save_snapshot=True,
    )
    print("run exit:", code)
    return code


if __name__ == "__main__":
    raise SystemExit(main())