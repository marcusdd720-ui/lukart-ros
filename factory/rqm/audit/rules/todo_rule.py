from __future__ import annotations

from pathlib import Path

from factory.rqm.audit.rule import AuditRule
from factory.rqm.model.finding import Finding


class TodoRule(AuditRule):
    rule_id = "CODE001"
    name = "TODO / FIXME comments"
    description = "Find pending TODO or FIXME comments in source files"
    category = "code_quality"
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
        }
        supported_extensions = {
            ".py",
            ".md",
            ".toml",
            ".yml",
            ".yaml",
            ".json",
            ".sh",
        }

        for path in root.rglob("*"):
            if path.is_file() and path.suffix in supported_extensions:
                if any(part in ignored_dirs for part in path.parts):
                    continue

                try:
                    rel_file = str(path.relative_to(root))
                    with path.open("r", encoding="utf-8", errors="ignore") as f:
                        for idx, line in enumerate(f, start=1):
                            line_upper = line.upper()
                            if "TODO" in line_upper or "FIXME" in line_upper:
                                tag = "FIXME" if "FIXME" in line_upper else "TODO"
                                findings.append(
                                    Finding(
                                        rule_id=self.rule_id,
                                        severity=self.severity,
                                        message=f"Found {tag} comment: {line.strip()}",
                                        file=rel_file,
                                        line=idx,
                                    )
                                )
                except Exception:
                    continue

        return findings
