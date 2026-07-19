"""
Knowledge Operating System (KOS)

File: knowledge/cycle_detection.py
Version: 1.0
Sprint: GRAPH-008

Cycle detection for directed graphs.
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph


class CycleDetection:
    """
    Detect cycles in a directed KnowledgeGraph.
    """

    def __init__(self, graph: KnowledgeGraph) -> None:
        self._graph = graph

    def has_cycle(self) -> bool:
        """
        Returns True if the graph contains a cycle.
        """

        visited: set[str] = set()
        recursion_stack: set[str] = set()

        for node_id in self._graph.nodes:

            if node_id not in visited:

                if self._visit(
                    node_id,
                    visited,
                    recursion_stack,
                ):
                    return True

        return False

    def _visit(
        self,
        node_id: str,
        visited: set[str],
        recursion_stack: set[str],
    ) -> bool:

        visited.add(node_id)
        recursion_stack.add(node_id)

        for neighbor in self._graph.neighbors(node_id):

            if neighbor.id not in visited:

                if self._visit(
                    neighbor.id,
                    visited,
                    recursion_stack,
                ):
                    return True

            elif neighbor.id in recursion_stack:
                return True

        recursion_stack.remove(node_id)

        return False