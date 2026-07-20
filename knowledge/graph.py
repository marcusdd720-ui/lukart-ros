"""
Knowledge Operating System (KOS)

File: knowledge/graph.py
Version: 2.2
Sprint: GRAPH-016

Knowledge Graph implementation.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional

from core.models.ids import EntityId
from knowledge.edge import KnowledgeEdge
from knowledge.node import KnowledgeNode


@dataclass(slots=True)
class KnowledgeGraph:
    """Knowledge Graph."""

    nodes: Dict[EntityId, KnowledgeNode] = field(default_factory=dict)
    edges: List[KnowledgeEdge] = field(default_factory=list)

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

    def remove_edge(self, source: EntityId, target: EntityId) -> bool:
        """Remove edge from graph."""
        initial_length = len(self.edges)
        self.edges = [
            edge
            for edge in self.edges
            if not (edge.source == source and edge.target == target)
        ]
        return len(self.edges) < initial_length

    def get_node(self, node_id: EntityId) -> Optional[KnowledgeNode]:
        """Return node or None."""
        return self.nodes.get(node_id)

    def has_node(self, node_id: EntityId) -> bool:
        """Check whether node exists."""
        return node_id in self.nodes

    def contains_node(self, node_id: EntityId) -> bool:
        """Alias for has_node()."""
        return self.has_node(node_id)

    def contains_edge(self, source: EntityId, target: EntityId) -> bool:
        """Check whether edge exists."""
        return any(
            edge.source == source and edge.target == target
            for edge in self.edges
        )

    def remove_node(self, node_id: EntityId) -> None:
        """Remove node together with every connected edge."""
        if node_id not in self.nodes:
            return

        del self.nodes[node_id]

        self.edges = [
            edge
            for edge in self.edges
            if edge.source != node_id and edge.target != node_id
        ]

    def neighbors(self, node_id: EntityId) -> List[KnowledgeNode]:
        """Return outgoing neighbour nodes."""
        return self.successors(node_id)

       def successors(self, node_id: EntityId) -> List[KnowledgeNode]:
        """Return all successor nodes."""
        result: List[KnowledgeNode] = []

        for edge in self.edges:
            if edge.source == node_id:
                node = self.get_node(edge.target)
                if node is not None:
                    result.append(node)

        return result

    def predecessors(self, node_id: EntityId) -> List[KnowledgeNode]:
        """Return all predecessor nodes."""
        result: List[KnowledgeNode] = []

        for edge in self.edges:
            if edge.target == node_id:
                node = self.get_node(edge.source)
                if node is not None:
                    result.append(node)

        return result

    def has_path(
        self,
        source: EntityId,
        target: EntityId,
    ) -> bool:
        """Return True if a path exists between two nodes."""

        if source not in self.nodes:
            raise KeyError(f"Unknown node: {source}")

        if target not in self.nodes:
            raise KeyError(f"Unknown node: {target}")

        if source == target:
            return True

        visited: Set[EntityId] = set()
        queue: deque[EntityId] = deque([source])

        while queue:
            current = queue.popleft()

            if current == target:
                return True

            if current in visited:
                continue

            visited.add(current)

            for edge in self.edges:
                if edge.source == current:
                    queue.append(edge.target)

        return False
        """Return total node degree."""
        if node_id not in self.nodes:
            raise KeyError(f"Unknown node: {node_id}")

        incoming = sum(1 for edge in self.edges if edge.target == node_id)
        outgoing = sum(1 for edge in self.edges if edge.source == node_id)
        return incoming + outgoing

    def in_degree(self, node_id: EntityId) -> int:
        """Return incoming degree."""
        if node_id not in self.nodes:
            raise KeyError(f"Unknown node: {node_id}")
        return sum(1 for edge in self.edges if edge.target == node_id)

    def out_degree(self, node_id: EntityId) -> int:
        """Return outgoing degree."""
        if node_id not in self.nodes:
            raise KeyError(f"Unknown node: {node_id}")
        return sum(1 for edge in self.edges if edge.source == node_id)

    def node_count(self) -> int:
        """Return number of nodes."""
        return len(self.nodes)

    def edge_count(self) -> int:
        """Return number of edges."""
        return len(self.edges)

    def statistics(self) -> dict[str, int]:
        
        """Return basic graph statistics."""
        isolated = len(self.isolated_nodes())
        connected = len(self.connected_nodes())

        return {
            "nodes": self.node_count(),
            "edges": self.edge_count(),
            "isolated_nodes": isolated,
            "connected_nodes": connected,
        }

    def isolated_nodes(self) -> List[KnowledgeNode]:
        """Return nodes with no connections."""
        return [
            node
            for node in self.nodes.values()
            if self.degree(node.id) == 0
        ]

    def connected_nodes(self) -> List[KnowledgeNode]:
        """Return nodes with at least one connection."""
        return [
            node
            for node in self.nodes.values()
            if self.degree(node.id) > 0
        ]

    def clear(self) -> None:
        """Remove all graph data."""
        self.nodes.clear()
        self.edges.clear()

    def copy(self) -> "KnowledgeGraph":
        """Return shallow copy of graph."""
        return KnowledgeGraph(
            nodes=dict(self.nodes),
            edges=list(self.edges),
        )

    def subgraph(self, node_ids: set[EntityId]) -> "KnowledgeGraph":
        """Create subgraph containing selected nodes."""
        graph = KnowledgeGraph()

        for node_id in node_ids:
            node = self.get_node(node_id)
            if node is not None:
                graph.add_node(node)

        for edge in self.edges:
            if edge.source in graph.nodes and edge.target in graph.nodes:
                graph.add_edge(edge)

        return graph

    def __len__(self) -> int:
        """Return number of nodes."""
        return self.node_count()

    def __contains__(self, node_id: EntityId) -> bool:
        """Support: node_id in graph"""
        return self.has_node(node_id)

    def __iter__(self):
        """Iterate over graph nodes."""
        return iter(self.nodes.values())

    def __str__(self) -> str:
        """Human-readable graph representation."""
        stats = self.statistics()
        return (
            "KnowledgeGraph("
            f"nodes={stats['nodes']}, "
            f"edges={stats['edges']}, "
            f"isolated={stats['isolated_nodes']}, "
            f"connected={stats['connected_nodes']}"
            ")"
        )