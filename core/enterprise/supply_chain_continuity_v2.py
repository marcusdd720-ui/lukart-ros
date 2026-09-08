"""SSC-02 supply-chain continuity bundle.

The bundle is intentionally directory-based and verifier-first.  It binds the exact source
identity, lock/build inputs and physical wheels needed by an offline recovery drill.  The
verifier uses only the Python standard library so historical bundles do not depend on the
current LUKART runtime or third-party packages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import sys
import tarfile
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

CONTINUITY_SCHEMA = "lukart.supply-chain-continuity.v2"
MANIFEST_NAME = "continuity-manifest.json"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_ROLES = frozenset({"identity", "source", "verifier", "wheel"})


class SupplyChainContinuityError(ValueError):
    """Fail-closed SSC-02 contract violation."""


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_name(name: str) -> str:
    normalized = re.sub(r"[-_.]+", "-", name.strip()).lower()
    if not normalized:
        raise SupplyChainContinuityError("package name cannot be blank")
    return normalized


def _safe_relative_path(raw: object, *, field: str = "path") -> str:
    value = str(raw).strip()
    if not value or "\\" in value:
        raise SupplyChainContinuityError(f"invalid {field}")
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise SupplyChainContinuityError(f"unsafe {field}: {value!r}")
    return candidate.as_posix()


def _strict_keys(
    value: Mapping[str, object],
    *,
    expected: set[str],
    context: str,
) -> None:
    actual = set(value)
    if actual != expected:
        missing = ",".join(sorted(expected - actual))
        unknown = ",".join(sorted(actual - expected))
        raise SupplyChainContinuityError(
            f"{context} fields mismatch: missing={missing or '-'}, unknown={unknown or '-'}"
        )


def _load_toml(path: Path) -> dict[str, object]:
    try:
        loaded = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise SupplyChainContinuityError(f"cannot parse TOML: {path}") from exc
    if not isinstance(loaded, dict):
        raise SupplyChainContinuityError(f"TOML root must be a table: {path}")
    return loaded


def _locked_versions(pylock_path: Path) -> dict[str, tuple[str, frozenset[str]]]:
    data = _load_toml(pylock_path)
    if data.get("lock-version") != "1.0":
        raise SupplyChainContinuityError("unsupported pylock contract")
    raw_packages = data.get("packages")
    if not isinstance(raw_packages, list) or not raw_packages:
        raise SupplyChainContinuityError("pylock packages are missing")

    collected: dict[str, tuple[str, set[str]]] = {}
    for raw in raw_packages:
        if not isinstance(raw, dict):
            raise SupplyChainContinuityError("pylock package must be a table")
        name = str(raw.get("name", "")).strip()
        version = str(raw.get("version", "")).strip()
        if not name or not version:
            raise SupplyChainContinuityError("pylock package identity is incomplete")
        normalized = _normalize_name(name)
        if normalized not in collected:
            collected[normalized] = (name, set())
        collected[normalized][1].add(version)
    return {
        normalized: (display, frozenset(versions))
        for normalized, (display, versions) in collected.items()
    }


def export_locked_constraints(pylock_path: str | Path, output_path: str | Path) -> None:
    """Export exact package constraints from pylock without using uv or a resolver."""

    locked = _locked_versions(Path(pylock_path))
    lines: list[str] = []
    for normalized in sorted(locked):
        display, versions = locked[normalized]
        if len(versions) != 1:
            raise SupplyChainContinuityError(
                f"pylock has platform-dependent versions for {display}: {sorted(versions)}"
            )
        version = next(iter(versions))
        lines.append(f"{display}=={version}")
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _project_identity(pyproject_path: Path) -> tuple[str, str, dict[str, str]]:
    data = _load_toml(pyproject_path)
    project = data.get("project")
    build_system = data.get("build-system")
    if not isinstance(project, dict) or not isinstance(build_system, dict):
        raise SupplyChainContinuityError("pyproject project/build-system tables are required")
    name = str(project.get("name", "")).strip()
    version = str(project.get("version", "")).strip()
    if not name or not version:
        raise SupplyChainContinuityError("project name/version are required")

    raw_requires = build_system.get("requires")
    if not isinstance(raw_requires, list) or not raw_requires:
        raise SupplyChainContinuityError("build-system requires must be a non-empty list")
    pinned: dict[str, str] = {}
    for raw in raw_requires:
        requirement = str(raw).strip()
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^;,\s]+)", requirement)
        if match is None:
            raise SupplyChainContinuityError(
                f"build-system requirement is not exactly pinned: {requirement!r}"
            )
        normalized = _normalize_name(match.group(1))
        if normalized in pinned:
            raise SupplyChainContinuityError(f"duplicate build-system requirement: {normalized}")
        pinned[normalized] = match.group(2)
    return name, version, pinned


def _wheel_identity(path: Path) -> tuple[str, str]:
    try:
        with zipfile.ZipFile(path) as archive:
            metadata_names = sorted(
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            )
            if len(metadata_names) != 1:
                raise SupplyChainContinuityError(
                    f"wheel must contain exactly one METADATA file: {path.name}"
                )
            raw = archive.read(metadata_names[0]).decode("utf-8")
    except (OSError, UnicodeError, zipfile.BadZipFile, KeyError) as exc:
        raise SupplyChainContinuityError(f"invalid wheel: {path.name}") from exc

    message = Parser().parsestr(raw)
    name = str(message.get("Name", "")).strip()
    version = str(message.get("Version", "")).strip()
    if not name or not version:
        raise SupplyChainContinuityError(f"wheel identity is incomplete: {path.name}")
    return name, version


def _validate_source_archive(path: Path, *, source_sha: str) -> None:
    try:
        with tarfile.open(path, mode="r:") as archive:
            archived_sha = str(archive.pax_headers.get("comment", "")).strip().lower()
            if archived_sha != source_sha:
                raise SupplyChainContinuityError(
                    "source archive commit identity does not match source_sha"
                )
            for member in archive.getmembers():
                safe = _safe_relative_path(member.name, field="source archive path")
                if safe != member.name.rstrip("/"):
                    raise SupplyChainContinuityError(
                        f"non-canonical source archive path: {member.name!r}"
                    )
                if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                    raise SupplyChainContinuityError(
                        f"unsafe source archive member type: {member.name}"
                    )
                if not (member.isfile() or member.isdir()):
                    raise SupplyChainContinuityError(
                        f"unsupported source archive member type: {member.name}"
                    )
    except (OSError, tarfile.TarError) as exc:
        raise SupplyChainContinuityError("source archive is invalid") from exc


def _inventory_record(
    root: Path,
    relative: str,
    *,
    role: str,
    package_name: str | None = None,
    package_version: str | None = None,
) -> dict[str, object]:
    safe = _safe_relative_path(relative)
    if role not in _ALLOWED_ROLES:
        raise SupplyChainContinuityError(f"unsupported inventory role: {role}")
    path = root / safe
    if path.is_symlink() or not path.is_file():
        raise SupplyChainContinuityError(f"inventory path is not a regular file: {safe}")
    record: dict[str, object] = {
        "path": safe,
        "role": role,
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if role == "wheel":
        if not package_name or not package_version:
            raise SupplyChainContinuityError("wheel record requires package identity")
        record["package_name"] = package_name
        record["package_version"] = package_version
    return record


def _classify_inventory(root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_dir():
            continue
        if path.is_symlink():
            raise SupplyChainContinuityError(
                f"bundle must not contain symlinks: {path.relative_to(root).as_posix()}"
            )
        relative = path.relative_to(root).as_posix()
        if relative == MANIFEST_NAME:
            continue
        if relative.startswith("wheelhouse/") and relative.endswith(".whl"):
            package_name, package_version = _wheel_identity(path)
            records.append(
                _inventory_record(
                    root,
                    relative,
                    role="wheel",
                    package_name=package_name,
                    package_version=package_version,
                )
            )
        elif relative.startswith("identity/"):
            records.append(_inventory_record(root, relative, role="identity"))
        elif relative == "source/repository.tar":
            records.append(_inventory_record(root, relative, role="source"))
        elif relative == "verifier.py":
            records.append(_inventory_record(root, relative, role="verifier"))
        else:
            raise SupplyChainContinuityError(f"unclassified bundle file: {relative}")
    return records


def _validate_wheel_boundary(
    *,
    root: Path,
    inventory: Sequence[Mapping[str, object]],
) -> None:
    pylock = root / "identity" / "pylock.toml"
    pyproject = root / "identity" / "pyproject.toml"
    locked = _locked_versions(pylock)
    project_name, project_version, build_requirements = _project_identity(pyproject)
    normalized_project = _normalize_name(project_name)

    seen_project = 0
    seen_build: set[str] = set()
    for raw in inventory:
        if raw.get("role") != "wheel":
            continue
        name = str(raw.get("package_name", "")).strip()
        version = str(raw.get("package_version", "")).strip()
        normalized = _normalize_name(name)
        if normalized == normalized_project:
            if version != project_version:
                raise SupplyChainContinuityError("project wheel version mismatch")
            seen_project += 1
            continue
        if normalized in build_requirements:
            if version != build_requirements[normalized]:
                raise SupplyChainContinuityError(
                    f"build-tool wheel version mismatch: {name}"
                )
            seen_build.add(normalized)
            continue
        locked_entry = locked.get(normalized)
        if locked_entry is None or version not in locked_entry[1]:
            raise SupplyChainContinuityError(
                f"wheel is not bound by pylock/build identity: {name}=={version}"
            )

    if seen_project != 1:
        raise SupplyChainContinuityError(
            f"bundle requires exactly one project wheel, found {seen_project}"
        )
    missing_build = sorted(set(build_requirements) - seen_build)
    if missing_build:
        raise SupplyChainContinuityError(
            f"bundle is missing pinned build-tool wheels: {missing_build}"
        )


def _manifest_digest(payload: Mapping[str, object]) -> str:
    unsigned = dict(payload)
    unsigned.pop("manifest_digest", None)
    return hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()


def create_manifest(bundle_root: str | Path, *, source_sha: str) -> dict[str, object]:
    root = Path(bundle_root)
    normalized_sha = source_sha.strip().lower()
    if _SOURCE_SHA_RE.fullmatch(normalized_sha) is None:
        raise SupplyChainContinuityError("source_sha must be a full 40-character Git SHA")

    required = (
        "identity/pyproject.toml",
        "identity/pylock.toml",
        "identity/uv.lock",
        "identity/lukart_build_backend.py",
        "source/repository.tar",
        "verifier.py",
    )
    missing = [item for item in required if not (root / item).is_file()]
    if missing:
        raise SupplyChainContinuityError(f"required continuity inputs missing: {missing}")

    _validate_source_archive(root / "source" / "repository.tar", source_sha=normalized_sha)
    inventory = _classify_inventory(root)
    if not inventory:
        raise SupplyChainContinuityError("continuity inventory cannot be empty")
    _validate_wheel_boundary(root=root, inventory=inventory)

    payload: dict[str, object] = {
        "schema": CONTINUITY_SCHEMA,
        "source_sha": normalized_sha,
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "cache_tag": sys.implementation.cache_tag or "",
        },
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
        },
        "recovery_contract": {
            "network": "DENY",
            "index": "NONE",
            "artifact_source": "wheelhouse",
            "source_archive": "source/repository.tar",
            "verifier": "verifier.py",
        },
        "inventory": inventory,
    }
    payload["manifest_digest"] = _manifest_digest(payload)
    return payload


def write_manifest(bundle_root: str | Path, *, source_sha: str) -> dict[str, object]:
    root = Path(bundle_root)
    manifest = create_manifest(root, source_sha=source_sha)
    (root / MANIFEST_NAME).write_bytes(canonical_json_bytes(manifest) + b"\n")
    verify_continuity_bundle(root)
    return manifest


def build_continuity_bundle(
    *,
    bundle_root: str | Path,
    wheelhouse: str | Path,
    source_archive: str | Path,
    repo_root: str | Path,
    source_sha: str,
) -> dict[str, object]:
    root = Path(bundle_root)
    if root.exists() and any(root.iterdir()):
        raise SupplyChainContinuityError("bundle root must be absent or empty")
    root.mkdir(parents=True, exist_ok=True)

    source = Path(source_archive)
    wheels = Path(wheelhouse)
    repository = Path(repo_root)
    wheel_files = sorted(wheels.glob("*.whl"), key=lambda item: item.name.lower())
    if not wheel_files:
        raise SupplyChainContinuityError("wheelhouse contains no wheels")

    (root / "wheelhouse").mkdir()
    for wheel in wheel_files:
        shutil.copyfile(wheel, root / "wheelhouse" / wheel.name)

    (root / "identity").mkdir()
    for name in ("pyproject.toml", "pylock.toml", "uv.lock", "lukart_build_backend.py"):
        candidate = repository / name
        if not candidate.is_file():
            raise SupplyChainContinuityError(f"repository identity input missing: {name}")
        shutil.copyfile(candidate, root / "identity" / name)

    if not source.is_file():
        raise SupplyChainContinuityError("source archive is missing")
    (root / "source").mkdir()
    shutil.copyfile(source, root / "source" / "repository.tar")
    shutil.copyfile(Path(__file__), root / "verifier.py")
    return write_manifest(root, source_sha=source_sha)


def _parse_manifest(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SupplyChainContinuityError("continuity manifest is unreadable") from exc
    if not isinstance(payload, dict):
        raise SupplyChainContinuityError("continuity manifest root must be an object")
    _strict_keys(
        payload,
        expected={
            "schema",
            "source_sha",
            "python",
            "platform",
            "recovery_contract",
            "inventory",
            "manifest_digest",
        },
        context="manifest",
    )
    return payload


def verify_continuity_bundle(bundle_root: str | Path) -> str:
    root = Path(bundle_root)
    manifest_path = root / MANIFEST_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise SupplyChainContinuityError("continuity manifest is missing")
    payload = _parse_manifest(manifest_path)

    if payload["schema"] != CONTINUITY_SCHEMA:
        raise SupplyChainContinuityError("unsupported continuity schema")
    source_sha = str(payload["source_sha"]).strip().lower()
    if _SOURCE_SHA_RE.fullmatch(source_sha) is None:
        raise SupplyChainContinuityError("invalid manifest source_sha")
    digest = str(payload["manifest_digest"]).strip().lower()
    if _SHA256_RE.fullmatch(digest) is None or _manifest_digest(payload) != digest:
        raise SupplyChainContinuityError("continuity manifest digest mismatch")

    python_identity = payload["python"]
    platform_identity = payload["platform"]
    recovery = payload["recovery_contract"]
    if not isinstance(python_identity, dict):
        raise SupplyChainContinuityError("python identity must be an object")
    if not isinstance(platform_identity, dict):
        raise SupplyChainContinuityError("platform identity must be an object")
    if not isinstance(recovery, dict):
        raise SupplyChainContinuityError("recovery contract must be an object")
    _strict_keys(
        python_identity,
        expected={"implementation", "version", "cache_tag"},
        context="python identity",
    )
    _strict_keys(
        platform_identity,
        expected={"system", "machine"},
        context="platform identity",
    )
    _strict_keys(
        recovery,
        expected={"network", "index", "artifact_source", "source_archive", "verifier"},
        context="recovery contract",
    )
    if recovery != {
        "network": "DENY",
        "index": "NONE",
        "artifact_source": "wheelhouse",
        "source_archive": "source/repository.tar",
        "verifier": "verifier.py",
    }:
        raise SupplyChainContinuityError("unsupported recovery contract")

    raw_inventory = payload["inventory"]
    if not isinstance(raw_inventory, list) or not raw_inventory:
        raise SupplyChainContinuityError("inventory must be a non-empty list")

    expected_paths: set[str] = set()
    inventory: list[Mapping[str, object]] = []
    for raw in raw_inventory:
        if not isinstance(raw, dict):
            raise SupplyChainContinuityError("inventory record must be an object")
        role = str(raw.get("role", "")).strip()
        expected_keys = {"path", "role", "size", "sha256"}
        if role == "wheel":
            expected_keys |= {"package_name", "package_version"}
        _strict_keys(raw, expected=expected_keys, context="inventory record")
        if role not in _ALLOWED_ROLES:
            raise SupplyChainContinuityError(f"unsupported inventory role: {role}")
        safe = _safe_relative_path(raw["path"])
        if safe == MANIFEST_NAME or safe in expected_paths:
            raise SupplyChainContinuityError(f"duplicate/reserved inventory path: {safe}")
        expected_paths.add(safe)
        size = raw["size"]
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise SupplyChainContinuityError(f"invalid inventory size: {safe}")
        expected_digest = str(raw["sha256"]).strip().lower()
        if _SHA256_RE.fullmatch(expected_digest) is None:
            raise SupplyChainContinuityError(f"invalid inventory digest: {safe}")
        candidate = root / safe
        if candidate.is_symlink() or not candidate.is_file():
            raise SupplyChainContinuityError(f"inventory file missing/non-regular: {safe}")
        if candidate.stat().st_size != size:
            raise SupplyChainContinuityError(f"inventory size mismatch: {safe}")
        if sha256_file(candidate) != expected_digest:
            raise SupplyChainContinuityError(f"inventory digest mismatch: {safe}")
        if role == "wheel":
            actual_name, actual_version = _wheel_identity(candidate)
            if (
                actual_name != str(raw["package_name"])
                or actual_version != str(raw["package_version"])
            ):
                raise SupplyChainContinuityError(f"wheel metadata mismatch: {safe}")
        inventory.append(raw)

    actual_paths: set[str] = set()
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == MANIFEST_NAME:
            continue
        if path.is_symlink():
            raise SupplyChainContinuityError(f"bundle contains symlink: {relative}")
        actual_paths.add(relative)
    if actual_paths != expected_paths:
        missing = sorted(expected_paths - actual_paths)
        unexpected = sorted(actual_paths - expected_paths)
        raise SupplyChainContinuityError(
            f"bundle inventory boundary mismatch: missing={missing}, unexpected={unexpected}"
        )

    role_paths: dict[str, list[str]] = {role: [] for role in _ALLOWED_ROLES}
    for item in inventory:
        role_paths[str(item["role"])].append(str(item["path"]))
    if role_paths["source"] != ["source/repository.tar"]:
        raise SupplyChainContinuityError("source archive identity is not unique")
    if role_paths["verifier"] != ["verifier.py"]:
        raise SupplyChainContinuityError("verifier identity is not unique")
    required_identity = {
        "identity/pyproject.toml",
        "identity/pylock.toml",
        "identity/uv.lock",
        "identity/lukart_build_backend.py",
    }
    if set(role_paths["identity"]) != required_identity:
        raise SupplyChainContinuityError("identity-file boundary mismatch")

    _validate_source_archive(root / "source" / "repository.tar", source_sha=source_sha)
    _validate_wheel_boundary(root=root, inventory=inventory)
    return digest


def _cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LUKART SSC-02 continuity bundle")
    sub = parser.add_subparsers(dest="command", required=True)

    constraints = sub.add_parser("constraints")
    constraints.add_argument("pylock")
    constraints.add_argument("output")

    build = sub.add_parser("build")
    build.add_argument("--bundle", required=True)
    build.add_argument("--wheelhouse", required=True)
    build.add_argument("--source-archive", required=True)
    build.add_argument("--repo-root", default=".")
    build.add_argument("--source-sha", required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("bundle")

    args = parser.parse_args(argv)
    if args.command == "constraints":
        export_locked_constraints(args.pylock, args.output)
        return 0
    if args.command == "build":
        manifest = build_continuity_bundle(
            bundle_root=args.bundle,
            wheelhouse=args.wheelhouse,
            source_archive=args.source_archive,
            repo_root=args.repo_root,
            source_sha=args.source_sha,
        )
        print(f"SSC02_MANIFEST_DIGEST={manifest['manifest_digest']}")
        return 0
    digest = verify_continuity_bundle(args.bundle)
    print(f"SSC02_VERIFY=PASS digest={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
