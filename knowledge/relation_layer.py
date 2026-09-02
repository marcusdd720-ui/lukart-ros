"""Relation layer for deterministic Knowledge Graph edge management."""

from __future__ import annotations

from dataclasses import dataclass

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.types import EdgeType


class RelationLayerError(ValueError):
    """Raised when a relation violates the relation-layer contract."""


@dataclass(slots=True)
class RelationLayer:
    """Validates and inserts typed relations into a KnowledgeGraph."""

    graph: KnowledgeGraph

    def add(
        self,
        source: str,
        target: str,
        relation_type: EdgeType,
        *,
        description: str = "",
        confidence: float = 1.0,
    ) -> KnowledgeEdge:
        edge = KnowledgeEdge(
            source=source,
            target=target,
            type=relation_type,
            description=description,
            confidence=confidence,
        )
        return self.ensure(edge)

    def ensure(self, edge: KnowledgeEdge) -> KnowledgeEdge:
        if not self.graph.has_node(edge.source):
            raise RelationLayerError(f"Unknown relation source: {edge.source}")
        if not self.graph.has_node(edge.target):
            raise RelationLayerError(f"Unknown relation target: {edge.target}")
        try:
            edge.validate()
        except ValueError as exc:
            raise RelationLayerError(str(exc)) from exc
        return self.graph.ensure_edge(edge)

    def has(
        self,
        source: str,
        target: str,
        relation_type: EdgeType,
    ) -> bool:
        return self.graph.has_edge_typed(source, target, relation_type)

    def get(
        self,
        source: str,
        target: str,
        relation_type: EdgeType,
    ) -> KnowledgeEdge | None:
        if not self.has(source, target, relation_type):
            return None
        for edge in self.graph.edges:
            if (
                edge.source == source
                and edge.target == target
                and edge.type == relation_type
            ):
                return edge
        return None

    def outgoing(
        self,
        source: str,
        relation_type: EdgeType | None = None,
    ) -> list[KnowledgeEdge]:
        return [
            edge
            for edge in self.graph.edges
            if edge.source == source
            and (relation_type is None or edge.type == relation_type)
        ]
