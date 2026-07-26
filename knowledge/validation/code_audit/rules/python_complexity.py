from __future__ import annotations
import ast
from pathlib import Path
from typing import List

from validation.code_audit.models import Finding, Severity
from validation.code_audit.rules.base import BaseRule


class ComplexityRule(BaseRule):
    rule_id = "COMP001"
    description = "Wykrywa zbyt złożone funkcje"

    MAX_COMPLEXITY = 12

    def check(self, tree: ast.AST, file_path: Path) -> List[Finding]:
        findings: List[Finding] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexity = self._calculate_complexity(node)
                if complexity > self.MAX_COMPLEXITY:
                    findings.append(
                        Finding(
                            rule_id="COMP001",
                            severity=Severity.WARNING,
                            message=f"Zbyt wysoka złożoność cyklomatyczna ({complexity}) w funkcji '{node.name}'",
                            file=str(file_path),
                            line=node.lineno,
                            symbol=node.name,
                        )
                    )
        return findings

    def _calculate_complexity(self, node: ast.AST) -> int:
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity