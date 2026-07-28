from __future__ import annotations

import ast
from pathlib import Path

from validation.code_audit.models import Finding, Severity
from validation.code_audit.rules.base import BaseRule


class StructureRule(BaseRule):
    rule_id = "STRUCT001"
    description = "Wykrywa zduplikowane definicje funkcji i klas"

    def check(self, tree: ast.AST, file_path: Path) -> list[Finding]:
        findings: list[Finding] = []
        seen_functions: dict[str, int] = {}
        seen_classes: dict[str, int] = {}

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
                if name in seen_functions:
                    findings.append(
                        Finding(
                            rule_id="STRUCT001",
                            severity=Severity.ERROR,
                            message=f"Zduplikowana funkcja: {name}",
                            file=str(file_path),
                            line=node.lineno,
                            symbol=name,
                        )
                    )
                else:
                    seen_functions[name] = node.lineno

            elif isinstance(node, ast.ClassDef):
                name = node.name
                if name in seen_classes:
                    findings.append(
                        Finding(
                            rule_id="STRUCT001",
                            severity=Severity.ERROR,
                            message=f"Zduplikowana klasa: {name}",
                            file=str(file_path),
                            line=node.lineno,
                            symbol=name,
                        )
                    )
                else:
                    seen_classes[name] = node.lineno

        return findings
