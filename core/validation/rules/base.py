"""
Validation Engine 2.0

File: core/validation/rules/base.py
Sprint: F-010

Base Validation Rule
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.validation.models import (
    ValidationContext,
    ValidationIssue,
)


class BaseValidationRule(ABC):
    """
    Base class for every validation rule.

    Every validation rule must inherit from this class.
    """

    rule_id: str = "BASE-000"
    name: str = "Base Validation Rule"
    description: str = "Abstract validation rule."
    version: str = "1.0"

    @property
    def full_name(self) -> str:
        """Human readable rule identifier."""
        return f"{self.rule_id} - {self.name}"

    @abstractmethod
    def validate(
        self,
        target: Any,
        context: ValidationContext | None = None,
    ) -> list[ValidationIssue]:
        """
        Validate target object.

        Parameters
        ----------
        target
            Object to validate.

        context
            Optional validation context.

        Returns
        -------
        list[ValidationIssue]
            List of detected validation issues.
        """
        raise NotImplementedError

    def __str__(self) -> str:
        return self.full_name

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"rule_id='{self.rule_id}', "
            f"version='{self.version}')"
        )