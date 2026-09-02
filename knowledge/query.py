from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from typing import Any

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode


class KnowledgeQuery:
    """Convenience query layer over KnowledgeGraph."""

    def __init__(self, graph: KnowledgeGraph) -> None:
        self.graph = graph

    @staticmethod
    def _as_id(item: KnowledgeNode | str) -> str:
        return item if isinstance(item, str) else item.id

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
                    candidate_path = result[0]
                    if candidate_path:
                        return [self._as_id(item) for item in candidate_path]
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
                fallback_path: list[str] = []
                node: str | None = target
                while node is not None:
                    fallback_path.append(node)
                    node = parent[node]
                fallback_path.reverse()
                return fallback_path
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

    def neighbors(self, node_id: str) -> list[KnowledgeNode]:
        return self.graph.neighbors(node_id)

    def successors(self, node_id: str) -> list[KnowledgeNode]:
        return self.graph.successors(node_id)

    def predecessors(self, node_id: str) -> list[KnowledgeNode]:
        return self.graph.predecessors(node_id)

    def has_path(self, source: str, target: str) -> bool:
        return self.graph.has_path(source, target)

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        return self.graph.get_node(node_id)

    def get_edge(self, source: str, target: str) -> KnowledgeEdge | None:
        return self.graph.get_edge(source, target)

    def node_count(self) -> int:
        return self.graph.node_count()

    def edge_count(self) -> int:
        return self.graph.edge_count()

    def roots(self) -> list[KnowledgeNode]:
        return self.graph.roots()

    def leaves(self) -> list[KnowledgeNode]:
        return self.graph.leaves()

    def isolated_nodes(self) -> list[KnowledgeNode]:
        return self.graph.isolated_nodes()

    def graph_statistics(self) -> dict[str, int]:
        return self.graph.graph_statistics()

    def query_nodes(
        self,
        *,
        node_type: Any | None = None,
        tag: str | None = None,
        status: str | None = None,
    ) -> list[KnowledgeNode]:
        result: list[KnowledgeNode] = []
        for node in self.graph.nodes_iter():
            if node_type is not None and node.type != node_type:
                continue
            if tag is not None and tag not in node.tags:
                continue
            if status is not None and node.status != status:
                continue
            result.append(node)
        return result

    def query_edges(
        self,
        *,
        edge_type: Any | None = None,
        source: str | None = None,
        target: str | None = None,
    ) -> list[KnowledgeEdge]:
        result: list[KnowledgeEdge] = []
        for edge in self.graph.iter_edges():
            if edge_type is not None and edge.type != edge_type:
                continue
            if source is not None and edge.source != source:
                continue
            if target is not None and edge.target != target:
                continue
            result.append(edge)
        return result

    def subgraph(self, node_ids: Iterable[str]) -> KnowledgeGraph:
        return self.graph.subgraph(node_ids)

    def to_dict(self) -> dict[str, Any]:
        return self.graph.to_dict()
