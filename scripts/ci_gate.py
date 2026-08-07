"""
CI regression gate for Case Factory v1.x.

  1. Golden Case DS.3960.2025 (strict hash + counts)
  2. Validation Case II_Kp (hash + counts + integrity)
  3. Cross-case domain isolation
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

GOLDEN_DS = ROOT / "golden" / "DS.3960.2025" / "v1.0" / "manifest.json"
VALID_II = ROOT / "golden" / "II_Kp_459_26" / "v1.0" / "manifest.json"
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


def _counts(graph) -> dict[str, int]:
    return {
        "evidence": sum(1 for n in graph if n.type == NodeType.EVIDENCE),
        "facts": sum(1 for n in graph if n.type == NodeType.FACT),
        "events": sum(1 for n in graph if n.type == NodeType.EVENT),
        "issues": sum(1 for n in graph if n.type == NodeType.ISSUE),
        "arguments": sum(1 for n in graph if n.type == NodeType.ARGUMENT),
        "decisions": sum(1 for n in graph if n.type == NodeType.DECISION),
    }


def check_golden_ds() -> None:
    if not GOLDEN_DS.is_file():
        _fail(f"missing golden manifest: {GOLDEN_DS}")
    m = json.loads(GOLDEN_DS.read_text(encoding="utf-8"))
    ws = open_ds_3960()
    h = compute_graph_hash(ws.graph)
    if h != m["graph_hash"]:
        _fail(f"DS hash mismatch: {h} != {m['graph_hash']}")
    if _counts(ws.graph) != m["counts"]:
        _fail(f"DS counts mismatch: {_counts(ws.graph)} != {m['counts']}")
    r = IntegrityEngine.run(ws.graph, ws.case)
    if r.blocks:
        _fail(f"DS integrity BLOCK: {r.blocks}")
    _ok(f"Golden Case       PASS  hash={h}")


def check_validation_ii() -> None:
    if not VALID_II.is_file():
        _fail(f"missing II_Kp validation manifest: {VALID_II}")
    m = json.loads(VALID_II.read_text(encoding="utf-8"))
    ws = open_ii_kp_459_26()
    h = compute_graph_hash(ws.graph)
    if h != m["graph_hash"]:
        _fail(f"II_Kp hash mismatch: {h} != {m['graph_hash']}")
    if _counts(ws.graph) != m["counts"]:
        _fail(f"II_Kp counts mismatch: {_counts(ws.graph)} != {m['counts']}")
    r = IntegrityEngine.run(ws.graph, ws.case)
    if r.export_status == ExportStatus.BLOCKED or r.blocks:
        _fail(f"II_Kp blocked: {r.report()}")
    _ok(f"II_Kp             PASS  hash={h} export={r.export_status.name}")


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
    _ok(f"Isolation         PASS  domain A={len(ids_a)} B={len(ids_b)}")


def main() -> int:
    print("CI GATE")
    print("─" * 40)
    check_golden_ds()
    check_validation_ii()
    check_isolation()
    print("─" * 40)
    print("CI GATE PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())