"""
Knowledge Operating System (KOS)

File: knowledge/dijkstra.py
Version: 1.0
Sprint: GRAPH-007

Dijkstra shortest path algorithm.
"""

from __future__ import annotations

import heapq

from knowledge.graph import KnowledgeGraph


class Dijkstra:
    """
    Dijkstra shortest path algorithm.

    Currently every edge has weight = 1.
    In future versions edge.weight will be used.
    """

    def __init__(self, graph: KnowledgeGraph) -> None:
        self._graph = graph

    def shortest_path(
        self,
        source: str,
        target: str,
    ) -> list[str]:

        if not self._graph.has_node(source):
            return []

        if not self._graph.has_node(target):
            return []

        distances: dict[str, int] = {
            node: float("inf")
            for node in self._graph.nodes
        }

        previous: dict[str, str | None] = {
            node: None
            for node in self._graph.nodes
        }

        distances[source] = 0

        queue: list[tuple[int, str]] = [(0, source)]

        while queue:

            current_distance, current = heapq.heappop(queue)

            if current == target:
                break

            if current_distance > distances[current]:
                continue

            for neighbor in self._graph.neighbors(current):

                new_distance = current_distance + 1

                if new_distance < distances[neighbor.id]:

                    distances[neighbor.id] = new_distance
                    previous[neighbor.id] = current

                    heapq.heappush(
                        queue,
                        (
                            new_distance,
                            neighbor.id,
                        ),
                    )

        if distances[target] == float("inf"):
            return []

        path: list[str] = []

        node: str | None = target

        while node is not None:

            path.append(node)
            node = previous[node]

        path.reverse()

        return path

    def distance(
        self,
        source: str,
        target: str,
    ) -> int | None:

        path = self.shortest_path(
            source,
            target,
        )

        if not path:
            return None

        return len(path) - 1