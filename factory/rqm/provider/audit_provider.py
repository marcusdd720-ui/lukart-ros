"""Repository audit provider for RQM."""

from __future__ import annotations

import time

from factory.rqm.model import Finding, Result, Severity
from factory.rqm.provider.base_provider import BaseProvider


class AuditProvider(BaseProvider):
    """Basic repository structure audit."""

    provider_name = "audit"

    @property
    def name(self) -> str:
        return self.provider_name

    def run(self) -> Result:
        start = time.perf_counter()
        findings: list[Finding] = []

        try:
            required_files = [
                "README.md",
                ".gitignore",
            ]
            for rel in required_files:
                if not (self.root / rel).exists():
                    findings.append(
                        Finding(
                            rule_id="AUDIT_MISSING_FILE",
                            message=f"Missing required file: {rel}",
                            severity=Severity.WARNING,
                        )
                    )

            if not (self.root / "pyproject.toml").exists() and not (
                self.root / "setup.py"
            ).exists():
                findings.append(
                    Finding(
                        rule_id="AUDIT_MISSING_PROJECT_FILE",
                        message="Missing pyproject.toml and setup.py",
                        severity=Severity.WARNING,
                    )
                )

            workflows = self.root / ".github" / "workflows"
            if not workflows.exists():
                findings.append(
                    Finding(
                        rule_id="AUDIT_MISSING_WORKFLOWS",
                        message="Missing directory: .github/workflows",
                        severity=Severity.INFO,
                    )
                )

            return Result(
                name=self.name,
                duration=time.perf_counter() - start,
                findings=findings,
                metadata={"checks": "basic_repo_structure"},
            )
        except Exception as exc:  # noqa: BLE001
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