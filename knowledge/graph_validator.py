"""
Knowledge Operating System (KOS)

File: knowledge/graph_validator.py
Version: 1.0
Sprint: GRAPH-009

Knowledge Graph Validator.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from knowledge.cycle_detection import CycleDetection
from knowledge.graph import KnowledgeGraph


@dataclass(slots=True)
class ValidationIssue:
    """
    Represents a validation issue.
    """

    code: str
    message: str


@dataclass(slots=True)
class ValidationResult:
    """
    Graph validation result.
    """

    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return len(self.issues) == 0

    def add(
        self,
        code: str,
        message: str,
    ) -> None:

        self.issues.append(
            ValidationIssue(
                code=code,
                message=message,
            )
        )


class GraphValidator:
    """
    Validates Knowledge Graph consistency.
    """

    def validate(
        self,
        graph: KnowledgeGraph,
    ) -> ValidationResult:

        result = ValidationResult()

        self._check_missing_nodes(
            graph,
            result,
        )

        self._check_cycles(
            graph,
            result,
        )

        return result

    def _check_missing_nodes(
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

    def _check_cycles(
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