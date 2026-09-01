"""
Project domain EvidenceItem into KnowledgeGraph.

Contract:
  - stable id: evidence:<domain_evidence.id>
  - NodeType.EVIDENCE
  - idempotent via ensure_node
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph
from knowledge.models.case import EvidenceItem
from knowledge.node import KnowledgeNode
from knowledge.types import NodeType


def evidence_node_id(evidence_id: str) -> str:
    if evidence_id.startswith("evidence:"):
        return evidence_id
    return f"evidence:{evidence_id}"


def project_evidence(graph: KnowledgeGraph, item: EvidenceItem) -> str:
    """
    Project a domain EvidenceItem into the graph.

    Returns the EVIDENCE node id.
    Safe to call repeatedly.
    """
    item.validate()
    node_id = evidence_node_id(item.id)

    label = (
        getattr(item, "label", "")
        or getattr(item, "title", "")
        or getattr(item, "source_ref", "")
        or node_id
    )
    weight = getattr(item, "weight", None)
    weight_name = (
        weight.name
        if weight is not None and hasattr(weight, "name")
        else str(weight or "")
    )

    node = KnowledgeNode(
        id=node_id,
        type=NodeType.EVIDENCE,
        name=str(label)[:120],
        description=str(getattr(item, "description", "") or label),
        metadata={
            "domain_id": item.id,
            "source_ref": getattr(item, "source_ref", "") or "",
            "weight": weight_name,
        },
        tags={"evidence"},
    )
    node.validate()
    graph.ensure_node(node)
    return node_id