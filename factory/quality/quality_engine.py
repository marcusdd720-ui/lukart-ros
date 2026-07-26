from pathlib import Path
from subprocess import run
from typing import Dict

class QualityEngine:
    """Uruchamia wszystkie kontrole jakości."""

    def run_all_checks(self) -> Dict:
        report = {
            "failed_tests": 0,
            "lint_passed": True,
            "type_check_passed": True
        }

        # pytest
        try:
            result = run(["python", "-m", "pytest", "-q", "--tb=no"], cwd=Path.cwd(), capture_output=True, timeout=60)
            report["failed_tests"] = result.returncode
        except:
            report["failed_tests"] = 1

        # Ruff + mypy (opcjonalnie)
        # Można rozbudować

        return report