"""Project-wide integrity audit for LukArt ROS.

This audit is deliberately independent of the RQM implementation. It verifies
that the repository has an executable quality-control surface and that obvious
placeholder quality claims cannot pass as evidence.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "pyproject.toml",
    ".github/workflows/ci.yml",
    "scripts/repository_audit.py",
    "scripts/pii_scan.py",
)
FORBIDDEN_REPORT_MARKERS = (
    "READY_FOR_MERGE",
    "Overall Score: 100.0/100",
    "Overall Score: 100/100",
)


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [ROOT / item for item in result.stdout.splitlines() if item]


def audit() -> list[str]:
    findings: list[str] = []

    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            findings.append(f"missing required quality-control file: {relative}")

    for path in tracked_files():
        if path.suffix == ".py" and path.is_file() and path.stat().st_size == 0:
            findings.append(f"empty tracked Python module: {path.relative_to(ROOT)}")

        if path.suffix in {".md", ".txt"} and path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for marker in FORBIDDEN_REPORT_MARKERS:
                if marker in text and path.parts[0] == "reports":
                    findings.append(
                        f"stale quality claim in report {path.relative_to(ROOT)}: {marker}"
                    )

    return sorted(set(findings))


def main() -> int:
    findings = audit()
    if findings:
        print("Repository audit: FAIL")
        for finding in findings:
            print(f"- {finding}")
        return 1

    print("Repository audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
