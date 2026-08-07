"""
CI regression gate for Case Factory v1.x.

Runs:
  1. Golden Case structure + hash (DS.3960.2025)
  2. II_Kp structure + integrity
  3. Cross-case isolation (domain)
  4. IntegrityEngine both cases

Exit 0 = PASS, 1 = FAIL
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from knowledge.integrity_engine import ExportStatus, IntegrityEngine
from knowledge.models.case_snapshot import compute_graph_hash
from knowledge.models.case_workspace import open_ds_3960, open_ii_kp_459_26
from knowledge.project_case import project_case
from knowledge.types import NodeType

MANIFEST = ROOT / "golden" / "DS.3960.2025" / "v1.0" / "manifest.json"
DOMAIN_TYPES = {
    NodeType.FACT,
    NodeType.ISSUE,
    NodeType.ARGUMENT,
    NodeType.EVIDENCE,
    NodeType.EVENT,
    NodeType.DECISION,
    NodeType.CASE,
}


def _fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def _ok(msg: str) -> None:
    print("OK:", msg)


def check_golden() -> None:
    if not MANIFEST.is_file():
        _fail(f"missing golden manifest: {MANIFEST}")
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ws = open_ds_3960()
    h = compute_graph_hash(ws.graph)
    if h != m["graph_hash"]:
        _fail(f"golden hash mismatch: {h} != {m['graph_hash']}")
    counts = {
        "evidence": sum(1 for n in ws.graph if n.type == NodeType.EVIDENCE),
        "facts": sum(1 for n in ws.graph if n.type == NodeType.FACT),
        "events": sum(1 for n in ws.graph if n.type == NodeType.EVENT),
        "issues": sum(1 for n in ws.graph if n.type == NodeType.ISSUE),
        "arguments": sum(1 for n in ws.graph if n.type == NodeType.ARGUMENT),
        "decisions": sum(1 for n in ws.graph if n.type == NodeType.DECISION),
    }
    if counts != m["counts"]:
        _fail(f"golden counts mismatch: {counts} != {m['counts']}")
    r = IntegrityEngine.run(ws.graph, ws.case)
    if r.blocks:
        _fail(f"golden integrity BLOCK: {r.blocks}")
    _ok(f"golden DS hash={h} counts={counts}")


def check_ii_kp() -> None:
    ws = open_ii_kp_459_26()
    if len(ws.case.facts) != 5 or len(ws.case.legal_issues) != 2:
        _fail("II_Kp unexpected domain size")
    r = IntegrityEngine.run(ws.graph, ws.case)
    if r.export_status == ExportStatus.BLOCKED or r.blocks:
        _fail(f"II_Kp integrity blocked: {r.report()}")
    _ok(f"II_Kp integrity={r.level.name} export={r.export_status.name}")


def check_isolation() -> None:
    a = open_ds_3960()
    b = open_ii_kp_459_26()
    if a.graph is b.graph or a.case is b.case:
        _fail("workspaces share objects")
    ids_a = {n.id for n in a.graph if n.type in DOMAIN_TYPES}
    ids_b = {n.id for n in b.graph if n.type in DOMAIN_TYPES}
    if not ids_a.isdisjoint(ids_b):
        _fail("domain node id overlap")
    ha, hb = compute_graph_hash(a.graph), compute_graph_hash(b.graph)
    if ha == hb:
        _fail("case hashes unexpectedly equal")
    hb_before = hb
    project_case(a.graph, a.case)
    if compute_graph_hash(b.graph) != hb_before:
        _fail("mutation of A changed hash of B")
    _ok(f"isolation domain A={len(ids_a)} B={len(ids_b)}")


def main() -> int:
    print("Case Factory CI gate")
    check_golden()
    check_ii_kp()
    check_isolation()
    print("CI GATE PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())