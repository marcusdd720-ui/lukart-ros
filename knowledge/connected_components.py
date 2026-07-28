"""
Knowledge Operating System (KOS)

File: knowledge/connected_components.py
Version: 1.0
Sprint: GRAPH-005

Connected Components algorithm.
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph


class ConnectedComponents:
    """
    Finds connected components in a KnowledgeGraph.
    """

    def __init__(self, graph: KnowledgeGraph) -> None:
        self._graph = graph

    def find(self) -> list[list[str]]:
        """
        Return all connected components.

        Each component is represented as a list
        of node identifiers.
        """

        visited: set[str] = set()
        components: list[list[str]] = []

        for node_id in self._graph.nodes:
            if node_id in visited:
                continue

            component: list[str] = []

            self._dfs(
                node_id=node_id,
                visited=visited,
                component=component,
            )

            components.append(component)

        return components

    def _dfs(
        self,
        node_id: str,
        visited: set[str],
        component: list[str],
    ) -> None:

        if node_id in visited:
            return

        visited.add(node_id)
        component.append(node_id)

        for neighbor in self._graph.neighbors(node_id):
            self._dfs(
                neighbor.id,
                visited,
                component,
            )
