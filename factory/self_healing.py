"""Deterministic self-healing primitives for the Factory lifecycle."""

from __future__ import annotations

import ast
import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FailureDiagnosis:
    """Structured classification of a failed stage gate."""

    category: str
    repairable_by_ruff: bool
    semantic_failure: bool


def diagnose_failure(log: str) -> FailureDiagnosis:
    """Classify a failure from concrete diagnostics rather than generic exit text."""
    lowered = log.lower()
    ruff_markers = ("ruff", "e501", "f401", "i001", "e402")
    if any(marker in lowered for marker in ruff_markers):
        return FailureDiagnosis("quality", True, False)
    if "mypy" in lowered or "type error" in lowered:
        return FailureDiagnosis("typing", False, True)
    if "importerror" in lowered or "modulenotfounderror" in lowered:
        return FailureDiagnosis("import", False, True)
    if "assertionerror" in lowered or "test failed" in lowered or "failed" in lowered:
        return FailureDiagnosis("test", False, True)
    return FailureDiagnosis("unknown", False, True)


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, text=True, capture_output=True)


def semantic_fingerprint(root: Path) -> str:
    """Hash Python ASTs and non-Python bytes to detect semantic changes."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts or path.suffix in {".pyc"}:
            continue
        relative = path.relative_to(root).as_posix().encode()
        digest.update(relative)
        if path.suffix == ".py":
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
                payload = ast.dump(tree, annotate_fields=True, include_attributes=False)
            except (OSError, SyntaxError):
                payload = path.read_bytes().hex()
            digest.update(payload.encode())
        else:
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _discard_uncommitted_changes() -> None:
    result = _run(["git", "reset", "--hard", "HEAD"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Cannot discard unsafe repair changes")
    result = _run(["git", "clean", "-fd"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Cannot clean unsafe repair changes")


def _commit_and_push(message: str) -> None:
    for command in (
        ["git", "add", "-A"],
        ["git", "commit", "-m", message],
        ["git", "push", "origin", "HEAD:main"],
    ):
        result = _run(command)
        if result.returncode != 0:
            detail = result.stderr.strip()
            raise RuntimeError(
                detail or f"Automatic repair command failed: {' '.join(command)}"
            )


def _candidate_is_safe_to_revert() -> bool:
    """Never revert lifecycle-state commits; only revert explicit code candidates."""
    result = _run(["git", "log", "-1", "--pretty=%s"])
    if result.returncode != 0:
        return False
    message = result.stdout.strip().lower()
    protected_prefixes = (
        "chore: advance stage lifecycle state",
        "chore: restart full stage lifecycle verification",
    )
    return not message.startswith(protected_prefixes)


def _revert_head_safely() -> bool:
    """Revert either a normal commit or a merge commit without guessing its parent."""
    if not _candidate_is_safe_to_revert():
        return False
    parents = _run(["git", "rev-list", "--parents", "-n", "1", "HEAD"])
    if parents.returncode != 0:
        return False
    parent_count = len(parents.stdout.strip().split()) - 1
    command = ["git", "revert", "--no-edit"]
    if parent_count > 1:
        command.extend(["-m", "1"])
    command.append("HEAD")
    return _run(command).returncode == 0


def repair_repository(root: Path, failure_log: str) -> bool:
    """Repair quality issues automatically; otherwise only rollback a safe code candidate."""
    diagnosis = diagnose_failure(failure_log)
    before = semantic_fingerprint(root)

    if diagnosis.repairable_by_ruff:
        ruff_check = _run(["python", "-m", "ruff", "check", ".", "--fix"])
        _run(["python", "-m", "ruff", "format", "."])
        after = semantic_fingerprint(root)
        status = _run(["git", "status", "--porcelain"])
        if (
            ruff_check.returncode in (0, 1)
            and status.returncode == 0
            and status.stdout.strip()
            and before == after
        ):
            _commit_and_push("fix: automatic stage repair")
            return True

    _discard_uncommitted_changes()
    if not diagnosis.semantic_failure:
        return False
    if not _revert_head_safely():
        return False
    _commit_and_push("fix: automatic semantic rollback")
    return True
