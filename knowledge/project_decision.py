"""
Project domain Decision into KnowledgeGraph.

Contract:
  - stable id: decision:<domain_decision.id>
  - NodeType.DECISION
  - EdgeType.RESOLVES: Issue → Decision (for decision.issue_ids)
  - idempotent via ensure_node / ensure_edge
"""

from __future__ import annotations

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.models.case import Decision
from knowledge.node import KnowledgeNode
from knowledge.types import EdgeType, NodeType


def decision_node_id(decision_id: str) -> str:
    if decision_id.startswith("decision:"):
        return decision_id
    return f"decision:{decision_id}"


def project_decision(graph: KnowledgeGraph, decision: Decision) -> str:
    """
    Project a domain Decision into the graph.

    Returns the DECISION node id.
    Wires Issue ──RESOLVES──→ Decision for known issue_ids.
    """
    decision.validate()
    node_id = decision_node_id(decision.id)

    node = KnowledgeNode(
        id=node_id,
        type=NodeType.DECISION,
        name=(decision.summary or "")[:120],
        description=decision.summary or "",
        metadata={
            "domain_id": decision.id,
            "kind": decision.kind.name,
            "issue_ids": list(decision.issue_ids),
            "argument_ids": list(getattr(decision, "argument_ids", None) or []),
        },
        tags={"decision"},
    )
    node.validate()
    graph.ensure_node(node)

    for iid in decision.issue_ids:
        issue_node = f"issue:{iid}" if not iid.startswith("issue:") else iid
        if not graph.has_node(issue_node):
            continue
        edge = KnowledgeEdge(
            source=issue_node,
            target=node_id,
            type=EdgeType.RESOLVES,
            description=f"{issue_node} resolves to {node_id}",
            confidence=1.0,
        )
        edge.validate()
        graph.ensure_edge(edge)

    return node_id