"""
Case pipeline v0:
  1) build dossier with graph authorities
  2) run ReviewAgent checklist
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> int:
    print(">", " ".join(cmd))
    completed = subprocess.run(cmd, cwd=ROOT)
    return completed.returncode


def main() -> int:
    steps = [
        [sys.executable, str(ROOT / "scripts" / "export_dossier_with_authorities.py")],
        [
            sys.executable,
            str(ROOT / "scripts" / "review_dossier.py"),
            str(
                ROOT
                / "output"
                / "cases"
                / "DS_3960_2025"
                / "stanowisko_dossier_with_authorities.txt"
            ),
        ],
    ]

    for cmd in steps:
        code = run(cmd)
        if code != 0:
            print(f"PIPELINE FAIL (exit {code})")
            return code

    print("PIPELINE PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())