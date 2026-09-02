from __future__ import annotations

from pathlib import Path

from factory.rqm.audit.rule import AuditRule
from factory.rqm.model.finding import Finding
from factory.rqm.model.severity import Severity


class LicenseRule(AuditRule):
    rule_id = "DOC002"
    name = "LICENSE exists"
    description = "Repository should contain LICENSE"
    category = "documentation"
    severity = Severity.WARNING

    def check(self, root: Path) -> list[Finding]:

        candidates = [
            "LICENSE",
            "LICENSE.txt",
            "LICENSE.md",
        ]

        for name in candidates:
            if (root / name).exists():
                return []

        return [
            Finding(
                rule_id=self.rule_id,
                severity=self.severity,
                message="LICENSE file not found.",
                file=None,
                line=None,
            )
        ]
