"""Fail-closed scan for obvious PII and legal source artifacts."""

from __future__ import annotations

import json
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
GOVERNANCE_CLOSURE_EVIDENCE_PREFIX = "evidence/governance_closure/"
GOVERNANCE_CLOSURE_EVIDENCE_SCHEMA = "lukart.closure-preparation-evidence.v1"
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


def _mask_governance_run_ids(relative: str, text: str) -> str:
    """Mask only provenance-bound GitHub workflow run IDs in canonical evidence.

    GitHub run IDs are positive integers and may naturally contain exactly
    eleven digits, which is indistinguishable from a PESEL-shaped token to a
    regex-only scanner. This exception is deliberately structural: it applies
    only to canonical closure-preparation evidence with the expected authority
    and result, and only to ``run_id`` fields inside the two workflow evidence
    arrays. Malformed/non-canonical JSON and every other numeric field remain
    unchanged and therefore remain subject to the normal fail-closed scan.
    """

    if not relative.startswith(GOVERNANCE_CLOSURE_EVIDENCE_PREFIX) or not relative.endswith(
        ".json"
    ):
        return text
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text
    if not isinstance(payload, dict):
        return text
    if (
        payload.get("schema") != GOVERNANCE_CLOSURE_EVIDENCE_SCHEMA
        or payload.get("authority") != "closure-preparation-only"
        or payload.get("result") != "PREPARED_NOT_CLOSED"
    ):
        return text

    for field in ("pr_workflows", "post_merge_workflows"):
        runs = payload.get(field)
        if not isinstance(runs, list):
            return text
        for run in runs:
            if not isinstance(run, dict):
                return text
            run_id = run.get("run_id")
            if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1:
                return text
            run["run_id"] = "<GITHUB_RUN_ID>"

    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def _pii_scan_text(text: str, *, relative: str = "") -> str:
    """Mask proven machine identifiers and standalone cryptographic digests.

    Cryptographic bindings are expected in validation/review metadata and can
    contain 9-11 digit runs that resemble Polish identifiers. Governance
    workflow run IDs are masked only after structural validation by
    :func:`_mask_governance_run_ids`. No adjacent or standalone phone, NIP,
    PESEL, email, or unrelated numeric value is suppressed.
    """

    machine_safe_text = _mask_governance_run_ids(relative, text)
    return CRYPTO_DIGEST.sub("<CRYPTO_DIGEST>", machine_safe_text)


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
        scan_text = _pii_scan_text(text, relative=relative)
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
