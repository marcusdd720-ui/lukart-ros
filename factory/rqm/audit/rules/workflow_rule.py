from __future__ import annotations

from pathlib import Path

from factory.rqm.audit.rule import AuditRule
from factory.rqm.model.finding import Finding


class WorkflowRule(AuditRule):
    rule_id = "CI001"
    name = "GitHub Actions"
    description = "Repository should contain GitHub Actions workflow"
    category = "ci"
    severity = "WARNING"

    def check(self, root: Path) -> list[Finding]:

        workflow_dir = root / ".github" / "workflows"

        if workflow_dir.exists():
            if any(workflow_dir.glob("*.yml")) or any(workflow_dir.glob("*.yaml")):
                return []

        return [
            Finding(
                rule_id=self.rule_id,
                severity=self.severity,
                message="No GitHub Actions workflow found.",
                file=".github/workflows",
                line=None,
            )
        ]
