"""Fail-closed scan for obvious PII and legal source artifacts in the public tree."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

TEXT_SUFFIXES = {
    ".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".py", ".csv", ".xml", ".html"
}
FORBIDDEN_BINARY_SUFFIXES = {".pdf", ".doc", ".docx", ".odt", ".rtf", ".zip"}

PATTERNS = {
    "PESEL-like 11 digits": re.compile(r"(?<!\d)\d{11}(?!\d)"),
    "NIP-like 10 digits": re.compile(r"(?<!\d)\d{3}[- ]?\d{3}[- ]?\d{2}[- ]?\d{2}(?!\d)"),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "Polish phone-like number": re.compile(r"(?<!\d)(?:\+48[ -]?)?\d{3}[ -]?\d{3}[ -]?\d{3}(?!\d)"),
}


def tracked_paths(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=root, check=True, capture_output=True, text=True
    )
    return [root / line for line in result.stdout.splitlines() if line]


def scan(root: Path) -> list[str]:
    findings: list[str] = []
    for path in tracked_paths(root):
        relative = path.relative_to(root).as_posix()
        suffix = path.suffix.lower()

        if suffix in FORBIDDEN_BINARY_SUFFIXES:
            findings.append(f"forbidden legal/source artifact: {relative}")
            continue
        if suffix not in TEXT_SUFFIXES or not path.is_file():
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(f"non-UTF8 tracked file requires manual security review: {relative}")
            continue

        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{label}: {relative}")

    return sorted(set(findings))


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    findings = scan(root)
    if findings:
        print("PII/security gate: FAIL")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("PII/security gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
