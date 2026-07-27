from __future__ import annotations

from pathlib import Path

from factory.rqm.audit.rule import AuditRule
from factory.rqm.model.finding import Finding


class InitRule(AuditRule):

    rule_id = "PY002"
    name = "__init__.py in package directories"
    description = "Directories containing Python files should have __init__.py"
    category = "python"
    severity = "WARNING"

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
        }

        for path in root.rglob("*.py"):
            if any(part in ignored_dirs for part in path.parts):
                continue

            parent = path.parent
            if parent == root:
                continue

            init_file = parent / "__init__.py"
            if not init_file.exists():
                rel_parent = parent.relative_to(root)
                if not any(f.file == str(rel_parent) for f in findings):
                    findings.append(
                        Finding(
                            rule_id=self.rule_id,
                            severity=self.severity,
                            message=f"Missing __init__.py in Python package directory '{rel_parent}'.",
                            file=str(rel_parent),
                            line=None,
                        )
                    )

        return findings