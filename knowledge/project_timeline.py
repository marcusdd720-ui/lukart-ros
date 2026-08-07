"""
Project domain TimelineEvent into KnowledgeGraph.

Contract:
  - stable id: event:<domain_event.id>
  - NodeType.EVENT
  - idempotent via ensure_node
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph
from knowledge.models.case import TimelineEvent
from knowledge.node import KnowledgeNode
from knowledge.types import NodeType


def event_node_id(event_id: str) -> str:
    if event_id.startswith("event:"):
        return event_id
    return f"event:{event_id}"


def project_timeline_event(graph: KnowledgeGraph, event: TimelineEvent) -> str:
    """
    Project a domain TimelineEvent into the graph.

    Returns the EVENT node id.
    Safe to call repeatedly.
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
        },
        tags={"timeline", "event"},
    )
    node.validate()
    graph.ensure_node(node)
    return node_id