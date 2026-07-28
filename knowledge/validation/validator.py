"""
Knowledge Operating System (KOS)

Validation Engine.
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph
from knowledge.validation.registry import DEFAULT_VALIDATION_CHECKS
from knowledge.validation.result import ValidationResult


class ValidationEngine:
    def __init__(self) -> None:

        self._checks = list(DEFAULT_VALIDATION_CHECKS)

    def register(self, check) -> None:
        """
        Register additional validation rule.
        """

        self._checks.append(check)

    def validate(
        self,
        graph: KnowledgeGraph,
    ) -> ValidationResult:

        result = ValidationResult()

        for check in self._checks:
            check.validate(
                graph,
                result,
            )

        return result
