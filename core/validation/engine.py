"""
Validation Engine 2.0

File: core/validation/engine.py
Sprint: F-010

Central Validation Engine
"""

from __future__ import annotations

from typing import Any

from core.validation.models import (
    ValidationContext,
    ValidationReport,
)
from core.validation.rules.base import BaseValidationRule


class ValidationEngine:
    """
    Central Validation Engine.

    Responsible for:
        - registering validation rules,
        - executing rules,
        - building ValidationReport.
    """

    def __init__(self) -> None:
        self._rules: list[BaseValidationRule] = []

    @property
    def rules(self) -> tuple[BaseValidationRule, ...]:
        """Read-only collection of registered rules."""
        return tuple(self._rules)

    def register_rule(
        self,
        rule: BaseValidationRule,
    ) -> None:
        """
        Register validation rule.

        Duplicate rule_id is not allowed.
        """

        for existing in self._rules:
            if existing.rule_id == rule.rule_id:
                raise ValueError(
                    f"Validation rule '{rule.rule_id}' already registered."
                )

        self._rules.append(rule)

    def clear(self) -> None:
        """Remove all registered rules."""
        self._rules.clear()

    def validate(
        self,
        target: Any,
        context: ValidationContext | None = None,
    ) -> ValidationReport:
        """
        Execute all registered validation rules.
        """

        context = context or ValidationContext()

        report = ValidationReport()

        for rule in self._rules:
            issues = rule.validate(
                target=target,
                context=context,
            )

            report.extend(issues)

        return report

    def __len__(self) -> int:
        return len(self._rules)

    def __iter__(self):
        return iter(self._rules)

    def __repr__(self) -> str:
        return f"ValidationEngine(rules={len(self._rules)})"
