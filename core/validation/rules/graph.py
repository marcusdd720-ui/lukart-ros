"""
Validation Engine 2.0

File: core/validation/rules/graph.py
Sprint: F-010

KnowledgeGraph validation rules.
"""

from __future__ import annotations

from core.validation.models import (
    ValidationContext,
    ValidationIssue,
    Severity,
)

from core.validation.rules.base import BaseValidationRule

from knowledge.graph import KnowledgeGraph


class GraphIntegrityRule(BaseValidationRule):
    """
    Executes KnowledgeGraph internal integrity validation.
    """

    rule_id = "GRAPH-001"
    name = "Graph Integrity"
    description = "Checks graph integrity."
    version = "1.0"

    def validate(
        self,
        target: object,
        context: ValidationContext | None = None,
    ) -> list[ValidationIssue]:

        if not isinstance(target, KnowledgeGraph):
            return []

        issues: list[ValidationIssue] = []

        for error in target.validate_integrity():

            issues.append(
                ValidationIssue(
                    code=self.rule_id,
                    message=error,
                    severity=Severity.ERROR,
                )
            )

        return issues


class GraphEmptyRule(BaseValidationRule):
    """
    Checks whether graph contains nodes.
    """

    rule_id = "GRAPH-002"
    name = "Empty Graph"
    description = "Detects empty graph."
    version = "1.0"

    def validate(
        self,
        target: object,
        context: ValidationContext | None = None,
    ) -> list[ValidationIssue]:

        if not isinstance(target, KnowledgeGraph):
            return []

        if target.node_count() > 0:
            return []

        return [
            ValidationIssue(
                code=self.rule_id,
                message="KnowledgeGraph contains no nodes.",
                severity=Severity.WARNING,
            )
        ]


class GraphCycleRule(BaseValidationRule):
    """
    Detect cycles inside graph.
    """

    rule_id = "GRAPH-003"
    name = "Cycle Detection"
    description = "Detect graph cycles."
    version = "1.0"

    def validate(
        self,
        target: object,
        context: ValidationContext | None = None,
    ) -> list[ValidationIssue]:

        if not isinstance(target, KnowledgeGraph):
            return []

        if not target.has_cycle():
            return []

        return [
            ValidationIssue(
                code=self.rule_id,
                message="Graph contains cycle.",
                severity=Severity.WARNING,
            )
        ]