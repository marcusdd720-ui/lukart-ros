"""
Knowledge Operating System (KOS)

File: knowledge/bfs.py
Version: 1.0
Sprint: GRAPH-003

Breadth First Search implementation.
"""

from __future__ import annotations

from collections import deque

from knowledge.graph import KnowledgeGraph


class BreadthFirstSearch:
    """
    Breadth First Search algorithms.
    """

    def __init__(self, graph: KnowledgeGraph) -> None:
        self._graph = graph

    def reachable_nodes(self, start: str) -> list[str]:
        """
        Return all reachable node ids from the start node.
        """

        if not self._graph.has_node(start):
            return []

        visited: set[str] = set()
        queue: deque[str] = deque([start])
        order: list[str] = []

        while queue:
            current = queue.popleft()

            if current in visited:
                continue

            visited.add(current)
            order.append(current)

            for neighbor in self._graph.neighbors(current):
                if neighbor.id not in visited:
                    queue.append(neighbor.id)

        return order

    def shortest_path(
        self,
        source: str,
        target: str,
    ) -> list[str]:
        """
        Return shortest path using BFS.
        """

        if not self._graph.has_node(source):
            return []

        if not self._graph.has_node(target):
            return []

        queue: deque[str] = deque([source])

        visited: set[str] = {source}

        previous: dict[str, str | None] = {
            source: None,
        }

        while queue:
            current = queue.popleft()

            if current == target:
                break

            for neighbor in self._graph.neighbors(current):
                if neighbor.id in visited:
                    continue

                visited.add(neighbor.id)
                previous[neighbor.id] = current
                queue.append(neighbor.id)

        if target not in previous:
            return []

        path: list[str] = []

        node: str | None = target

        while node is not None:
            path.append(node)
            node = previous[node]

        path.reverse()

        return path