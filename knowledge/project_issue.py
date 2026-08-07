"""
Project domain LegalIssue into KnowledgeGraph.

Creates:
  - NodeType.ISSUE
  - EdgeType.RAISES     (Fact → Issue)
  - EdgeType.RELIES_ON  (Issue → Statute / CaseLaw)  — legal basis
  - RESOLVES reserved for later Decision linkage

Idempotent via ensure_node / ensure_edge.
"""

from __future__ import annotations

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.models.case import LegalIssue
from knowledge.node import KnowledgeNode
from knowledge.types import EdgeType, NodeType


def project_legal_issue(
    graph: KnowledgeGraph,
    issue: LegalIssue,
    *,
    fact_node_ids: list[str] | None = None,
    statute_node_ids: list[str] | None = None,
) -> str:
    """
    Project a domain LegalIssue into the graph.

    Returns the ISSUE node id.
    Fact/Statute nodes must already exist (or be passed explicitly).
    Safe to call repeatedly.
    """
    issue.validate()

    node_id = f"issue:{issue.id}"

    node = KnowledgeNode(
        id=node_id,
        type=NodeType.ISSUE,
        name=issue.question[:120],
        description=issue.hypothesis or issue.question,
        metadata={
            "domain_id": issue.id,
            "status": issue.status.name,
            "statute_refs": list(issue.statute_refs),
            "case_law_refs": list(issue.case_law_refs),
        },
        tags={"issue", "legal_issue"},
    )
    node.validate()
    graph.ensure_node(node)

    for fact_id in fact_node_ids or []:
        if not graph.has_node(fact_id):
            continue
        edge = KnowledgeEdge(
            source=fact_id,
            target=node_id,
            type=EdgeType.RAISES,
            description=f"{fact_id} raises {node_id}",
            confidence=1.0,
        )
        edge.validate()
        graph.ensure_edge(edge)

    # Issue ──RELIES_ON──→ Statute / CaseLaw (legal basis, not "resolved")
    for statute_id in statute_node_ids or []:
        if not graph.has_node(statute_id):
            continue
        edge = KnowledgeEdge(
            source=node_id,
            target=statute_id,
            type=EdgeType.RELIES_ON,
            description=f"{node_id} relies on {statute_id}",
            confidence=1.0,
        )
        edge.validate()
        graph.ensure_edge(edge)

    return node_id