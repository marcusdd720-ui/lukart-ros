"""
Knowledge Operating System (KOS)

File: knowledge/query.py
Version: 1.1.1
Sprint: GRAPH-020

High-level query API over KnowledgeGraph.
Read-only. Builds lightweight indexes at construction time.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable, Iterable
from typing import Any

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode
from knowledge.types import EdgeType, NodeType


class GraphQuery:
    """
    Query facade for KnowledgeGraph.

    Indexes (name → nodes, type → nodes) are built once at init.
    Call refresh() after external graph mutations.
    """

    def __init__(self, graph: KnowledgeGraph) -> None:
        self.graph = graph
        self._by_name: dict[str, list[KnowledgeNode]] = defaultdict(list)
        self._by_type: dict[NodeType, list[KnowledgeNode]] = defaultdict(list)
        self._rebuild_indexes()

    def refresh(self) -> GraphQuery:
        """Rebuild indexes after the underlying graph changed."""
        self._rebuild_indexes()
        return self

    def _rebuild_indexes(self) -> None:
        self._by_name.clear()
        self._by_type.clear()
        for node in self.graph.nodes.values():
            self._by_name[node.name].append(node)
            self._by_type[node.type].append(node)

    @staticmethod
    def _as_id(item: KnowledgeNode | str) -> str:
        if isinstance(item, KnowledgeNode):
            return item.id
        return str(item)

    # ------------------------------------------------------------------
    # Point lookups
    # ------------------------------------------------------------------

    def get(self, node_id: str) -> KnowledgeNode | None:
        return self.graph.get_node(node_id)

    def require(self, node_id: str) -> KnowledgeNode:
        node = self.graph.get_node(node_id)
        if node is None:
            raise KeyError(f"Node not found: {node_id}")
        return node

    def exists(self, node_id: str) -> bool:
        return self.graph.has_node(node_id)

    def first(
        self,
        nodes: Iterable[KnowledgeNode] | None = None,
    ) -> KnowledgeNode | None:
        iterable = self.graph.nodes.values() if nodes is None else nodes
        for node in iterable:
            return node
        return None

    def one(
        self,
        nodes: Iterable[KnowledgeNode],
        *,
        error: str = "Expected exactly one node",
    ) -> KnowledgeNode:
        found: list[KnowledgeNode] = list(nodes)
        if len(found) != 1:
            raise ValueError(f"{error} (got {len(found)})")
        return found[0]

    # ------------------------------------------------------------------
    # Indexed / filtered node queries
    # ------------------------------------------------------------------

    def find_by_name(self, name: str, *, exact: bool = True) -> list[KnowledgeNode]:
        if exact:
            return list(self._by_name.get(name, []))
        needle = name.lower()
        return [
            n
            for n in self.graph.nodes.values()
            if n.name.lower() == needle
        ]

    def find_by_type(self, node_type: NodeType | str) -> list[KnowledgeNode]:
        expected = self._as_node_type(node_type)
        return list(self._by_type.get(expected, []))

    def find_by_tag(self, tag: str) -> list[KnowledgeNode]:
        return [n for n in self.graph.nodes.values() if tag in n.tags]

    def find_by_status(self, status: str) -> list[KnowledgeNode]:
        return [n for n in self.graph.nodes.values() if n.status == status]

    def search(
        self,
        *,
        name_contains: str | None = None,
        node_type: NodeType | str | None = None,
        tag: str | None = None,
        status: str | None = None,
        source_contains: str | None = None,
        metadata_key: str | None = None,
        metadata_value: Any = None,
        confidence_min: float | None = None,
        confidence_max: float | None = None,
    ) -> list[KnowledgeNode]:
        """Filter nodes by optional criteria (AND)."""
        expected_type = (
            self._as_node_type(node_type) if node_type is not None else None
        )
        name_q = name_contains.lower() if name_contains else None
        source_q = source_contains.lower() if source_contains else None

        if expected_type is not None:
            pool: Iterable[KnowledgeNode] = self._by_type.get(expected_type, [])
        else:
            pool = self.graph.nodes.values()

        result: list[KnowledgeNode] = []
        for node in pool:
            if status is not None and node.status != status:
                continue
            if tag is not None and tag not in node.tags:
                continue
            if name_q is not None and name_q not in node.name.lower():
                continue
            if source_q is not None and source_q not in node.source.lower():
                continue
            if confidence_min is not None and node.confidence < confidence_min:
                continue
            if confidence_max is not None and node.confidence > confidence_max:
                continue
            if metadata_key is not None:
                if metadata_key not in node.metadata:
                    continue
                if (
                    metadata_value is not None
                    and node.metadata.get(metadata_key) != metadata_value
                ):
                    continue
            result.append(node)
        return result

    def filter(
        self,
        predicate: Callable[[KnowledgeNode], bool],
        nodes: Iterable[KnowledgeNode] | None = None,
    ) -> list[KnowledgeNode]:
        pool = self.graph.nodes.values() if nodes is None else nodes
        return [n for n in pool if predicate(n)]

    def sort(
        self,
        nodes: Iterable[KnowledgeNode],
        *,
        key: str | Callable[[KnowledgeNode], Any] = "name",
        reverse: bool = False,
    ) -> list[KnowledgeNode]:
        if callable(key):
            return sorted(nodes, key=key, reverse=reverse)
        return sorted(
            nodes,
            key=lambda n: getattr(n, key, ""),
            reverse=reverse,
        )

    def limit(
        self,
        nodes: Iterable[KnowledgeNode],
        n: int,
    ) -> list[KnowledgeNode]:
        if n < 0:
            raise ValueError("limit must be >= 0")
        result: list[KnowledgeNode] = []
        for i, node in enumerate(nodes):
            if i >= n:
                break
            result.append(node)
        return result

    # ------------------------------------------------------------------
    # Edges / neighbourhood
    # ------------------------------------------------------------------

    def successors(self, node_id: str) -> list[KnowledgeNode]:
        return self.graph.successors(node_id)

    def predecessors(self, node_id: str) -> list[KnowledgeNode]:
        return self.graph.predecessors(node_id)

    def neighbors(self, node_id: str) -> list[KnowledgeNode]:
        return self.graph.neighbors(node_id)

    def outgoing_edges(self, node_id: str) -> list[KnowledgeEdge]:
        return [e for e in self.graph.edges if e.source == node_id]

    def incoming_edges(self, node_id: str) -> list[KnowledgeEdge]:
        return [e for e in self.graph.edges if e.target == node_id]

    def edges_of_type(self, edge_type: EdgeType | str) -> list[KnowledgeEdge]:
        expected = self._as_edge_type(edge_type)
        return [e for e in self.graph.edges if e.type == expected]

    def related(
        self,
        node_id: str,
        *,
        edge_type: EdgeType | str | None = None,
        direction: str = "out",
    ) -> list[KnowledgeNode]:
        """direction: 'out' | 'in' | 'both'"""
        expected = (
            self._as_edge_type(edge_type) if edge_type is not None else None
        )
        ids: set[str] = set()
        for edge in self.graph.edges:
            if expected is not None and edge.type != expected:
                continue
            if direction in ("out", "both") and edge.source == node_id:
                ids.add(edge.target)
            if direction in ("in", "both") and edge.target == node_id:
                ids.add(edge.source)
        result: list[KnowledgeNode] = []
        for nid in ids:
            node = self.graph.get_node(nid)
            if node is not None:
                result.append(node)
        return result

    # ------------------------------------------------------------------
    # Topology
    # ------------------------------------------------------------------

    def has_path(self, source: str, target: str) -> bool:
        return self.graph.has_path(source, target)

    def bfs(self, start: str) -> list[str]:
        raw = self.graph.bfs(start)
        return [self._as_id(item) for item in raw]

    def dfs(self, start: str) -> list[str]:
        raw = self.graph.dfs(start)
        return [self._as_id(item) for item in raw]

    def shortest_path(
        self,
        source: str,
        target: str,
    ) -> list[str] | None:
        """Shortest path by weight (dijkstra) or unweighted BFS fallback."""
        if source == target:
            return [source] if self.graph.has_node(source) else None

        dijkstra = getattr(self.graph, "dijkstra", None)
        if callable(dijkstra):
            try:
                result = dijkstra(source, target)
                if isinstance(result, tuple) and result:
                    path = result[0]
                    if path:
                        return [self._as_id(item) for item in path]
                    return None
                if isinstance(result, list):
                    return [self._as_id(item) for item in result] or None
            except TypeError:
                pass

        if not self.graph.has_node(source):
            return None

        parent: dict[str, str | None] = {source: None}
        queue: deque[str] = deque([source])
        while queue:
            current = queue.popleft()
            if current == target:
                path: list[str] = []
                node: str | None = target
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                return path
            for nxt in self.graph.adjacency.get(current, []):
                nxt_id = self._as_id(nxt)
                if nxt_id not in parent:
                    parent[nxt_id] = current
                    queue.append(nxt_id)
        return None

    def descendants(self, node_id: str) -> list[KnowledgeNode]:
        """Nodes reachable via outgoing edges (excluding start)."""
        if not self.graph.has_node(node_id):
            return []
        order = self.bfs(node_id)
        result: list[KnowledgeNode] = []
        for nid in order:
            if nid == node_id:
                continue
            node = self.graph.get_node(nid)
            if node is not None:
                result.append(node)
        return result

    def ancestors(self, node_id: str) -> list[KnowledgeNode]:
        """Nodes reachable via incoming edges (excluding start)."""
        if not self.graph.has_node(node_id):
            return []

        seen: set[str] = {node_id}
        queue: deque[str] = deque([node_id])
        result: list[KnowledgeNode] = []
        while queue:
            current = queue.popleft()
            for pred in self.graph.reverse_adjacency.get(current, []):
                pred_id = self._as_id(pred)
                if pred_id in seen:
                    continue
                seen.add(pred_id)
                queue.append(pred_id)
                node = self.graph.get_node(pred_id)
                if node is not None:
                    result.append(node)
        return result

    def connected_component(self, node_id: str) -> list[KnowledgeNode]:
        """Undirected connected component containing node_id."""
        if not self.graph.has_node(node_id):
            return []

        seen: set[str] = {node_id}
        queue: deque[str] = deque([node_id])
        while queue:
            current = queue.popleft()
            for nxt in self.graph.adjacency.get(current, []):
                nxt_id = self._as_id(nxt)
                if nxt_id not in seen:
                    seen.add(nxt_id)
                    queue.append(nxt_id)
            for pred in self.graph.reverse_adjacency.get(current, []):
                pred_id = self._as_id(pred)
                if pred_id not in seen:
                    seen.add(pred_id)
                    queue.append(pred_id)
        return [
            n for nid in seen if (n := self.graph.get_node(nid)) is not None
        ]

    def subgraph(self, node_ids: Iterable[str]) -> KnowledgeGraph:
        return self.graph.subgraph(set(node_ids))

    # ------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------

    def count_nodes(self, node_type: NodeType | str | None = None) -> int:
        if node_type is None:
            return self.graph.node_count()
        return len(self.find_by_type(node_type))

    def count_edges(self, edge_type: EdgeType | str | None = None) -> int:
        if edge_type is None:
            return self.graph.edge_count()
        return len(self.edges_of_type(edge_type))

    def isolated(self) -> list[KnowledgeNode]:
        """
        Isolated nodes.

        Compatible with graph.isolated_nodes() returning either node IDs
        or KnowledgeNode instances.
        """
        raw = self.graph.isolated_nodes()
        result: list[KnowledgeNode] = []
        for item in raw:
            if isinstance(item, KnowledgeNode):
                result.append(item)
            else:
                node = self.graph.get_node(str(item))
                if node is not None:
                    result.append(node)
        return result

    def statistics(self) -> dict[str, Any]:
        return self.summary()

    def summary(self) -> dict[str, Any]:
        by_type = {k.name: len(v) for k, v in self._by_type.items()}
        return {
            "nodes": self.graph.node_count(),
            "edges": self.graph.edge_count(),
            "by_type": by_type,
            "isolated": len(self.isolated()),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _as_node_type(value: NodeType | str) -> NodeType:
        if isinstance(value, NodeType):
            return value
        text = str(value).strip()
        if text in NodeType.__members__:
            return NodeType[text]
        upper = text.upper()
        if upper in NodeType.__members__:
            return NodeType[upper]
        return NodeType(text.lower())

    @staticmethod
    def _as_edge_type(value: EdgeType | str) -> EdgeType:
        if isinstance(value, EdgeType):
            return value
        text = str(value).strip()
        if text in EdgeType.__members__:
            return EdgeType[text]
        upper = text.upper()
        if upper in EdgeType.__members__:
            return EdgeType[upper]
        return EdgeType(text.lower())