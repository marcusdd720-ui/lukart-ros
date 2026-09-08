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
GOVERNANCE_RUN_ID_DOCS = frozenset(
    {
        "MASTER_PLAN.md",
        "docs/GOVERNANCE_CLOSURE_AUTOMATION_V1.md",
        "docs/POST_HARDCORE_ROADMAP.md",
    }
)
GOVERNANCE_RUN_CONTEXT = re.compile(r"\b(?:workflow run|run id|self-dogfood run)\b", re.I)
BACKTICKED_ELEVEN_DIGITS = re.compile(r"`(?P<value>\d{11})`")
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


def _canonical_governance_run_ids(text: str) -> frozenset[int] | None:
    """Return run IDs only from structurally valid closure-preparation evidence."""

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if (
        payload.get("schema") != GOVERNANCE_CLOSURE_EVIDENCE_SCHEMA
        or payload.get("authority") != "closure-preparation-only"
        or payload.get("result") != "PREPARED_NOT_CLOSED"
    ):
        return None

    run_ids: set[int] = set()
    for field in ("pr_workflows", "post_merge_workflows"):
        runs = payload.get(field)
        if not isinstance(runs, list):
            return None
        for run in runs:
            if not isinstance(run, dict):
                return None
            run_id = run.get("run_id")
            if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1:
                return None
            run_ids.add(run_id)
    return frozenset(run_ids)


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
    run_ids = _canonical_governance_run_ids(text)
    if run_ids is None:
        return text

    payload = json.loads(text)
    for field in ("pr_workflows", "post_merge_workflows"):
        for run in payload[field]:
            run["run_id"] = "<GITHUB_RUN_ID>"
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def _mask_documented_governance_run_ids(
    relative: str, text: str, *, governance_run_ids: frozenset[int]
) -> str:
    """Mask exact evidence-bound run IDs in the three canonical governance docs.

    This is not a generic numeric exception. A token is masked only when all
    of these conditions hold: the path is one of the fixed canonical governance
    documents, the token is an eleven-digit value inside backticks, the same
    line explicitly identifies it as a workflow/run identifier, and the exact
    integer occurs in structurally valid closure-preparation machine evidence.
    Any unrelated PESEL-shaped value remains visible to the normal fail-closed
    regexes, even in the same document or on the same line.
    """

    if relative not in GOVERNANCE_RUN_ID_DOCS or not governance_run_ids:
        return text

    masked_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if not GOVERNANCE_RUN_CONTEXT.search(line):
            masked_lines.append(line)
            continue

        def replace(match: re.Match[str]) -> str:
            value = int(match.group("value"))
            if value in governance_run_ids:
                return "`<GITHUB_RUN_ID>`"
            return match.group(0)

        masked_lines.append(BACKTICKED_ELEVEN_DIGITS.sub(replace, line))
    return "".join(masked_lines)


def _pii_scan_text(
    text: str, *, relative: str = "", governance_run_ids: frozenset[int] = frozenset()
) -> str:
    """Mask proven machine identifiers and standalone cryptographic digests.

    Cryptographic bindings are expected in validation/review metadata and can
    contain 9-11 digit runs that resemble Polish identifiers. Governance
    workflow run IDs are masked only after structural validation of their
    machine evidence and, for prose, exact provenance/context matching. No
    adjacent or standalone phone, NIP, PESEL, email, or unrelated numeric value
    is suppressed.
    """

    machine_safe_text = _mask_governance_run_ids(relative, text)
    machine_safe_text = _mask_documented_governance_run_ids(
        relative, machine_safe_text, governance_run_ids=governance_run_ids
    )
    return CRYPTO_DIGEST.sub("<CRYPTO_DIGEST>", machine_safe_text)


def _collect_governance_run_ids(paths: list[Path]) -> frozenset[int]:
    """Collect exact run identities from valid tracked closure evidence only."""

    run_ids: set[int] = set()
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if not relative.startswith(GOVERNANCE_CLOSURE_EVIDENCE_PREFIX) or not relative.endswith(
            ".json"
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        evidence_run_ids = _canonical_governance_run_ids(text)
        if evidence_run_ids is not None:
            run_ids.update(evidence_run_ids)
    return frozenset(run_ids)


def scan() -> list[str]:
    findings: list[str] = []
    paths = tracked_files()
    governance_run_ids = _collect_governance_run_ids(paths)
    for path in paths:
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
        scan_text = _pii_scan_text(
            text, relative=relative, governance_run_ids=governance_run_ids
        )
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
