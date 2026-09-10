"""IRR-01 deterministic public-only independent-review readiness package.

This module packages only allowlisted, Git-tracked bytes from one exact commit. It may
assert readiness to begin a real external review; it never creates reviewer provenance,
review outcomes, certification, or any other external-trust claim.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

IRR_SCHEMA_V1 = "lukart.independent-review-readiness.v1"
IRR_SCOPE_ID_V1 = "IRR-01/v1"
IRR_READINESS_STATUS = "READY_FOR_INDEPENDENT_REVIEW"
IRR_REVIEW_STATUS = "NOT_INDEPENDENTLY_REVIEWED"
IRR_AUTHORITY = "readiness-only-no-review-no-certification"
IRR_SOURCE_REPOSITORY = "marcusdd720-ui/lukart-ros"

ALLOWED_TOP_LEVEL_DIRS_V1 = (
    ".github",
    "agents",
    "canon",
    "certification_tests",
    "config",
    "core",
    "docs",
    "factory",
    "knowledge",
    "learning",
    "reasoning",
    "renderer",
    "scripts",
    "tests",
    "validation",
)
ALLOWED_ROOT_FILES_V1 = (
    ".gitignore",
    "AGENTS.md",
    "FOUNDATION.md",
    "MASTER_PLAN.md",
    "README.md",
    "SECURITY.md",
    "kos.py",
    "lukart_build_backend.py",
    "pylock.toml",
    "pyproject.toml",
    "run_audit.py",
    "uv.lock",
)
EXCLUDED_RUNTIME_ROOTS_V1 = ("cases", "data", "evidence", "reports", ".vscode")
MANDATORY_PATHS_V1 = (
    "MASTER_PLAN.md",
    "README.md",
    "SECURITY.md",
    "pyproject.toml",
    "docs/WORKING_PRINCIPLES.md",
    "docs/POST_HARDCORE_ROADMAP.md",
)

MAX_FILES_V1 = 5000
MAX_FILE_BYTES_V1 = 16 * 1024 * 1024
MAX_TOTAL_BYTES_V1 = 128 * 1024 * 1024

_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PACKAGE_NAME_RE = re.compile(
    r"^IRR-01-v1-(?P<commit>[0-9a-f]{40})-(?P<digest>[0-9a-f]{64})\.zip$"
)
_MANIFEST_KEYS = frozenset(
    {
        "schema",
        "scope_id",
        "readiness_status",
        "independent_review_status",
        "source_repository",
        "source_commit_sha",
        "public_only",
        "authority",
        "scope",
        "file_count",
        "total_payload_bytes",
        "payload_identity_sha256",
        "review_readme_sha256",
        "files",
    }
)
_SCOPE_KEYS = frozenset(
    {"allowed_top_level_dirs", "allowed_root_files", "excluded_runtime_roots", "mandatory_paths"}
)
_FILE_KEYS = frozenset({"path", "git_mode", "git_blob_sha", "sha256", "size"})


class IndependentReviewReadinessError(ValueError):
    """Fail-closed IRR-01 package or verification error."""


@dataclass(frozen=True, slots=True)
class ReviewPackageResultV1:
    package_path: Path
    sha256_path: Path
    source_commit_sha: str
    package_sha256: str
    file_count: int
    total_payload_bytes: int
    readiness_status: str = IRR_READINESS_STATUS
    independent_review_status: str = IRR_REVIEW_STATUS


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - Git SHA-1 object identity


def _require_git_sha(value: str) -> str:
    if not _GIT_SHA_RE.fullmatch(value):
        raise IndependentReviewReadinessError(
            "source commit must be a lowercase full 40-character Git SHA"
        )
    return value


def _safe_relative_path(raw: str, *, field: str = "path") -> PurePosixPath:
    if not raw or raw != raw.strip():
        raise IndependentReviewReadinessError(f"{field} must be nonblank and canonical")
    if "\\" in raw or "\x00" in raw or any(ord(ch) < 32 or ord(ch) == 127 for ch in raw):
        raise IndependentReviewReadinessError(f"unsafe {field}: {raw!r}")
    candidate = PurePosixPath(raw)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise IndependentReviewReadinessError(f"unsafe {field}: {raw!r}")
    if candidate.as_posix() != raw:
        raise IndependentReviewReadinessError(f"non-canonical {field}: {raw!r}")
    if ":" in candidate.parts[0]:
        raise IndependentReviewReadinessError(f"unsafe {field}: {raw!r}")
    return candidate


def _selected_path(path: str) -> bool:
    candidate = _safe_relative_path(path)
    if len(candidate.parts) == 1:
        return path in ALLOWED_ROOT_FILES_V1
    return candidate.parts[0] in ALLOWED_TOP_LEVEL_DIRS_V1


def _git(repo_root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise IndependentReviewReadinessError(
            f"git command failed ({' '.join(args)}): {message or 'unknown error'}"
        )
    return result.stdout


def _commit_exists(repo_root: Path, commit_sha: str) -> None:
    kind = _git(repo_root, "cat-file", "-t", commit_sha).decode("ascii", errors="strict").strip()
    if kind != "commit":
        raise IndependentReviewReadinessError("source SHA does not identify a Git commit")


def _list_selected_entries(repo_root: Path, commit_sha: str) -> list[dict[str, object]]:
    raw = _git(repo_root, "ls-tree", "-r", "-z", commit_sha)
    entries: list[dict[str, object]] = []
    seen: set[str] = set()
    total = 0
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, path_bytes = record.split(b"\t", 1)
            mode_bytes, kind_bytes, blob_bytes = metadata.split(b" ", 2)
            path = path_bytes.decode("utf-8", errors="strict")
            mode = mode_bytes.decode("ascii", errors="strict")
            kind = kind_bytes.decode("ascii", errors="strict")
            blob_sha = blob_bytes.decode("ascii", errors="strict")
        except (ValueError, UnicodeDecodeError) as exc:
            raise IndependentReviewReadinessError("invalid git tree entry") from exc
        if not _selected_path(path):
            continue
        if path in seen:
            raise IndependentReviewReadinessError(f"duplicate selected path: {path}")
        seen.add(path)
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise IndependentReviewReadinessError(
                f"selected path must be a regular Git blob, not symlink/submodule: {path}"
            )
        if not re.fullmatch(r"[0-9a-f]{40}", blob_sha):
            raise IndependentReviewReadinessError(f"invalid Git blob identity: {path}")
        data = _git(repo_root, "show", f"{commit_sha}:{path}")
        if len(data) > MAX_FILE_BYTES_V1:
            raise IndependentReviewReadinessError(f"selected file exceeds size limit: {path}")
        total += len(data)
        if total > MAX_TOTAL_BYTES_V1:
            raise IndependentReviewReadinessError("selected payload exceeds total size limit")
        if _git_blob_sha1(data) != blob_sha:
            raise IndependentReviewReadinessError(f"Git blob identity mismatch: {path}")
        entries.append(
            {
                "path": path,
                "git_mode": mode,
                "git_blob_sha": blob_sha,
                "sha256": _sha256(data),
                "size": len(data),
                "_data": data,
            }
        )
        if len(entries) > MAX_FILES_V1:
            raise IndependentReviewReadinessError("selected file count exceeds limit")
    entries.sort(key=lambda item: str(item["path"]))
    present = {str(item["path"]) for item in entries}
    missing = [path for path in MANDATORY_PATHS_V1 if path not in present]
    if missing:
        raise IndependentReviewReadinessError(
            "mandatory public review paths missing: " + ", ".join(missing)
        )
    return entries


def _public_file_record(entry: dict[str, object]) -> dict[str, object]:
    return {key: entry[key] for key in ("path", "git_mode", "git_blob_sha", "sha256", "size")}


def _scope_dict() -> dict[str, object]:
    return {
        "allowed_top_level_dirs": list(ALLOWED_TOP_LEVEL_DIRS_V1),
        "allowed_root_files": list(ALLOWED_ROOT_FILES_V1),
        "excluded_runtime_roots": list(EXCLUDED_RUNTIME_ROOTS_V1),
        "mandatory_paths": list(MANDATORY_PATHS_V1),
    }


def _review_readme(commit_sha: str) -> bytes:
    text = f"""# LUKART ROS — IRR-01 Independent Review Readiness Package v1

