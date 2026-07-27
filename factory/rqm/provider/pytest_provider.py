from __future__ import annotations

import subprocess
import time

from factory.rqm.model import Finding, Result, Severity
from factory.rqm.provider.base_provider import BaseProvider


class PytestProvider(BaseProvider):
    """
    Provider executing the project's pytest suite.
    """

    @property
    def name(self) -> str:
        return "pytest"

    def run(self) -> Result:
        start = time.perf_counter()

        try:
            process = subprocess.run(
                ["python", "-m", "pytest", "-q", "--tb=no"],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=180,
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

            return Result(
                name=self.name,
                findings=findings,
                duration=time.perf_counter() - start,
                metadata={
                    "passed": passed,
                    "failed": failed,
                    "returncode": process.returncode,
                },
            )

        except Exception as exc:
            return Result(
                name=self.name,
                duration=time.perf_counter() - start,
                metadata={
                    "passed": 0,
                    "failed": 1,
                    "exception": exc.__class__.__name__,
                },
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
        """
        Parse pytest summary output.

        Examples:
            201 passed in 3.16s
            198 passed, 3 failed in 5.11s
        """
        passed = 0
        failed = 0

        for part in output.split(","):
            tokens = part.strip().split()

            if len(tokens) < 2:
                continue

            if tokens[0].isdigit():
                if tokens[1] == "passed":
                    passed = int(tokens[0])
                elif tokens[1] == "failed":
                    failed = int(tokens[0])

        return passed, failed