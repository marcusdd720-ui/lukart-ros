"""Fail-closed scan for obvious PII and legal source artifacts."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".py",
    ".csv",
    ".xml",
    ".html",
}
FORBIDDEN_SUFFIXES = {".pdf", ".doc", ".docx", ".odt", ".rtf"}
PATTERNS = {
    "PESEL-like 11 digits": re.compile(r"(?<!\d)\d{11}(?!\d)"),
    "NIP-like number": re.compile(r"(?<!\d)\d{3}[- ]?\d{3}[- ]?\d{2}[- ]?\d{2}(?!\d)"),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "phone-like number": re.compile(
        r"(?<!\d)(?:\+48[ -]?)?\d{3}[ -]?\d{3}[ -]?\d{3}(?!\d)"
    ),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return [ROOT / item for item in result.stdout.splitlines() if item]


def scan() -> list[str]:
    findings: list[str] = []
    for path in tracked_files():
        relative = path.relative_to(ROOT).as_posix()
        suffix = path.suffix.lower()
        if suffix in FORBIDDEN_SUFFIXES:
            findings.append(f"forbidden legal artifact: {relative}")
            continue
        if suffix not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(f"non-UTF8 tracked text candidate requires review: {relative}")
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{label}: {relative}")
    return sorted(set(findings))


def main() -> int:
    findings = scan()
    if findings:
        print("PII/confidentiality gate: FAIL")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("PII/confidentiality gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
