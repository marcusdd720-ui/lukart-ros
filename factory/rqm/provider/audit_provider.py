from __future__ import annotations

import time

from factory.rqm.model import Finding, Result, Severity
from factory.rqm.provider.base_provider import BaseProvider


class AuditProvider(BaseProvider):
    """
    Provider executing the Validation Code Audit Engine.
    """

    @property
    def name(self) -> str:
        return "code_audit"

    def run(self) -> Result:
        start = time.perf_counter()

        try:
            from validation.code_audit.engine import CodeAuditEngine

            engine = CodeAuditEngine()
            report = engine.audit_directory(self.root / "knowledge")

            findings = [
                Finding(
                    rule_id=f.rule_id,
                    message=f.message,
                    severity=(
                        f.severity
                        if isinstance(f.severity, Severity)
                        else Severity(str(f.severity).upper())
                    ),
                    file=f.file,
                    line=f.line,
                )
                for f in report.findings
            ]

            return Result(
                name=self.name,
                findings=findings,
                duration=time.perf_counter() - start,
                metadata={
                    "errors": len(report.errors),
                    "warnings": len(report.warnings),
                },
            )

        except Exception as exc:
            return Result(
                name=self.name,
                duration=time.perf_counter() - start,
                metadata={"exception": exc.__class__.__name__},
                findings=[
                    Finding(
                        rule_id="AUDIT_ERROR",
                        message=str(exc),
                        severity=Severity.WARNING,
                    )
                ],
            )