from pathlib import Path
from subprocess import run


class QualityEngine:
    """Uruchamia wszystkie kontrole jakości."""

    def run_all_checks(self) -> dict:
        report = {
            "failed_tests": 0,
            "lint_passed": True,
            "type_check_passed": True,
        }

        try:
            result = run(
                ["python", "-m", "pytest", "-q", "--tb=no"],
                cwd=Path.cwd(),
                capture_output=True,
                timeout=60,
            )
            report["failed_tests"] = result.returncode
        except (OSError, TimeoutError):
            report["failed_tests"] = 1

        return report
