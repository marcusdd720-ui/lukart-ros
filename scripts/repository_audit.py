"""Project-wide structural audit used by CI.

This is deliberately narrower than Ruff/MyPy/Pytest: it checks the integrity of
our quality process itself. A report is not allowed to claim release readiness
from a hand-edited or stale snapshot.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

IGNORED_EMPTY_PY = {"__init__.py"}
STALE_REPORT_MARKERS = ("READY_FOR_MERGE", "Overall Score:")


def tracked_files(root: Path) -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files"], cwd=root, check=True, capture_output=True, text=True
    )
    return [root / line for line in completed.stdout.splitlines() if line]


def audit(root: Path) -> list[str]:
    files = tracked_files(root)
    findings: list[str] = []

    for path in files:
        relative = path.relative_to(root).as_posix()
        if not path.is_file():
            continue

        if path.suffix == ".py" and path.stat().st_size == 0 and path.name not in IGNORED_EMPTY_PY:
            findings.append(f"empty Python module: {relative}")

        if relative.startswith("reports/") and path.suffix == ".md":
            text = path.read_text(encoding="utf-8")
            if any(marker in text for marker in STALE_REPORT_MARKERS):
                findings.append(f"stale/manual release report: {relative}")

    if not (root / "pyproject.toml").is_file():
        findings.append("missing pyproject.toml")
    if not (root / ".github/workflows/ci.yml").is_file():
        findings.append("missing primary CI workflow")
    if not (root / "scripts/pii_scan.py").is_file():
        findings.append("missing PII/confidentiality gate")

    return sorted(findings)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    findings = audit(root)
    print("Repository audit scope: entire git-tracked tree")
    print(f"Tracked files: {len(tracked_files(root))}")
    if findings:
        print("Repository audit: FAIL")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("Repository audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
