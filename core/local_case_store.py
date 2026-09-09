"""Private local storage policy for real MVROS cases."""

from __future__ import annotations

import os
from pathlib import Path

from core.enterprise.contracts import AuthorizationContext
from core.private_evidence_v1 import (
    EvidenceKeyProvider,
    EvidenceKind,
    PrivateEvidenceError,
    PrivateEvidenceStore,
)


class PrivacyViolation(RuntimeError):
    """Raised when real case data would cross a private storage boundary."""


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
    return case_dir(case_key, root, repo_root=repo_root) / ".private-evidence"


def save_source_snapshot(
    case_key: str,
    source_path: Path,
    *,
    authorization: AuthorizationContext | None = None,
    key_provider: EvidenceKeyProvider | None = None,
    tenant_id: str | None = None,
    key_id: str | None = None,
    key_version: int = 1,
    source_ref: str | None = None,
    data_root: Path | None = None,
    repo_root: Path | None = None,
) -> Path:
    """Store an encrypted snapshot whose evidence identity is plaintext sha256."""
    if authorization is None or key_provider is None or not tenant_id or not key_id:
        raise PrivacyViolation(
            "source snapshot requires authorization, key provider, tenant id and key id"
        )
    untrusted_source = source_path.expanduser().absolute()
    if untrusted_source.is_symlink() or not untrusted_source.is_file():
        raise FileNotFoundError(untrusted_source)
    source = untrusted_source.resolve()
    key = validate_case_key(case_key)
    try:
        store = PrivateEvidenceStore(
            source_snapshot_dir(key, data_root, repo_root=repo_root),
            key_provider=key_provider,
            authorization=authorization,
            tenant_id=tenant_id,
            case_id=key,
            key_id=key_id,
            key_version=key_version,
        )
        imported = store.import_file(
            source,
            source_ref=source_ref or f"snapshot:{source.name}",
            kind=EvidenceKind.PRIMARY,
        )
    except PrivateEvidenceError as exc:
        raise PrivacyViolation(str(exc)) from exc
    return imported.envelope_path
