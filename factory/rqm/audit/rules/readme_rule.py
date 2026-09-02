from __future__ import annotations

from pathlib import Path

from factory.rqm.audit.rule import AuditRule
from factory.rqm.model.finding import Finding
from factory.rqm.model.severity import Severity


class ReadmeRule(AuditRule):
    rule_id = "DOC001"
    name = "README exists"
    description = "Repository should contain README.md"
    category = "documentation"
    severity = Severity.ERROR

    def check(self, root: Path) -> list[Finding]:

        if (root / "README.md").exists():
            return []

        return [
            Finding(
                rule_id=self.rule_id,
                severity=self.severity,
                message="README.md not found.",
                file="README.md",
                line=None,
            )
        ]
