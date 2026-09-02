"""
Knowledge Operating System (KOS)

Validation Engine.
"""

from __future__ import annotations

from typing import Protocol

from knowledge.graph import KnowledgeGraph
from knowledge.validation.registry import DEFAULT_VALIDATION_CHECKS
from knowledge.validation.result import ValidationResult


class ValidationCheck(Protocol):
    """Structural contract implemented by validation checks."""

    def validate(
        self,
        graph: KnowledgeGraph,
        result: ValidationResult,
    ) -> None: ...


class ValidationEngine:
    def __init__(self) -> None:
        self._checks: list[ValidationCheck] = list(DEFAULT_VALIDATION_CHECKS)

    def register(self, check: ValidationCheck) -> None:
        """Register additional validation rule."""
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
