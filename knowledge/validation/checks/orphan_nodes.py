"""
Knowledge Operating System (KOS)

Validation check:
Orphan Nodes
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph
from knowledge.validation.result import ValidationResult


class OrphanNodesCheck:
    """
    Detect nodes that are not connected
    by any incoming or outgoing edge.
    """

    def validate(
        self,
        graph: KnowledgeGraph,
        result: ValidationResult,
    ) -> None:

        connected: set[str] = set()

        for edge in graph.edges:
            connected.add(edge.source)
            connected.add(edge.target)

        for node_id in graph.nodes:

            if node_id not in connected:

                result.add(
                    "ORPHAN_NODE",
                    f"Node '{node_id}' is orphan."
                )