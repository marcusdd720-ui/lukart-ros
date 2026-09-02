"""
Knowledge Operating System (KOS)

File: knowledge/graph.py
Version: 5.3.0
Sprint: GRAPH-018 / CASE-012-H1

High-performance directed Knowledge Graph with optimized node and edge indexes.
Idempotent ensure_node / ensure_edge primitives for deterministic projection.
"""

from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass, field

from knowledge.edge import KnowledgeEdge
from knowledge.node import KnowledgeNode


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


@dataclass(slots=True)
class KnowledgeGraph:
    """Directed Knowledge Graph preserving insertion order + fast O(1) index lookup."""

    nodes: dict[str, KnowledgeNode] = field(default_factory=dict)
    edges: list[KnowledgeEdge] = field(default_factory=list)

    adjacency: dict[str, list[str]] = field(default_factory=dict)
    reverse_adjacency: dict[str, list[str]] = field(default_factory=dict)

    _node_index: dict[str, KnowledgeNode] = field(default_factory=dict, init=False, repr=False)
    _edge_index: dict[tuple[str, str], KnowledgeEdge] = field(
        default_factory=dict, init=False, repr=False
    )
    _typed_edge_index: dict[tuple[str, str, str], KnowledgeEdge] = field(
        default_factory=dict, init=False, repr=False
    )
    _adj_lookup: dict[str, set[str]] = field(default_factory=dict, init=False, repr=False)
    _rev_lookup: dict[str, set[str]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._rebuild_indexes()

    def _edge_type_key(self, edge: KnowledgeEdge) -> str:
        t = getattr(edge, "type", None)
        if t is None:
            return ""
        return t.name if hasattr(t, "name") else str(t)

    def _rebuild_indexes(self) -> None:
        self._node_index.clear()
        self._edge_index.clear()
        self._typed_edge_index.clear()
        self.adjacency.clear()
        self.reverse_adjacency.clear()
        self._adj_lookup.clear()
        self._rev_lookup.clear()

        for node_id, node in self.nodes.items():
            self._node_index[node_id] = node
            self.adjacency[node_id] = []
            self.reverse_adjacency[node_id] = []
            self._adj_lookup[node_id] = set()
            self._rev_lookup[node_id] = set()

        for edge in self.edges:
            src, tgt = edge.source, edge.target
            self._edge_index[(src, tgt)] = edge
            self._typed_edge_index[(src, tgt, self._edge_type_key(edge))] = edge
            if tgt not in self._adj_lookup[src]:
                self.adjacency[src].append(tgt)
                self._adj_lookup[src].add(tgt)
            if src not in self._rev_lookup[tgt]:
                self.reverse_adjacency[tgt].append(src)
                self._rev_lookup[tgt].add(src)

    def add_node(self, node: KnowledgeNode) -> None:
        if node.id in self.nodes:
            raise NodeAlreadyExists(f"Node {node.id} already exists")
        self.nodes[node.id] = node
        self._node_index[node.id] = node
        self.adjacency.setdefault(node.id, [])
        self.reverse_adjacency.setdefault(node.id, [])
        self._adj_lookup.setdefault(node.id, set())
        self._rev_lookup.setdefault(node.id, set())

    def ensure_node(self, node: KnowledgeNode) -> KnowledgeNode:
        """Idempotently insert a node and return the existing or new node."""
        existing = self.get_node(node.id)
        if existing is not None:
            return existing
        self.add_node(node)
        return node

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        return self._node_index.get(node_id)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._node_index

    def contains_node(self, node_id: str) -> bool:
        return self.has_node(node_id)

    def remove_node(self, node_id: str) -> None:
        if node_id not in self.nodes:
            return
        del self.nodes[node_id]
        self._node_index.pop(node_id, None)
        self.edges = [e for e in self.edges if e.source != node_id and e.target != node_id]
        self._rebuild_indexes()

    def add_edge(self, edge: KnowledgeEdge) -> None:
        if edge.source not in self.nodes:
            raise KeyError(edge.source)
        if edge.target not in self.nodes:
            raise KeyError(edge.target)

        self.edges.append(edge)
        src, tgt = edge.source, edge.target
        self._edge_index[(src, tgt)] = edge
        self._typed_edge_index[(src, tgt, self._edge_type_key(edge))] = edge

        if tgt not in self._adj_lookup[src]:
            self.adjacency[src].append(tgt)
            self._adj_lookup[src].add(tgt)

        if src not in self._rev_lookup[tgt]:
            self.reverse_adjacency[tgt].append(src)
            self._rev_lookup[tgt].add(src)

    def ensure_edge(self, edge: KnowledgeEdge) -> KnowledgeEdge:
        """Idempotently insert an edge keyed by source, target and type."""
        if edge.source not in self.nodes:
            raise KeyError(edge.source)
        if edge.target not in self.nodes:
            raise KeyError(edge.target)

        key = (edge.source, edge.target, self._edge_type_key(edge))
        existing = self._typed_edge_index.get(key)
        if existing is not None:
            return existing

        self.add_edge(edge)
        return edge

    def has_edge_typed(self, source: str, target: str, edge_type: object) -> bool:
        type_key = edge_type.name if hasattr(edge_type, "name") else str(edge_type)
        return (source, target, type_key) in self._typed_edge_index

    def remove_edge(self, source: str, target: str) -> bool:
        initial = len(self.edges)
        self.edges = [e for e in self.edges if not (e.source == source and e.target == target)]
        if len(self.edges) < initial:
            self._rebuild_indexes()
            return True
        return False

    def contains_edge(self, source: str, target: str) -> bool:
        return (source, target) in self._edge_index

    def get_edge(self, source: str, target: str) -> KnowledgeEdge | None:
        return self._edge_index.get((source, target))

    def neighbors(self, node_id: str) -> list[KnowledgeNode]:
        """Return outgoing neighbour nodes."""
        return self.successors(node_id)

    def successors(self, node_id: str) -> list[KnowledgeNode]:
        if node_id not in self._node_index:
            raise NodeNotFound(f"Unknown node: {node_id}")
        return [node for target in self.adjacency.get(node_id, []) if (node := self.get_node(target))]

    def predecessors(self, node_id: str) -> list[KnowledgeNode]:
        if node_id not in self._node_index:
            raise NodeNotFound(f"Unknown node: {node_id}")
        return [node for source in self.reverse_adjacency.get(node_id, []) if (node := self.get_node(source))]

    def bfs(self, start: str) -> list[KnowledgeNode]:
        if start not in self._node_index:
            raise NodeNotFound(f"Unknown node '{start}'.")
        visited: set[str] = set()
        queue: deque[str] = deque([start])
        result: list[KnowledgeNode] = []
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

    def dfs(self, start: str) -> list[KnowledgeNode]:
        if start not in self._node_index:
            raise NodeNotFound(f"Unknown node '{start}'.")
        visited: set[str] = set()
        stack: list[str] = [start]
        result: list[KnowledgeNode] = []
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

    def dijkstra(self, start: str) -> dict[str, float]:
        if start not in self._node_index:
            raise NodeNotFound(f"Unknown node '{start}'.")
        dist: dict[str, float] = {nid: float("inf") for nid in self._node_index}
        dist[start] = 0.0
        pq: list[tuple[float, str]] = [(0.0, start)]
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

    def has_path(self, source: str, target: str) -> bool:
        if source == target and source in self._node_index:
            return True
        visited: set[str] = set()
        queue: deque[str] = deque([source])
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
        visited: set[str] = set()
        active: set[str] = set()
        for nid in self._node_index:
            if nid not in visited and self._has_cycle(nid, visited, active):
                return True
        return False

    def _has_cycle(self, node_id: str, visited: set[str], active: set[str]) -> bool:
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

    def degree(self, node_id: str) -> int:
        if node_id not in self._node_index:
            raise NodeNotFound(f"Unknown node: {node_id}")
        return self.in_degree(node_id) + self.out_degree(node_id)

    def in_degree(self, node_id: str) -> int:
        if node_id not in self._node_index:
            raise NodeNotFound(f"Unknown node: {node_id}")
        return len(self.reverse_adjacency.get(node_id, []))

    def out_degree(self, node_id: str) -> int:
        if node_id not in self._node_index:
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

    def isolated_nodes(self) -> list[KnowledgeNode]:
        return [n for n in self.nodes.values() if self.degree(n.id) == 0]

    def connected_nodes(self) -> list[KnowledgeNode]:
        return [n for n in self.nodes.values() if self.degree(n.id) > 0]

    def clear(self) -> None:
        self.nodes.clear()
        self.edges.clear()
        self._node_index.clear()
        self._edge_index.clear()
        self._typed_edge_index.clear()
        self.adjacency.clear()
        self.reverse_adjacency.clear()
        self._adj_lookup.clear()
        self._rev_lookup.clear()

    def copy(self) -> KnowledgeGraph:
        return KnowledgeGraph(
            nodes=dict(self.nodes),
            edges=list(self.edges),
            adjacency={k: list(v) for k, v in self.adjacency.items()},
            reverse_adjacency={k: list(v) for k, v in self.reverse_adjacency.items()},
        )

    def subgraph(self, node_ids: set[str]) -> KnowledgeGraph:
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

    def validate_integrity(self) -> list[str]:
        return self._validate_graph()

    def is_valid(self) -> bool:
        return self.validate()

    def _validate_graph(self) -> list[str]:
        errors: list[str] = []
        for e in self.edges:
            if e.source not in self._node_index:
                errors.append(f"Missing source node: {e.source}")
            if e.target not in self._node_index:
                errors.append(f"Missing target node: {e.target}")
        return errors

    def __len__(self) -> int:
        return self.node_count()

    def __contains__(self, node_id: str) -> bool:
        return self.has_node(node_id)

    def __iter__(self):
        return iter(self.nodes.values())

    def __str__(self) -> str:
        stats = self.statistics()
        return f"KnowledgeGraph(nodes={stats['nodes']}, edges={stats['edges']})"

    def __repr__(self) -> str:
        return f"KnowledgeGraph(nodes={self.node_count()}, edges={self.edge_count()})"
