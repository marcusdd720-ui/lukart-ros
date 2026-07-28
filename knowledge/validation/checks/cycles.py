"""
Knowledge Operating System (KOS)

File: knowledge/validation/checks/cycles.py
Sprint: GRAPH-010A
"""

from __future__ import annotations

from knowledge.cycle_detection import CycleDetection
from knowledge.graph import KnowledgeGraph
from knowledge.validation.result import ValidationResult


class CycleCheck:
    """
    Detects cycles in a KnowledgeGraph.
    """

    def validate(
        self,
        graph: KnowledgeGraph,
        result: ValidationResult,
    ) -> None:

        detector = CycleDetection(graph)

        if detector.has_cycle():
            result.add(
                "GRAPH_CYCLE",
                "Graph contains at least one directed cycle.",
            )
