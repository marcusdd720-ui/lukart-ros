"""
Knowledge Operating System (KOS)

File: knowledge/topological_sort.py
Version: 1.0
Sprint: GRAPH-006

Topological Sort implementation.
"""

from __future__ import annotations

from collections import deque

from knowledge.graph import KnowledgeGraph


class TopologicalSort:
    """
    Performs topological sorting of a directed acyclic graph.
    """

    def __init__(self, graph: KnowledgeGraph) -> None:
        self._graph = graph

    def sort(self) -> list[str]:
        """
        Return nodes in topological order.

        Raises:
            ValueError:
                If the graph contains a cycle.
        """

        indegree: dict[str, int] = {
            node_id: 0
            for node_id in self._graph.nodes
        }

        for edge in self._graph.edges:
            indegree[edge.target] += 1

        queue: deque[str] = deque()

        for node_id, degree in indegree.items():
            if degree == 0:
                queue.append(node_id)

        result: list[str] = []

        while queue:

            current = queue.popleft()

            result.append(current)

            for neighbor in self._graph.neighbors(current):

                indegree[neighbor.id] -= 1

                if indegree[neighbor.id] == 0:
                    queue.append(neighbor.id)

        if len(result) != self._graph.node_count():
            raise ValueError(
                "Graph contains a cycle."
            )

        return result