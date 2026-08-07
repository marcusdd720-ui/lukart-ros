"""
Project domain Argument into KnowledgeGraph.

Creates:
  - NodeType.ARGUMENT
  - EdgeType.ADVANCES (Argument → Issue)

Idempotent via ensure_node / ensure_edge.
"""

from __future__ import annotations

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.models.case import Argument
from knowledge.node import KnowledgeNode
from knowledge.types import EdgeType, NodeType


def project_argument(
    graph: KnowledgeGraph,
    argument: Argument,
    *,
    issue_node_id: str | None = None,
) -> str:
    """
    Project a domain Argument into the graph.

    Returns the ARGUMENT node id.
    Safe to call repeatedly.
    """
    argument.validate()

    node_id = f"argument:{argument.id}"

    node = KnowledgeNode(
        id=node_id,
        type=NodeType.ARGUMENT,
        name=argument.claim[:120],
        description=argument.claim,
        metadata={
            "domain_id": argument.id,
            "issue_id": argument.issue_id,
            "status": argument.status.name,
        },
        tags={"argument"},
    )
    node.validate()
    graph.ensure_node(node)

    target_issue = issue_node_id or f"issue:{argument.issue_id}"
    if graph.has_node(target_issue):
        edge = KnowledgeEdge(
            source=node_id,
            target=target_issue,
            type=EdgeType.ADVANCES,
            description=f"{node_id} advances {target_issue}",
            confidence=1.0,
        )
        edge.validate()
        graph.ensure_edge(edge)

    return node_id