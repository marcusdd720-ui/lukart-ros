from __future__ import annotations

from pathlib import Path

from factory.rqm.audit.rule import AuditRule
from factory.rqm.model.finding import Finding
from factory.rqm.model.severity import Severity


class LargeFileRule(AuditRule):
    rule_id = "PERF001"
    name = "No large files"
    description = "Check for files larger than threshold (default: 5MB)"
    category = "performance"
    severity = Severity.WARNING

    max_bytes: int = 5 * 1024 * 1024  # 5 MB

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

        for path in root.rglob("*"):
            if path.is_file() and not any(part in ignored_dirs for part in path.parts):
                try:
                    size = path.stat().st_size
                    if size > self.max_bytes:
                        size_mb = size / (1024 * 1024)
                        rel_file = str(path.relative_to(root))
                        findings.append(
                            Finding(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=(
                                    f"File '{rel_file}' exceeds maximum size "
                                    f"({size_mb:.2f}MB > 5MB)."
                                ),
                                file=rel_file,
                                line=None,
                            )
                        )
                except Exception:
                    continue

        return findings
