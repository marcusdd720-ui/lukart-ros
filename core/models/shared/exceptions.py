from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class KOSException(Exception):
    """
    Base exception for the Knowledge Operating System.
    """

    code = "KOS_ERROR"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.message = message or self.__class__.__name__
        self.code = code or self.code
        self.details = dict(details or {})
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.details:
            return f"[{self.code}] {self.message} | details={self.details}"

        return f"[{self.code}] {self.message}"


class DomainError(KOSException):
    """Raised when a domain rule is violated."""

    code = "DOMAIN_ERROR"


class ValidationError(KOSException):
    """Raised when validation fails."""

    code = "VALIDATION_ERROR"


class WorkflowError(KOSException):
    """Raised when workflow execution fails."""

    code = "WORKFLOW_ERROR"


class ConfigurationError(KOSException):
    """Raised when configuration is invalid or missing."""

    code = "CONFIGURATION_ERROR"


class PluginError(KOSException):
    """Raised when plugin registration or execution fails."""

    code = "PLUGIN_ERROR"


class InfrastructureError(KOSException):
    """Raised when infrastructure components fail."""

    code = "INFRASTRUCTURE_ERROR"


class KnowledgeError(KOSException):
    """Raised when knowledge graph or reasoning fails."""

    code = "KNOWLEDGE_ERROR"
