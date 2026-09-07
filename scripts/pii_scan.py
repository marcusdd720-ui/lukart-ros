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
GENERATED_DEPENDENCY_ARTIFACTS = frozenset({"pylock.toml"})
CRYPTO_DIGEST = re.compile(r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{40}|[0-9A-Fa-f]{64})(?![0-9A-Fa-f])")
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


def _is_pii_text_candidate(relative: str, suffix: str) -> bool:
    """Return whether naive PII regexes are valid for this tracked text artifact.

    ``pylock.toml`` is a deterministic PEP 751 dependency artifact generated
    from ``uv.lock``. Registry URLs, sizes, timestamps and hashes contain
    arbitrary numeric runs that resemble Polish identifiers but are not
    user-authored personal data. The exemption is path-specific; ordinary TOML
    and every other supported text source remain in the fail-closed PII scan.
    """

    return suffix in TEXT_SUFFIXES and relative not in GENERATED_DEPENDENCY_ARTIFACTS


def _pii_scan_text(text: str) -> str:
    """Remove only standalone SHA-1/SHA-256 tokens before PII matching.

    Cryptographic bindings are expected in validation/review metadata and can
    contain 9-11 digit runs that resemble Polish identifiers. Masking the full
    40/64-hex token avoids that false positive without suppressing adjacent or
    standalone phone, NIP, PESEL, or email values.
    """

    return CRYPTO_DIGEST.sub("<CRYPTO_DIGEST>", text)


def scan() -> list[str]:
    findings: list[str] = []
    for path in tracked_files():
        relative = path.relative_to(ROOT).as_posix()
        suffix = path.suffix.lower()
        if suffix in FORBIDDEN_SUFFIXES:
            findings.append(f"forbidden legal artifact: {relative}")
            continue
        if not _is_pii_text_candidate(relative, suffix) or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(f"non-UTF8 tracked text candidate requires review: {relative}")
            continue
        scan_text = _pii_scan_text(text)
        for label, pattern in PATTERNS.items():
            if pattern.search(scan_text):
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
