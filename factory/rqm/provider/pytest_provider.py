"""Pytest provider for RQM."""

from __future__ import annotations

import re
import subprocess
import time

from factory.rqm.model import Finding, Result, Severity
from factory.rqm.provider.base_provider import BaseProvider


class PytestProvider(BaseProvider):
    """Provider executing the project's pytest suite."""

    provider_name = "pytest"

    @property
    def name(self) -> str:
        return self.provider_name

    def run(self) -> Result:
        start = time.perf_counter()

        try:
            process = subprocess.run(
                ["python", "-m", "pytest", "-q", "--tb=no"],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            output = (process.stdout or "") + (process.stderr or "")
            passed, failed = self._parse(output)
            findings: list[Finding] = []

            if failed:
                findings.append(
                    Finding(
                        rule_id="PYTEST_FAILED",
                        message=f"{failed} test(s) failed",
                        severity=Severity.ERROR,
                    )
                )

            if process.returncode not in (0, 1) and not failed:
                findings.append(
                    Finding(
                        rule_id="PYTEST_ERROR",
                        message=f"pytest exited with code {process.returncode}",
                        severity=Severity.ERROR,
                    )
                )

            return Result(
                name=self.name,
                duration=time.perf_counter() - start,
                findings=findings,
                metadata={
                    "returncode": process.returncode,
                    "passed": passed,
                    "failed": failed,
                    "output_tail": output.strip()[-1500:],
                },
            )
        except Exception as exc:  # noqa: BLE001
            return Result(
                name=self.name,
                duration=time.perf_counter() - start,
                metadata={"exception": exc.__class__.__name__},
                findings=[
                    Finding(
                        rule_id="PYTEST_ERROR",
                        message=str(exc),
                        severity=Severity.ERROR,
                    )
                ],
            )

    @staticmethod
    def _parse(output: str) -> tuple[int, int]:
        passed = failed = 0
        m = re.search(r"(\d+)\s+passed", output)
        if m:
            passed = int(m.group(1))
        m = re.search(r"(\d+)\s+failed", output)
        if m:
            failed = int(m.group(1))
        return passed, failed