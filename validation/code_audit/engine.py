from __future__ import annotations
import ast
from pathlib import Path
from typing import List

from validation.code_audit.models import AuditReport, Finding, Severity
from validation.code_audit.rules.base import BaseRule
from validation.code_audit.rules.python_dead_code import DeadCodeRule
from validation.code_audit.rules.python_structure import StructureRule
from validation.code_audit.rules.python_complexity import ComplexityRule


class CodeAuditEngine:
    def __init__(self):
        self.rules: List[BaseRule] = [
            DeadCodeRule(),
            StructureRule(),
            ComplexityRule(),
        ]

    def audit_file(self, file_path: Path) -> List[Finding]:
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as e:
            return [
                Finding(
                    rule_id="SYNTAX",
                    severity=Severity.ERROR,
                    message=f"Błąd składni: {e}",
                    file=str(file_path),
                    line=e.lineno,
                )
            ]

        findings: List[Finding] = []
        for rule in self.rules:
            findings.extend(rule.check(tree, file_path))
        return findings

    def audit_directory(self, directory: Path, pattern: str = "**/*.py") -> AuditReport:
        report = AuditReport()
        for path in directory.glob(pattern):
            if path.is_file():
                for finding in self.audit_file(path):
                    report.add(finding)
        return report
