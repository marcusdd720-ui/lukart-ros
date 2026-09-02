from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from factory.rqm.model.finding import Finding
from factory.rqm.model.severity import Severity


class AuditRule(ABC):
    """
    Base class for every audit rule.

    Each rule is responsible for checking one specific aspect
    of the repository and returning zero or more findings.
    """

    rule_id: str = "UNKNOWN"
    name: str = "Unnamed Rule"
    description: str = ""
    category: str = "general"
    severity: Severity = Severity.WARNING

    @abstractmethod
    def check(self, root: Path) -> list[Finding]:
        """Execute the rule and return produced findings."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}"
            f"(rule_id='{self.rule_id}', "
            f"category='{self.category}')"
        )
