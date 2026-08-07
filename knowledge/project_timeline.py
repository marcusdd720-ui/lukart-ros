"""
Project domain TimelineEvent into KnowledgeGraph.

Contract:
  - stable id: event:<domain_event.id>
  - NodeType.EVENT
  - EdgeType.REFERENCES: Event → Evidence (when event.evidence_ids present)
  - idempotent via ensure_node / ensure_edge
"""

from __future__ import annotations

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.models.case import TimelineEvent
from knowledge.node import KnowledgeNode
from knowledge.project_evidence import evidence_node_id
from knowledge.types import EdgeType, NodeType


def event_node_id(event_id: str) -> str:
    if event_id.startswith("event:"):
        return event_id
    return f"event:{event_id}"


def project_timeline_event(graph: KnowledgeGraph, event: TimelineEvent) -> str:
    """
    Project a domain TimelineEvent into the graph.

    Returns the EVENT node id.
    Safe to call repeatedly.
    Also wires Event ──REFERENCES──→ Evidence for known evidence_ids.
    """
    event.validate()
    node_id = event_node_id(event.id)

    label = (
        getattr(event, "event", "")
        or getattr(event, "label", "")
        or getattr(event, "title", "")
        or getattr(event, "date_label", "")
        or node_id
    )
    description = (
        getattr(event, "procedural_meaning", "")
        or getattr(event, "description", "")
        or getattr(event, "summary", "")
        or str(label)
    )

    node = KnowledgeNode(
        id=node_id,
        type=NodeType.EVENT,
        name=str(label)[:120],
        description=str(description),
        metadata={
            "domain_id": event.id,
            "date_label": getattr(event, "date_label", "") or "",
            "sort_key": getattr(event, "sort_key", "") or "",
            "source": getattr(event, "source", "") or "",
            "evidence_ids": list(getattr(event, "evidence_ids", None) or []),
            "fact_ids": list(getattr(event, "fact_ids", None) or []),
        },
        tags={"timeline", "event"},
    )
    node.validate()
    graph.ensure_node(node)

    # Event ──REFERENCES──→ Evidence
    for eid in getattr(event, "evidence_ids", None) or []:
        ev_id = evidence_node_id(eid)
        if not graph.has_node(ev_id):
            continue
        edge = KnowledgeEdge(
            source=node_id,
            target=ev_id,
            type=EdgeType.REFERENCES,
            description=f"{node_id} references {ev_id}",
            confidence=1.0,
        )
        edge.validate()
        graph.ensure_edge(edge)

    return node_id