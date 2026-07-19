"""
Knowledge Operating System (KOS)

File: knowledge/traversal.py
Version: 1.0
Sprint: GRAPH-002

Traversal API for Knowledge Graph.
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode


class GraphTraversal:
    """
    Provides traversal operations for KnowledgeGraph.
    """

    def __init__(self, graph: KnowledgeGraph) -> None:
        self._graph = graph

    def neighbors(self, node_id: str) -> list[KnowledgeNode]:
        """
        Return direct neighbours of a node.
        """
        return self._graph.neighbors(node_id)

    def has_path(self, source: str, target: str) -> bool:
        """
        Determine whether a path exists between two nodes.
        """

        if source == target:
            return True

        visited: set[str] = set()
        queue: list[str] = [source]

        while queue:
            current = queue.pop(0)

            if current in visited:
                continue

            visited.add(current)

            for node in self._graph.neighbors(current):
                if node.id == target:
                    return True

                if node.id not in visited:
                    queue.append(node.id)

        return False