Source repository: `{IRR_SOURCE_REPOSITORY}`  
Exact source commit: `{commit_sha}`  
Readiness status: `{IRR_READINESS_STATUS}`  
Independent-review status: `{IRR_REVIEW_STATUS}`

This archive is an engineering handoff for a real independent reviewer. Repository
automation created and verified the package only. It did **not** perform an independent
review and did **not** certify LUKART ROS.

The fixed IRR-01/v1 scope contains public, Git-tracked source, tests, validation,
workflows and documentation. Runtime case material and generated/runtime evidence roots
(`cases/`, `data/`, `evidence/`, `reports/`) are outside this package by design.

Verification:
1. Verify the archive SHA-256 against the digest embedded in its filename and sidecar.
2. Inspect `manifest.json`; every repository file has Git blob identity, SHA-256 and size.
3. Independently inspect the exact source commit and review scope before issuing any
   external review outcome.

A PASS/FAIL review, reviewer identity, certification, or external attestation must come
from evidence outside this package and outside repository automation.
"""
    return text.encode("utf-8")


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    return info


def build_review_package_v1(
    *, repo_root: Path, commit_sha: str, output_dir: Path
) -> ReviewPackageResultV1:
    """Build a deterministic, content-addressed package from one exact Git commit."""

    commit_sha = _require_git_sha(commit_sha)
    root = repo_root.resolve()
    _commit_exists(root, commit_sha)
    entries = _list_selected_entries(root, commit_sha)
    public_records = [_public_file_record(entry) for entry in entries]
    total = sum(cast(int, record["size"]) for record in public_records)
    readme = _review_readme(commit_sha)
    manifest: dict[str, object] = {
        "schema": IRR_SCHEMA_V1,
        "scope_id": IRR_SCOPE_ID_V1,
        "readiness_status": IRR_READINESS_STATUS,
        "independent_review_status": IRR_REVIEW_STATUS,
        "source_repository": IRR_SOURCE_REPOSITORY,
        "source_commit_sha": commit_sha,
        "public_only": True,
        "authority": IRR_AUTHORITY,
        "scope": _scope_dict(),
        "file_count": len(public_records),
        "total_payload_bytes": total,
        "payload_identity_sha256": _sha256(_canonical_json_bytes(public_records)),
        "review_readme_sha256": _sha256(readme),
        "files": public_records,
    }
    manifest_bytes = _canonical_json_bytes(manifest)

    output_dir.mkdir(parents=True, exist_ok=True)
    provisional = output_dir / f"IRR-01-v1-{commit_sha}.zip"
    provisional.unlink(missing_ok=True)
    with zipfile.ZipFile(provisional, mode="w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(_zip_info("IRR-01/manifest.json"), manifest_bytes)
        archive.writestr(_zip_info("IRR-01/REVIEW_README.md"), readme)
        for entry in entries:
            archive.writestr(
                _zip_info(f"IRR-01/repository/{entry['path']}"),
                cast(bytes, entry["_data"]),
            )

    package_bytes = provisional.read_bytes()
    package_digest = _sha256(package_bytes)
    final = output_dir / f"IRR-01-v1-{commit_sha}-{package_digest}.zip"
    if final.exists() and final.read_bytes() != package_bytes:
        raise IndependentReviewReadinessError("content-addressed output collision")
    provisional.replace(final)
    sidecar = Path(f"{final}.sha256")
    sidecar.write_text(f"{package_digest}  {final.name}\n", encoding="ascii")
    return ReviewPackageResultV1(
        package_path=final,
        sha256_path=sidecar,
        source_commit_sha=commit_sha,
        package_sha256=package_digest,
        file_count=len(entries),
        total_payload_bytes=total,
    )


def _strict_keys(value: dict[str, Any], expected: frozenset[str], field: str) -> None:
    if set(value) != expected:
        raise IndependentReviewReadinessError(f"{field} key contract violation")


def _load_manifest(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IndependentReviewReadinessError("invalid manifest JSON") from exc
    if not isinstance(value, dict):
        raise IndependentReviewReadinessError("manifest must be a JSON object")
    _strict_keys(value, _MANIFEST_KEYS, "manifest")
    return value


def _validate_manifest(manifest: dict[str, Any], *, commit_sha: str) -> list[dict[str, Any]]:
    expected_scalars = {
        "schema": IRR_SCHEMA_V1,
        "scope_id": IRR_SCOPE_ID_V1,
        "readiness_status": IRR_READINESS_STATUS,
        "independent_review_status": IRR_REVIEW_STATUS,
        "source_repository": IRR_SOURCE_REPOSITORY,
        "source_commit_sha": commit_sha,
        "public_only": True,
        "authority": IRR_AUTHORITY,
    }
    for field, expected in expected_scalars.items():
        if manifest.get(field) != expected:
            raise IndependentReviewReadinessError(f"manifest {field} mismatch")
    scope = manifest.get("scope")
    if not isinstance(scope, dict):
        raise IndependentReviewReadinessError("manifest scope must be an object")
    _strict_keys(scope, _SCOPE_KEYS, "scope")
    if scope != _scope_dict():
        raise IndependentReviewReadinessError("manifest fixed scope mismatch")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise IndependentReviewReadinessError("manifest files must be a non-empty list")
    if len(files) > MAX_FILES_V1:
        raise IndependentReviewReadinessError("manifest file count exceeds limit")
    validated: list[dict[str, Any]] = []
    paths: list[str] = []
    total = 0
    for raw_record in files:
        if not isinstance(raw_record, dict):
            raise IndependentReviewReadinessError("manifest file record must be an object")
        _strict_keys(raw_record, _FILE_KEYS, "file record")
        path = raw_record.get("path")
        if not isinstance(path, str) or not _selected_path(path):
            raise IndependentReviewReadinessError("manifest contains out-of-scope path")
        mode = raw_record.get("git_mode")
        blob_sha = raw_record.get("git_blob_sha")
        digest = raw_record.get("sha256")
        size = raw_record.get("size")
        if mode not in {"100644", "100755"}:
            raise IndependentReviewReadinessError(f"invalid regular-file mode: {path}")
        if not isinstance(blob_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", blob_sha):
            raise IndependentReviewReadinessError(f"invalid Git blob SHA: {path}")
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise IndependentReviewReadinessError(f"invalid SHA-256: {path}")
        if (
            not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or size > MAX_FILE_BYTES_V1
        ):
            raise IndependentReviewReadinessError(f"invalid file size: {path}")
        paths.append(path)
        total += size
        validated.append(raw_record)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise IndependentReviewReadinessError("manifest paths must be unique and sorted")
    if total > MAX_TOTAL_BYTES_V1:
        raise IndependentReviewReadinessError("manifest payload exceeds total size limit")
    missing = [path for path in MANDATORY_PATHS_V1 if path not in set(paths)]
    if missing:
        raise IndependentReviewReadinessError("manifest mandatory paths missing")
    if manifest.get("file_count") != len(validated):
        raise IndependentReviewReadinessError("manifest file_count mismatch")
    if manifest.get("total_payload_bytes") != total:
        raise IndependentReviewReadinessError("manifest total_payload_bytes mismatch")
    if manifest.get("payload_identity_sha256") != _sha256(_canonical_json_bytes(validated)):
        raise IndependentReviewReadinessError("manifest payload identity mismatch")
    return validated


def verify_review_package_v1(package_path: Path) -> ReviewPackageResultV1:
    """Verify archive content address, fixed scope, statuses and every packaged byte."""

    match = _PACKAGE_NAME_RE.fullmatch(package_path.name)
    if match is None:
        raise IndependentReviewReadinessError("package filename is not content-addressed IRR-01/v1")
    commit_sha = match.group("commit")
    expected_digest = match.group("digest")
    package_bytes = package_path.read_bytes()
    actual_digest = _sha256(package_bytes)
    if actual_digest != expected_digest:
        raise IndependentReviewReadinessError("package SHA-256 does not match filename")
    sidecar = Path(f"{package_path}.sha256")
    if not sidecar.is_file():
        raise IndependentReviewReadinessError("package SHA-256 sidecar is missing")
    expected_sidecar = f"{actual_digest}  {package_path.name}\n"
    if sidecar.read_text(encoding="ascii") != expected_sidecar:
        raise IndependentReviewReadinessError("package SHA-256 sidecar mismatch")

    try:
        archive = zipfile.ZipFile(package_path, mode="r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise IndependentReviewReadinessError("invalid review package ZIP") from exc
    with archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise IndependentReviewReadinessError("duplicate ZIP member")
        if len(names) > MAX_FILES_V1 + 2:
            raise IndependentReviewReadinessError("ZIP member count exceeds limit")
        for info in infos:
            _safe_relative_path(info.filename, field="ZIP member")
            if info.is_dir() or info.compress_type != zipfile.ZIP_STORED:
                raise IndependentReviewReadinessError("ZIP must contain stored regular files only")
            if info.file_size > MAX_FILE_BYTES_V1:
                raise IndependentReviewReadinessError("ZIP member exceeds size limit")
        try:
            manifest_raw = archive.read("IRR-01/manifest.json")
            readme = archive.read("IRR-01/REVIEW_README.md")
        except KeyError as exc:
            raise IndependentReviewReadinessError("required package metadata is missing") from exc
        manifest = _load_manifest(manifest_raw)
        records = _validate_manifest(manifest, commit_sha=commit_sha)
        if manifest.get("review_readme_sha256") != _sha256(readme):
            raise IndependentReviewReadinessError("review README digest mismatch")
        if readme != _review_readme(commit_sha):
            raise IndependentReviewReadinessError("review README contract mismatch")
        expected_names = {"IRR-01/manifest.json", "IRR-01/REVIEW_README.md"}
        expected_names.update(f"IRR-01/repository/{record['path']}" for record in records)
        if set(names) != expected_names:
            raise IndependentReviewReadinessError("ZIP members do not match fixed manifest")
        total = 0
        for record in records:
            path = str(record["path"])
            data = archive.read(f"IRR-01/repository/{path}")
            total += len(data)
            if len(data) != record["size"]:
                raise IndependentReviewReadinessError(f"size mismatch: {path}")
            if _sha256(data) != record["sha256"]:
                raise IndependentReviewReadinessError(f"SHA-256 mismatch: {path}")
            if _git_blob_sha1(data) != record["git_blob_sha"]:
                raise IndependentReviewReadinessError(f"Git blob identity mismatch: {path}")
        if total != manifest["total_payload_bytes"]:
            raise IndependentReviewReadinessError("verified total payload size mismatch")

    return ReviewPackageResultV1(
        package_path=package_path,
        sha256_path=sidecar,
        source_commit_sha=commit_sha,
        package_sha256=actual_digest,
        file_count=len(records),
        total_payload_bytes=total,
    )
