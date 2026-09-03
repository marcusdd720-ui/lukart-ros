"""Lightweight deterministic secret-leakage scan for repository CI."""

from __future__ import annotations

import re
from pathlib import Path

PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"(?i)\b(?:aws_secret_access_key|github_token|api_key)\s*[:=]\s*['\"][^'\"]+['\"]"),
)
EXCLUDED_PATHS = {"scripts/secret_scan.py"}
EXCLUDED_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache"}


def scan_text(text: str) -> list[str]:
    findings: list[str] = []
    for pattern in PATTERNS:
        if pattern.search(text):
            findings.append(pattern.pattern)
    return findings


def scan_repository(root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        if relative in EXCLUDED_PATHS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in scan_text(text):
            findings.append(f"{relative}:{pattern}")
    return findings


def main() -> int:
    findings = scan_repository(Path.cwd().resolve())
    if findings:
        print("Secret-scanning findings:")
        print("\n".join(findings))
        return 1
    print("Secret-scanning: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
