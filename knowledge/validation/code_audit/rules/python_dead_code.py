from __future__ import annotations
import ast
from pathlib import Path
from typing import List

from validation.code_audit.models import Finding, Severity
from validation.code_audit.rules.base import BaseRule


class DeadCodeRule(BaseRule):
    rule_id = "DEAD001"
    description = "Wykrywa nieosiągalny kod po return/raise"

    def check(self, tree: ast.AST, file_path: Path) -> List[Finding]:
        findings: List[Finding] = []

        class Visitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node: ast.FunctionDef):
                self._check_unreachable(node.body)
                self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                self._check_unreachable(node.body)
                self.generic_visit(node)

            def _check_unreachable(self, body: list):
                for i, stmt in enumerate(body):
                    if isinstance(stmt, (ast.Return, ast.Raise)):
                        for dead in body[i + 1:]:
                            findings.append(
                                Finding(
                                    rule_id="DEAD001",
                                    severity=Severity.ERROR,
                                    message="Nieosiągalny kod po return/raise",
                                    file=str(file_path),
                                    line=getattr(dead, "lineno", None),
                                )
                            )
                        break

        Visitor().visit(tree)
        return findings