"""
Projection Contract.

DOMAIN MODEL = source of truth
GRAPH = deterministic projection

project(X) ∘ project(X) ≡ project(X)
"""

from __future__ import annotations

from knowledge.models.case_workspace import open_ds_3960, open_ii_kp_459_26
from knowledge.project_case import project_case
from knowledge.types import EdgeType, NodeType


def _counts(graph):
    return {
        "nodes": graph.node_count(),
        "edges": graph.edge_count(),
        "evidence": sum(1 for n in graph if n.type == NodeType.EVIDENCE),
        "events": sum(1 for n in graph if n.type == NodeType.EVENT),
        "facts": sum(1 for n in graph if n.type == NodeType.FACT),
        "issues": sum(1 for n in graph if n.type == NodeType.ISSUE),
        "arguments": sum(1 for n in graph if n.type == NodeType.ARGUMENT),
        "raises": sum(1 for e in graph.edges if e.type == EdgeType.RAISES),
        "advances": sum(1 for e in graph.edges if e.type == EdgeType.ADVANCES),
        "supports": sum(1 for e in graph.edges if e.type == EdgeType.SUPPORTS),
        "references": sum(1 for e in graph.edges if e.type == EdgeType.REFERENCES),
    }


def test_ds3960_projection_idempotent() -> None:
    ws = open_ds_3960()
    c1 = _counts(ws.graph)
    project_case(ws.graph, ws.case)
    project_case(ws.graph, ws.case)
    c2 = _counts(ws.graph)
    assert c1 == c2
    assert c1["facts"] == len(ws.case.facts)
    assert c1["issues"] == len(ws.case.legal_issues)
    assert c1["arguments"] == len(ws.case.arguments)
    assert c1["evidence"] == len(ws.case.evidence_items)
    assert c1["events"] == len(ws.case.timeline_events)
    assert c1["advances"] == len(ws.case.arguments)


def test_ii_kp_projection_idempotent() -> None:
    ws = open_ii_kp_459_26()
    c1 = _counts(ws.graph)
    project_case(ws.graph, ws.case)
    c2 = _counts(ws.graph)
    assert c1 == c2
    assert c1["issues"] == len(ws.case.legal_issues)
    assert c1["arguments"] == len(ws.case.arguments)


def test_multi_case_independent() -> None:
    ws1 = open_ds_3960()
    ws2 = open_ii_kp_459_26()
    assert ws1.graph is not ws2.graph
    assert len(ws1.case.legal_issues) == 3
    assert len(ws2.case.legal_issues) == 2