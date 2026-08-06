"""
Project domain LegalIssue into KnowledgeGraph.

Creates:
  - NodeType.ISSUE
  - EdgeType.RAISES  (Fact → Issue)
  - EdgeType.RESOLVES (Issue → Statute)
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

    Returns the created ISSUE node id.
    Does not invent missing Fact/Statute nodes – they must already exist
    or be passed explicitly.
    """
    issue.validate()

    node_id = f"issue:{issue.id}"

    if graph.has_node(node_id):
        return node_id

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
    graph.add_node(node)

    # RAISES: Fact → Issue
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
        graph.add_edge(edge)

    # RESOLVES: Issue → Statute
    for statute_id in statute_node_ids or []:
        if not graph.has_node(statute_id):
            continue
        edge = KnowledgeEdge(
            source=node_id,
            target=statute_id,
            type=EdgeType.RESOLVES,
            description=f"{node_id} resolves to {statute_id}",
            confidence=1.0,
        )
        edge.validate()
        graph.add_edge(edge)

    return node_id