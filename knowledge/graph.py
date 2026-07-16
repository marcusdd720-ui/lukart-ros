"""
Knowledge Operating System (KOS)

File: knowledge/graph.py
Version: 2.0
Sprint: F-010

Knowledge Graph implementation.
"""

from dataclasses import dataclass, field

from knowledge.edge import KnowledgeEdge
from knowledge.node import KnowledgeNode


@dataclass
class KnowledgeGraph:
    """Knowledge Graph."""

    nodes: dict[str, KnowledgeNode] = field(default_factory=dict)
    edges: list[KnowledgeEdge] = field(default_factory=list)

    def add_node(self, node: KnowledgeNode) -> None:
        """Add node to graph."""

        self.nodes[node.id] = node

    def add_edge(self, edge: KnowledgeEdge) -> None:
        """Add edge to graph."""

        self.edges.append(edge)

    def get_node(self, node_id: str):

        return self.nodes.get(node_id)

    def has_node(self, node_id: str) -> bool:

        return node_id in self.nodes

    def node_count(self) -> int:

        return len(self.nodes)

    def edge_count(self) -> int:

        return len(self.edges)

    def __str__(self):

        return (
            f"KnowledgeGraph("
            f"nodes={self.node_count()}, "
            f"edges={self.edge_count()})"
        )