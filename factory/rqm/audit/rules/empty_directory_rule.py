from __future__ import annotations

from pathlib import Path

from factory.rqm.audit.rule import AuditRule
from factory.rqm.model.finding import Finding


class EmptyDirectoryRule(AuditRule):

    rule_id = "DIR001"
    name = "No empty directories"
    description = "Repository should not contain empty directories"
    category = "structure"
    severity = "INFO"

    def check(self, root: Path) -> list[Finding]:

        findings: list[Finding] = []
        ignored_dirs = {
            ".git",
            ".pytest_cache",
            "__pycache__",
            ".venv",
            "venv",
            "build",
            "dist",
            ".idea",
            ".vscode",
        }

        for path in root.rglob("*"):
            if path.is_dir() and not any(part in ignored_dirs for part in path.parts):
                if not any(path.iterdir()):
                    rel_path = path.relative_to(root)
                    findings.append(
                        Finding(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            message=f"Empty directory found: '{rel_path}'.",
                            file=str(rel_path),
                            line=None,
                        )
                    )

        return findings