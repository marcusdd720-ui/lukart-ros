from __future__ import annotations

import hashlib
from pathlib import Path

from factory.rqm.audit.rule import AuditRule
from factory.rqm.model.finding import Finding


class DuplicateFileRule(AuditRule):

    rule_id = "DUP001"
    name = "No duplicate files"
    description = "Detect exact duplicate files in repository"
    category = "duplication"
    severity = "WARNING"

    def _hash_file(self, path: Path) -> str:

        hasher = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def check(self, root: Path) -> list[Finding]:

        findings: list[Finding] = []
        hashes: dict[str, str] = {}
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
                if path.stat().st_size == 0:
                    continue

                try:
                    rel_file = str(path.relative_to(root))
                    file_hash = self._hash_file(path)

                    if file_hash in hashes:
                        original = hashes[file_hash]
                        findings.append(
                            Finding(
                                rule_id=self.rule_id,
                                severity=self.severity,
                                message=f"Duplicate file detected (identical to '{original}').",
                                file=rel_file,
                                line=None,
                            )
                        )
                    else:
                        hashes[file_hash] = rel_file
                except Exception:
                    continue

        return findings