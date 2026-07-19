"""
Knowledge Operating System (KOS)

File: knowledge/validation/base.py
Version: 2.0
Sprint: GRAPH-010A

Validation interfaces.
"""

from __future__ import annotations

from typing import Protocol

from knowledge.graph import KnowledgeGraph
from knowledge.validation.result import ValidationResult


class ValidationCheck(Protocol):
    """
    Base protocol for every validation rule.
    """

    def validate(
        self,
        graph: KnowledgeGraph,
        result: ValidationResult,
    ) -> None: ...