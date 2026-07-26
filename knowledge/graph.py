"""
Knowledge Operating System (KOS)

File: knowledge/graph.py
Version: 5.1
Sprint: GRAPH-016

High-performance directed Knowledge Graph – pełna zgodność z testami.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import heapq
from typing import Dict, List, Optional, Set

from core.models.ids import EntityId
from knowledge.edge import KnowledgeEdge
from knowledge.node import KnowledgeNode


# ----------------------------------------------------------------------
# Exceptions
# ----------------------------------------------------------------------

class GraphError(Exception):
    """Base exception for graph operations."""


class NodeAlreadyExists(GraphError):
    """Node with given ID already exists."""


class NodeNotFound(GraphError):
    """Node with given ID not found."""


class EdgeAlreadyExists(GraphError):
    """Edge already exists."""


class EdgeNotFound(GraphError):
    """Edge not found."""


class CycleDetected(GraphError):
    """Cycle detected in graph."""


# ----------------------------------------------------------------------
# Knowledge Graph
# ----------------------------------------------------------------------

@dataclass(slots=True)
class KnowledgeGraph:
    """Directed Knowledge Graph preserving insertion order + fast lookup."""

    nodes: Dict[EntityId, KnowledgeNode] = field(default_factory=dict)
    edges: List[KnowledgeEdge] = field(default_factory=list)

    adjacency: Dict[EntityId, List[EntityId]] = field(default_factory=dict)
    reverse_adjacency: Dict[EntityId, List[EntityId]] = field(default_factory=dict)

    _adj_lookup: Dict[EntityId, Set[EntityId]] = field(default_factory=dict, init=False, repr=False)
    _rev_lookup: Dict[EntityId, Set[EntityId]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._rebuild_indexes()

    def _rebuild_indexes(self) -> None:
        self.adjacency.clear()
        self.reverse_adjacency.clear()
        self._adj_lookup.clear()
        self._rev_lookup.clear()

        for node_id in self.nodes:
            self.adjacency[node_id] = []
            self.reverse_adjacency[node_id] = []
            self._adj_lookup[node_id] = set()
            self._rev_lookup[node_id] = set()

        for edge in self.edges:
            src, tgt = edge.source, edge.target
            if tgt not in self._adj_lookup[src]:
                self.adjacency[src].append(tgt)
                self._adj_lookup[src].add(tgt)
            if src not in self._rev_lookup[tgt]:
                self.reverse_adjacency[tgt].append(src)
                self._rev_lookup[tgt].add(src)

    # ------------------------------------------------------------------
    # Node API
    # ------------------------------------------------------------------

    def add_node(self, node: KnowledgeNode) -> None:
        if node.id in self.nodes:
            raise NodeAlreadyExists(f"Node {node.id} already exists")
        self.nodes[node.id] = node
        self.adjacency.setdefault(node.id, [])
        self.reverse_adjacency.setdefault(node.id, [])
        self._adj_lookup.setdefault(node.id, set())
        self._rev_lookup.setdefault(node.id, set())

    def get_node(self, node_id: EntityId) -> Optional[KnowledgeNode]:
        return self.nodes.get(node_id)

    def has_node(self, node_id: EntityId) -> bool:
        return node_id in self.nodes

    def contains_node(self, node_id: EntityId) -> bool:
        return self.has_node(node_id)

    def remove_node(self, node_id: EntityId) -> None:
        if node_id not in self.nodes:
            return
        del self.nodes[node_id]
        self.edges = [e for e in self.edges if e.source != node_id and e.target != node_id]
        self._rebuild_indexes()

    # ------------------------------------------------------------------
    # Edge API
    # ------------------------------------------------------------------

    def add_edge(self, edge: KnowledgeEdge) -> None:
        if edge.source not in self.nodes:
            raise KeyError(edge.source)
        if edge.target not in self.nodes:
            raise KeyError(edge.target)

        self.edges.append(edge)

        src = edge.source
        tgt = edge.target

        if tgt not in self._adj_lookup[src]:
            self.adjacency[src].append(tgt)
            self._adj_lookup[src].add(tgt)

        if src not in self._rev_lookup[tgt]:
            self.reverse_adjacency[tgt].append(src)
            self._rev_lookup[tgt].add(src)

    def remove_edge(self, source: EntityId, target: EntityId) -> bool:
        initial = len(self.edges)
        self.edges = [e for e in self.edges if not (e.source == source and e.target == target)]
        if len(self.edges) < initial:
            self._rebuild_indexes()
            return True
        return False

    def contains_edge(self, source: EntityId, target: EntityId) -> bool:
        return target in self._adj_lookup.get(source, set())

    def get_edge(self, source: EntityId, target: EntityId) -> Optional[KnowledgeEdge]:
        for e in self.edges:
            if e.source == source and e.target == target:
                return e
        return None

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def neighbors(self, node_id: EntityId) -> List[KnowledgeNode]:
        """Return outgoing neighbour nodes."""
        return self.successors(node_id)

    def successors(self, node_id: EntityId) -> List[KnowledgeNode]:
        if node_id not in self.nodes:
            raise NodeNotFound(f"Unknown node: {node_id}")
        return [self.get_node(t) for t in self.adjacency.get(node_id, []) if self.get_node(t)]

    def predecessors(self, node_id: EntityId) -> List[KnowledgeNode]:
        if node_id not in self.nodes:
            raise NodeNotFound(f"Unknown node: {node_id}")
        return [self.get_node(s) for s in self.reverse_adjacency.get(node_id, []) if self.get_node(s)]

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def bfs(self, start: EntityId) -> List[KnowledgeNode]:
        if start not in self.nodes:
            raise NodeNotFound(f"Unknown node '{start}'.")
        visited: Set[EntityId] = set()
        queue: deque[EntityId] = deque([start])
        result: List[KnowledgeNode] = []
        while queue:
            cur = queue.popleft()
            if cur in visited:
                continue
            visited.add(cur)
            node = self.get_node(cur)
            if node:
                result.append(node)
            for n in self.adjacency.get(cur, []):
                if n not in visited:
                    queue.append(n)
        return result

    def dfs(self, start: EntityId) -> List[KnowledgeNode]:
        if start not in self.nodes:
            raise NodeNotFound(f"Unknown node '{start}'.")
        visited: Set[EntityId] = set()
        stack: List[EntityId] = [start]
        result: List[KnowledgeNode] = []
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            node = self.get_node(cur)
            if node:
                result.append(node)
            for n in reversed(self.adjacency.get(cur, [])):
                if n not in visited:
                    stack.append(n)
        return result

    def dijkstra(self, start: EntityId) -> Dict[EntityId, float]:
        if start not in self.nodes:
            raise NodeNotFound(f"Unknown node '{start}'.")
        dist: Dict[EntityId, float] = {nid: float('inf') for nid in self.nodes}
        dist[start] = 0.0
        pq: list[tuple[float, EntityId]] = [(0.0, start)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            for v in self.adjacency.get(u, []):
                alt = d + 1.0
                if alt < dist[v]:
                    dist[v] = alt
                    heapq.heappush(pq, (alt, v))
        return dist

    def has_path(self, source: EntityId, target: EntityId) -> bool:
        if source == target and source in self.nodes:
            return True
        visited: Set[EntityId] = set()
        queue: deque[EntityId] = deque([source])
        while queue:
            cur = queue.popleft()
            if cur == target:
                return True
            if cur in visited:
                continue
            visited.add(cur)
            queue.extend(self.adjacency.get(cur, []))
        return False

    def has_cycle(self) -> bool:
        visited: Set[EntityId] = set()
        active: Set[EntityId] = set()
        for nid in self.nodes:
            if nid not in visited:
                if self._has_cycle(nid, visited, active):
                    return True
        return False

    def _has_cycle(self, node_id: EntityId, visited: Set[EntityId], active: Set[EntityId]) -> bool:
        visited.add(node_id)
        active.add(node_id)
        for succ in self.adjacency.get(node_id, []):
            if succ not in visited:
                if self._has_cycle(succ, visited, active):
                    return True
            elif succ in active:
                return True
        active.remove(node_id)
        return False

    # ------------------------------------------------------------------
    # Degree & Statistics
    # ------------------------------------------------------------------

    def degree(self, node_id: EntityId) -> int:
        """Return total node degree (in + out)."""
        if node_id not in self.nodes:
            raise NodeNotFound(f"Unknown node: {node_id}")
        return self.in_degree(node_id) + self.out_degree(node_id)

    def in_degree(self, node_id: EntityId) -> int:
        if node_id not in self.nodes:
            raise NodeNotFound(f"Unknown node: {node_id}")
        return len(self.reverse_adjacency.get(node_id, []))

    def out_degree(self, node_id: EntityId) -> int:
        if node_id not in self.nodes:
            raise NodeNotFound(f"Unknown node: {node_id}")
        return len(self.adjacency.get(node_id, []))

    def node_count(self) -> int:
        return len(self.nodes)

    def edge_count(self) -> int:
        return len(self.edges)

    def statistics(self) -> dict[str, int]:
        isolated = len(self.isolated_nodes())
        connected = len(self.connected_nodes())
        return {
            "nodes": self.node_count(),
            "edges": self.edge_count(),
            "isolated_nodes": isolated,
            "connected_nodes": connected,
        }

    def isolated_nodes(self) -> List[KnowledgeNode]:
        return [n for n in self.nodes.values() if self.degree(n.id) == 0]

    def connected_nodes(self) -> List[KnowledgeNode]:
        return [n for n in self.nodes.values() if self.degree(n.id) > 0]

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def clear(self) -> None:
        self.nodes.clear()
        self.edges.clear()
        self.adjacency.clear()
        self.reverse_adjacency.clear()
        self._adj_lookup.clear()
        self._rev_lookup.clear()

    def copy(self) -> "KnowledgeGraph":
        return KnowledgeGraph(
            nodes=dict(self.nodes),
            edges=list(self.edges),
            adjacency={k: list(v) for k, v in self.adjacency.items()},
            reverse_adjacency={k: list(v) for k, v in self.reverse_adjacency.items()},
        )

    def subgraph(self, node_ids: set[EntityId]) -> "KnowledgeGraph":
        g = KnowledgeGraph()
        for nid in node_ids:
            node = self.get_node(nid)
            if node:
                g.add_node(node)
        for e in self.edges:
            if e.source in g.nodes and e.target in g.nodes:
                g.add_edge(e)
        return g

    def validate(self) -> bool:
        return len(self._validate_graph()) == 0

    def validate_integrity(self) -> List[str]:
        return self._validate_graph()

    def is_valid(self) -> bool:
        return self.validate()

    def _validate_graph(self) -> List[str]:
        errors: List[str] = []
        for e in self.edges:
            if e.source not in self.nodes:
                errors.append(f"Missing source node: {e.source}")
            if e.target not in self.nodes:
                errors.append(f"Missing target node: {e.target}")
        return errors

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return self.node_count()

    def __contains__(self, node_id: EntityId) -> bool:
        return self.has_node(node_id)

    def __iter__(self):
        return iter(self.nodes.values())

    def __str__(self) -> str:
        stats = self.statistics()
        return f"KnowledgeGraph(nodes={stats['nodes']}, edges={stats['edges']})"

    def __repr__(self) -> str:
        return f"KnowledgeGraph(nodes={self.node_count()}, edges={self.edge_count()})"