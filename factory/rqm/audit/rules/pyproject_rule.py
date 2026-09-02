from __future__ import annotations

from pathlib import Path

from factory.rqm.audit.rule import AuditRule
from factory.rqm.model.finding import Finding
from factory.rqm.model.severity import Severity


class PyprojectRule(AuditRule):
    rule_id = "PY001"
    name = "pyproject.toml exists"
    description = "Repository should contain pyproject.toml"
    category = "python"
    severity = Severity.ERROR

    def check(self, root: Path) -> list[Finding]:

        if (root / "pyproject.toml").exists():
            return []

        return [
            Finding(
                rule_id=self.rule_id,
                severity=self.severity,
                message="pyproject.toml not found.",
                file="pyproject.toml",
                line=None,
            )
        ]
