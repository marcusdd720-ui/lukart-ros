from __future__ import annotations

from pathlib import Path

from factory.rqm.audit.rule import AuditRule
from factory.rqm.model.finding import Finding


class GitignoreRule(AuditRule):

    rule_id = "GIT001"
    name = ".gitignore exists"
    description = "Repository should contain .gitignore"
    category = "git"
    severity = "WARNING"

    def check(self, root: Path) -> list[Finding]:

        if (root / ".gitignore").exists():
            return []

        return [
            Finding(
                rule_id=self.rule_id,
                severity=self.severity,
                message=".gitignore not found.",
                file=".gitignore",
                line=None,
            )
        ]