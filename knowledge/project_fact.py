"""
Project domain Fact into KnowledgeGraph.

Contract:
  - stable id: fact:<domain_fact.id>
  - NodeType.FACT
  - idempotent via ensure_node
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph
from knowledge.models.case import Fact
from knowledge.node import KnowledgeNode
from knowledge.types import NodeType


def fact_node_id(fact_id: str) -> str:
    """Stable graph id derived from domain Fact.id."""
    if fact_id.startswith("fact:"):
        return fact_id
    return f"fact:{fact_id}"


def project_fact(graph: KnowledgeGraph, fact: Fact) -> str:
    """
    Project a domain Fact into the graph.

    Returns the FACT node id.
    Safe to call repeatedly — ensure_node is idempotent.
    """
    fact.validate()
    node_id = fact_node_id(fact.id)

    node = KnowledgeNode(
        id=node_id,
        type=NodeType.FACT,
        name=(fact.statement or "")[:120],
        description=fact.statement or "",
        metadata={
            "domain_id": fact.id,
            "status": fact.status.name,
            "confidence": fact.confidence,
            "source_refs": list(fact.source_refs),
        },
        tags={"fact"},
    )
    node.validate()
    graph.ensure_node(node)
    return node_id