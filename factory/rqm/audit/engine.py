from __future__ import annotations

from pathlib import Path

from factory.rqm.audit.registry import AuditRegistry
from factory.rqm.model.finding import Finding
from factory.rqm.model.severity import Severity


class AuditEngine:
    """
    Executes all registered audit rules against a repository.

    The engine itself contains no business logic.
    It only orchestrates the execution of rules.
    """

    def __init__(self, root: Path, registry: AuditRegistry):
        self.root = root
        self.registry = registry

    def run(self) -> list[Finding]:
        """Execute all registered audit rules."""
        findings: list[Finding] = []

        for rule in self.registry.create_all():
            try:
                result = rule.check(self.root)
                if result:
                    findings.extend(result)
            except Exception as exc:
                findings.append(
                    Finding(
                        rule_id=rule.rule_id,
                        severity=Severity.ERROR,
                        message=f"Audit rule failed: {exc}",
                        file=None,
                        line=None,
                    )
                )

        return findings

    @property
    def rule_count(self) -> int:
        """Number of registered rules."""
        return len(self.registry)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(rules={self.rule_count})"
