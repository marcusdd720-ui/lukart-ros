"""
Knowledge Operating System (KOS)

File: knowledge/validation/checks/missing_nodes.py
Sprint: GRAPH-010A
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph
from knowledge.validation.result import ValidationResult


class MissingNodesCheck:
    """
    Checks whether every edge references existing nodes.
    """

    def validate(
        self,
        graph: KnowledgeGraph,
        result: ValidationResult,
    ) -> None:

        for edge in graph.edges:
            if not graph.has_node(edge.source):
                result.add(
                    "UNKNOWN_SOURCE",
                    f"Unknown source node '{edge.source}'.",
                )

            if not graph.has_node(edge.target):
                result.add(
                    "UNKNOWN_TARGET",
                    f"Unknown target node '{edge.target}'.",
                )
