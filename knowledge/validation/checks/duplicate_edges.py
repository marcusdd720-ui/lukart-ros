"""
Knowledge Operating System (KOS)

Validation check:
Duplicate Edges
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph
from knowledge.validation.result import ValidationResult


class DuplicateEdgesCheck:
    """
    Detect duplicated graph edges.
    """

    def validate(
        self,
        graph: KnowledgeGraph,
        result: ValidationResult,
    ) -> None:

        seen: set[tuple[str, str]] = set()

        for edge in graph.edges:

            key = (
                edge.source,
                edge.target,
            )

            if key in seen:

                result.add(
                    "DUPLICATE_EDGE",
                    (
                        f"Duplicate edge "
                        f"{edge.source} -> {edge.target}"
                    ),
                )

            else:
                seen.add(key)