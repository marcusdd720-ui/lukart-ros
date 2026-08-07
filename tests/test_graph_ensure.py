"""Tests for ensure_node / ensure_edge idempotency."""

from __future__ import annotations

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph, NodeAlreadyExists
from knowledge.node import KnowledgeNode
from knowledge.types import EdgeType, NodeType


def _node(nid: str, ntype: NodeType = NodeType.FACT) -> KnowledgeNode:
    n = KnowledgeNode(id=nid, type=ntype, name=nid)
    n.validate()
    return n


def _edge(src: str, tgt: str, etype: EdgeType = EdgeType.RAISES) -> KnowledgeEdge:
    e = KnowledgeEdge(
        source=src,
        target=tgt,
        type=etype,
        description=f"{src}->{tgt}",
        confidence=1.0,
    )
    e.validate()
    return e


def test_ensure_node_idempotent() -> None:
    g = KnowledgeGraph()
    n = _node("fact:1")
    a = g.ensure_node(n)
    b = g.ensure_node(n)
    assert a is b
    assert g.node_count() == 1


def test_add_node_still_raises() -> None:
    g = KnowledgeGraph()
    n = _node("fact:1")
    g.add_node(n)
    try:
        g.add_node(n)
        raised = False
    except NodeAlreadyExists:
        raised = True
    assert raised


def test_ensure_edge_idempotent() -> None:
    g = KnowledgeGraph()
    g.ensure_node(_node("fact:1"))
    g.ensure_node(_node("issue:1", NodeType.ISSUE))
    e = _edge("fact:1", "issue:1", EdgeType.RAISES)
    a = g.ensure_edge(e)
    b = g.ensure_edge(e)
    assert a is b
    assert g.edge_count() == 1


def test_ensure_edge_different_types_allowed() -> None:
    g = KnowledgeGraph()
    g.ensure_node(_node("a"))
    g.ensure_node(_node("b", NodeType.ISSUE))
    g.ensure_edge(_edge("a", "b", EdgeType.RAISES))
    g.ensure_edge(_edge("a", "b", EdgeType.SUPPORTS))
    assert g.edge_count() == 2


def test_triple_project_stable() -> None:
    g = KnowledgeGraph()
    for _ in range(3):
        g.ensure_node(_node("fact:x"))
        g.ensure_node(_node("issue:y", NodeType.ISSUE))
        g.ensure_edge(_edge("fact:x", "issue:y", EdgeType.RAISES))
    assert g.node_count() == 2
    assert g.edge_count() == 1