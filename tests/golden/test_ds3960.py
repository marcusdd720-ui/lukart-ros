"""Golden Case v1.0 — DS.3960.2025 regression oracle (reads frozen manifest)."""

from __future__ import annotations

import json
from pathlib import Path

from knowledge.integrity_engine import ExportStatus, IntegrityEngine
from knowledge.models.case_snapshot import CaseSnapshot, compute_graph_hash
from knowledge.models.case_workspace import open_ds_3960
from knowledge.types import NodeType

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "golden" / "DS.3960.2025" / "v1.0" / "manifest.json"


def _load_manifest() -> dict:
    assert MANIFEST_PATH.is_file(), f"Missing golden manifest: {MANIFEST_PATH}"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _counts(graph) -> dict[str, int]:
    return {
        "evidence": sum(1 for n in graph if n.type == NodeType.EVIDENCE),
        "facts": sum(1 for n in graph if n.type == NodeType.FACT),
        "events": sum(1 for n in graph if n.type == NodeType.EVENT),
        "issues": sum(1 for n in graph if n.type == NodeType.ISSUE),
        "arguments": sum(1 for n in graph if n.type == NodeType.ARGUMENT),
        "decisions": sum(1 for n in graph if n.type == NodeType.DECISION),
    }


def test_golden_manifest_present() -> None:
    m = _load_manifest()
    assert m["golden_case"] == "DS.3960.2025"
    assert m["version"] == "1.0"
    assert m["graph_hash"]
    assert m["status"] == "READY_TO_PUBLISH"


def test_golden_structure() -> None:
    m = _load_manifest()
    ws = open_ds_3960()
    assert _counts(ws.graph) == m["counts"]
    assert len(ws.case.facts) == m["counts"]["facts"]
    assert len(ws.case.legal_issues) == m["counts"]["issues"]
    assert len(ws.case.arguments) == m["counts"]["arguments"]
    assert len(ws.case.decisions) == m["counts"]["decisions"]


def test_golden_hash() -> None:
    m = _load_manifest()
    ws = open_ds_3960()
    h = compute_graph_hash(ws.graph)
    assert h == m["graph_hash"]


def test_golden_integrity_ready() -> None:
    ws = open_ds_3960()
    r = IntegrityEngine.run(ws.graph, ws.case)
    assert not r.blocks
    assert r.export_status in (
        ExportStatus.READY,
        ExportStatus.READY_WITH_WARNINGS,
    )


def test_golden_full_run() -> None:
    m = _load_manifest()
    ws = open_ds_3960()
    code = ws.run(
        author_name="Mariusz Brodziszewski",
        place="Poznań",
        subject="Stanowisko procesowe — VW Transporter",
        recipient_lines=["Prokuratura Rejonowa Poznań-Wilda"],
        export_docx=False,
    )
    assert code == 0
    assert ws.fact_ok is True
    assert ws.law_ok is True
    assert ws.review_ok is True
    assert ws.last_snapshot_path is not None
    snap = CaseSnapshot.load(ws.last_snapshot_path)
    assert snap.status == "READY_TO_PUBLISH"
    assert snap.graph_hash == m["graph_hash"]
    assert compute_graph_hash(ws.graph) == m["graph_hash"]