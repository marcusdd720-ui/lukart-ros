"""
Knowledge Operating System (KOS)

File: knowledge/graph.py
Version: 2.1
Sprint: GRAPH-001

Knowledge Graph implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from knowledge.edge import KnowledgeEdge
from knowledge.node import KnowledgeNode


@dataclass(slots=True)
class KnowledgeGraph:
    """Knowledge Graph."""

    nodes: dict[str, KnowledgeNode] = field(default_factory=dict)
    edges: list[KnowledgeEdge] = field(default_factory=list)

    def add_node(self, node: KnowledgeNode) -> None:
        """Add node to graph."""

        self.nodes[node.id] = node

    def add_edge(self, edge: KnowledgeEdge) -> None:
        """Add edge to graph."""

        if edge.source not in self.nodes:
            raise KeyError(f"Unknown source node: {edge.source}")

        if edge.target not in self.nodes:
            raise KeyError(f"Unknown target node: {edge.target}")

        self.edges.append(edge)

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        """Return node or None."""

        return self.nodes.get(node_id)

    def has_node(self, node_id: str) -> bool:
        """Check whether node exists."""

        return node_id in self.nodes

    def remove_node(self, node_id: str) -> None:
        """Remove node and all connected edges."""

        if node_id not in self.nodes:
            return

        del self.nodes[node_id]

        self.edges = [
            edge
            for edge in self.edges
            if edge.source != node_id
            and edge.target != node_id
        ]

    def neighbors(self, node_id: str) -> list[KnowledgeNode]:
        """Return outgoing neighbours."""

        result: list[KnowledgeNode] = []

        for edge in self.edges:
            if edge.source == node_id:
                node = self.get_node(edge.target)
                if node is not None:
                    result.append(node)

        return result

    def node_count(self) -> int:
        """Return number of nodes."""

        return len(self.nodes)

    def edge_count(self) -> int:
        """Return number of edges."""

        return len(self.edges)

    def clear(self) -> None:
        """Remove all graph data."""

        self.nodes.clear()
        self.edges.clear()

    def __str__(self) -> str:
        return (
            f"KnowledgeGraph("
            f"nodes={self.node_count()}, "
            f"edges={self.edge_count()})"
        )