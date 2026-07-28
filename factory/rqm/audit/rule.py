from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from factory.rqm.model.finding import Finding


class AuditRule(ABC):
    """
    Base class for every audit rule.

    Each rule is responsible for checking one specific aspect
    of the repository and returning zero or more findings.
    """

    #: Unique identifier of the rule.
    rule_id: str = "UNKNOWN"

    #: Human-readable rule name.
    name: str = "Unnamed Rule"

    #: Short rule description.
    description: str = ""

    #: Category (documentation, security, structure, ...)
    category: str = "general"

    #: Default severity.
    severity: str = "WARNING"

    @abstractmethod
    def check(self, root: Path) -> list[Finding]:
        """
        Execute the rule.

        Parameters
        ----------
        root:
            Repository root directory.

        Returns
        -------
        list[Finding]
            Findings produced by the rule.
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}"
            f"(rule_id='{self.rule_id}', "
            f"category='{self.category}')"
        )
