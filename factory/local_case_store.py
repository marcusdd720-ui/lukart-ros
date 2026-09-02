"""Private local storage policy for real MVROS cases.

Real case data must live outside the Git working tree. This module centralizes
that invariant so case creation/import/publish code cannot silently default to
repository-relative storage.
"""

from __future__ import annotations

import os
from pathlib import Path


class PrivacyViolation(RuntimeError):
    """Raised when real case data would be stored inside the repository."""


def find_repo_root(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        marker = candidate / ".git"
        if marker.exists():
            return candidate
    return None


def default_data_root() -> Path:
    configured = os.environ.get("MVROS_DATA_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "MVROS-DATA").resolve()


def validate_data_root(data_root: Path, *, repo_root: Path | None = None) -> Path:
    root = data_root.expanduser().resolve()
    repo = (repo_root or find_repo_root()).resolve() if (repo_root or find_repo_root()) else None

    if repo is not None and (root == repo or repo in root.parents):
        raise PrivacyViolation(
            "Real MVROS case data must be outside the Git repository: "
            f"data_root={root} repo_root={repo}"
        )

    if (root / ".git").exists():
        raise PrivacyViolation(f"Case data root must not contain a Git repository: {root}")

    return root


def ensure_data_root(
    data_root: Path | None = None,
    *,
    repo_root: Path | None = None,
) -> Path:
    root = validate_data_root(data_root or default_data_root(), repo_root=repo_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate_case_key(case_key: str) -> str:
    key = case_key.strip()
    if not key or key in {".", ".."}:
        raise PrivacyViolation("Case key cannot be empty or relative")
    if Path(key).is_absolute() or "/" in key or "\\" in key:
        raise PrivacyViolation(f"Unsafe case key: {case_key!r}")
    return key


def case_dir(case_key: str, data_root: Path | None = None, *, repo_root: Path | None = None) -> Path:
    root = ensure_data_root(data_root, repo_root=repo_root)
    return root / "cases" / validate_case_key(case_key)


def output_case_dir(
    case_key: str,
    data_root: Path | None = None,
    *,
    repo_root: Path | None = None,
) -> Path:
    root = ensure_data_root(data_root, repo_root=repo_root)
    return root / "output" / "cases" / validate_case_key(case_key)
