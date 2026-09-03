"""Private local storage policy for real MVROS cases."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


class PrivacyViolation(RuntimeError):
    """Raised when real case data would be stored inside the repository."""


def find_repo_root(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def default_data_root() -> Path:
    configured = os.environ.get("MVROS_DATA_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "MVROS-DATA").resolve()


def validate_data_root(data_root: Path, *, repo_root: Path | None = None) -> Path:
    root = data_root.expanduser().resolve()
    repo = repo_root.expanduser().resolve() if repo_root else find_repo_root()

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


def case_dir(
    case_key: str,
    data_root: Path | None = None,
    *,
    repo_root: Path | None = None,
) -> Path:
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


def source_snapshot_dir(
    case_key: str,
    data_root: Path | None = None,
    *,
    repo_root: Path | None = None,
) -> Path:
    root = ensure_data_root(data_root, repo_root=repo_root)
    return case_dir(case_key, root, repo_root=repo_root) / "source-snapshots"


def save_source_snapshot(
    case_key: str,
    source_path: Path,
    *,
    data_root: Path | None = None,
    repo_root: Path | None = None,
) -> Path:
    """Store an immutable content-addressed source snapshot."""
    source = source_path.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    payload = source.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    destination_dir = source_snapshot_dir(case_key, data_root, repo_root=repo_root)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / digest
    if destination.exists():
        if destination.read_bytes() != payload:
            raise PrivacyViolation("Snapshot hash collision detected")
        return destination
    destination.write_bytes(payload)
    destination.chmod(0o444)
    return destination
