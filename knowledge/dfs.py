"""
Knowledge Operating System (KOS)

File: knowledge/dfs.py
Version: 1.0
Sprint: GRAPH-004

Depth First Search implementation.
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph


class DepthFirstSearch:
    """
    Depth First Search algorithms.
    """

    def __init__(self, graph: KnowledgeGraph) -> None:
        self._graph = graph

    def reachable_nodes(self, start: str) -> list[str]:
        """
        Return all reachable nodes using DFS.
        """

        if not self._graph.has_node(start):
            return []

        visited: set[str] = set()
        result: list[str] = []

        self._visit(start, visited, result)

        return result

    def _visit(
        self,
        node_id: str,
        visited: set[str],
        result: list[str],
    ) -> None:

        if node_id in visited:
            return

        visited.add(node_id)
        result.append(node_id)

        for neighbor in self._graph.neighbors(node_id):
            self._visit(
                neighbor.id,
                visited,
                result,
            )

    def has_path(
        self,
        source: str,
        target: str,
    ) -> bool:

        if not self._graph.has_node(source):
            return False

        visited: set[str] = set()

        return self._search(
            source,
            target,
            visited,
        )

    def _search(
        self,
        current: str,
        target: str,
        visited: set[str],
    ) -> bool:

        if current == target:
            return True

        visited.add(current)

        for neighbor in self._graph.neighbors(current):

            if neighbor.id in visited:
                continue

            if self._search(
                neighbor.id,
                target,
                visited,
            ):
                return True

        return False