"""LRD-01C content-addressed artifact escrow and least-privilege offline runner.

This module binds verified artifact bytes to the immutable LRD-01B manifest without
creating a second Product/CCL authority.  Backend location is never artifact identity.
The offline runner reuses the existing Enterprise process-isolation boundary and reports
the exact controls that were enforced; it is not a kernel/container sandbox.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import socket
import stat
import tempfile
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Protocol, cast

from core.case_ledger.contracts import ContentAddress
from core.enterprise.isolation import (
    IsolatedExecutionError,
    IsolatedTask,
    IsolationPolicy,
    ProcessIsolationExecutor,
)
from core.long_range_replay_v1 import (
    LongRangeReplayManifestV1,
    ReplayArtifactRole,
    ReplayPreservationStatus,
)
from core.p3.contracts import canonical_json

ARTIFACT_ESCROW_MANIFEST_SCHEMA_V1 = "lukart.artifact-escrow-manifest.v1"
ESCROW_BINDING_SCHEMA_V1 = "lukart.artifact-escrow-binding.v1"
ESCROW_BLOB_SCHEMA_V1 = "lukart.artifact-blob.v1"
OFFLINE_REPLAY_RECEIPT_SCHEMA_V1 = "lukart.offline-replay-receipt.v1"
OFFLINE_REPLAY_ENTRYPOINT_V1 = "core.artifact_escrow_v1:offline_verify_escrow_worker"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MANIFEST_KEYS = frozenset(
    {
        "schema",
        "case_id",
        "long_range_manifest_identity",
        "bindings",
        "escrow_manifest_identity",
    }
)
_BINDING_KEYS = frozenset(
    {
        "schema",
        "role",
        "logical_identity",
        "blob",
        "kind",
        "binding_identity",
    }
)
_BLOB_KEYS = frozenset({"schema", "algorithm", "digest", "size"})
_RECEIPT_KEYS = frozenset(
    {
        "schema",
        "case_id",
        "long_range_manifest_identity",
        "escrow_manifest_identity",
        "task_digest",
        "output_digest",
        "verified_blob_count",
        "network_mode",
        "network_enforcement",
        "process_enforcement",
        "native_ffi_enforcement",
        "filesystem_enforcement",
        "kernel_sandbox",
        "receipt_identity",
    }
)


class ArtifactEscrowError(ValueError):
    """Fail-closed LRD-01C contract violation."""


class EscrowArtifactKind(StrEnum):
    BLOB = "BLOB"
    ZIP = "ZIP"


def _canonical_copy(value: Mapping[str, object], *, field_name: str) -> dict[str, object]:
    if any(not isinstance(key, str) for key in value):
        raise ArtifactEscrowError(f"{field_name} keys must be strings")
    try:
        decoded: object = json.loads(canonical_json(dict(value)))
    except (TypeError, ValueError) as exc:
        raise ArtifactEscrowError(f"{field_name} is not canonically serializable") from exc
    if not isinstance(decoded, dict):
        raise ArtifactEscrowError(f"{field_name} must be an object")
    return cast(dict[str, object], decoded)


def _strict_keys(
    value: Mapping[str, object],
    *,
    expected: frozenset[str],
    field_name: str,
) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = ",".join(sorted(expected - actual)) or "-"
    unknown = ",".join(sorted(actual - expected)) or "-"
    raise ArtifactEscrowError(
        f"{field_name} key contract violation: missing={missing}; unknown={unknown}"
    )


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArtifactEscrowError(f"{field_name} must be a nonblank string")
    if value != value.strip():
        raise ArtifactEscrowError(f"{field_name} must already be canonical")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ArtifactEscrowError(f"{field_name} cannot contain control characters")
    return value


def _address(value: object, *, field_name: str) -> ContentAddress:
    if not isinstance(value, Mapping):
        raise ArtifactEscrowError(f"{field_name} must be a content-address object")
    if set(value) != {"algorithm", "digest"}:
        raise ArtifactEscrowError(f"{field_name} content-address fields are invalid")
    try:
        return ContentAddress.from_dict(cast(Mapping[str, object], value))
    except ValueError as exc:
        raise ArtifactEscrowError(str(exc)) from exc


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _int_field(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ArtifactEscrowError(f"{field_name} must be an integer")
    return value


def _float_field(value: object, *, field_name: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ArtifactEscrowError(f"{field_name} must be numeric")
    return float(value)


def _safe_relative_path(raw: str, *, field_name: str = "path") -> PurePosixPath:
    value = _text(raw, field_name=field_name)
    if "\\" in value or "\x00" in value:
        raise ArtifactEscrowError(f"unsafe {field_name}: {value!r}")
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ArtifactEscrowError(f"unsafe {field_name}: {value!r}")
    if candidate.as_posix() != value:
        raise ArtifactEscrowError(f"non-canonical {field_name}: {value!r}")
    first = candidate.parts[0]
    if ":" in first:
        raise ArtifactEscrowError(f"unsafe {field_name}: {value!r}")
    return candidate


def _path_is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _secure_root(raw: str | Path, *, field_name: str) -> Path:
    candidate = Path(raw).expanduser()
    absolute = candidate if candidate.is_absolute() else Path.cwd() / candidate
    for item in (absolute, *absolute.parents):
        if item.exists() and item.is_symlink():
            raise ArtifactEscrowError(f"{field_name} must not traverse a symlink")
    return absolute.resolve(strict=False)


def _reject_symlink_chain(root: Path, relative: PurePosixPath) -> Path:
    root = root.resolve(strict=False)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ArtifactEscrowError(f"symlink escape rejected: {relative.as_posix()}")
        resolved = current.resolve(strict=False)
        if not _path_is_within(resolved, root):
            raise ArtifactEscrowError(f"path escapes root: {relative.as_posix()}")
    return current


@dataclass(frozen=True, slots=True)
class EscrowLimitsV1:
    """Deterministic resource bounds for bytes/archive handling and offline execution."""

    max_blob_bytes: int = 64 * 1024 * 1024
    max_archive_bytes: int = 64 * 1024 * 1024
    max_archive_members: int = 4096
    max_member_bytes: int = 32 * 1024 * 1024
    max_expanded_bytes: int = 256 * 1024 * 1024
    max_compression_ratio: int = 200
    io_chunk_bytes: int = 1024 * 1024
    runner_timeout_seconds: float = 30.0
    runner_memory_bytes: int = 512 * 1024 * 1024
    runner_cpu_seconds: int = 20

    def __post_init__(self) -> None:
        integer_fields = (
            self.max_blob_bytes,
            self.max_archive_bytes,
            self.max_archive_members,
            self.max_member_bytes,
            self.max_expanded_bytes,
            self.max_compression_ratio,
            self.io_chunk_bytes,
            self.runner_memory_bytes,
            self.runner_cpu_seconds,
        )
        if any(value <= 0 for value in integer_fields):
            raise ArtifactEscrowError("all escrow integer limits must be positive")
        if self.runner_timeout_seconds <= 0:
            raise ArtifactEscrowError("runner timeout must be positive")
        if self.max_archive_bytes > self.max_blob_bytes:
            raise ArtifactEscrowError("max_archive_bytes cannot exceed max_blob_bytes")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "max_blob_bytes": self.max_blob_bytes,
            "max_archive_bytes": self.max_archive_bytes,
            "max_archive_members": self.max_archive_members,
            "max_member_bytes": self.max_member_bytes,
            "max_expanded_bytes": self.max_expanded_bytes,
            "max_compression_ratio": self.max_compression_ratio,
            "io_chunk_bytes": self.io_chunk_bytes,
            "runner_timeout_seconds": self.runner_timeout_seconds,
            "runner_memory_bytes": self.runner_memory_bytes,
            "runner_cpu_seconds": self.runner_cpu_seconds,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> EscrowLimitsV1:
        expected = frozenset(cls().canonical_dict())
        raw = _canonical_copy(value, field_name="escrow limits")
        _strict_keys(raw, expected=expected, field_name="escrow limits")
        return cls(
            max_blob_bytes=_int_field(raw.get("max_blob_bytes"), field_name="max_blob_bytes"),
            max_archive_bytes=_int_field(
                raw.get("max_archive_bytes"),
                field_name="max_archive_bytes",
            ),
            max_archive_members=_int_field(
                raw.get("max_archive_members"),
                field_name="max_archive_members",
            ),
            max_member_bytes=_int_field(
                raw.get("max_member_bytes"),
                field_name="max_member_bytes",
            ),
            max_expanded_bytes=_int_field(
                raw.get("max_expanded_bytes"),
                field_name="max_expanded_bytes",
            ),
            max_compression_ratio=_int_field(
                raw.get("max_compression_ratio"),
                field_name="max_compression_ratio",
            ),
            io_chunk_bytes=_int_field(raw.get("io_chunk_bytes"), field_name="io_chunk_bytes"),
            runner_timeout_seconds=_float_field(
                raw.get("runner_timeout_seconds"),
                field_name="runner_timeout_seconds",
            ),
            runner_memory_bytes=_int_field(
                raw.get("runner_memory_bytes"),
                field_name="runner_memory_bytes",
            ),
            runner_cpu_seconds=_int_field(
                raw.get("runner_cpu_seconds"),
                field_name="runner_cpu_seconds",
            ),
        )


@dataclass(frozen=True, slots=True)
class EscrowBlobIdentityV1:
    """Raw-byte identity. Backend path/location is intentionally absent."""

    digest: str
    size: int
    algorithm: str = "sha256"
    schema: str = ESCROW_BLOB_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != ESCROW_BLOB_SCHEMA_V1:
            raise ArtifactEscrowError(f"unsupported blob schema: {self.schema}")
        if self.algorithm != "sha256":
            raise ArtifactEscrowError(f"unsupported blob digest algorithm: {self.algorithm}")
        if _SHA256_RE.fullmatch(self.digest) is None:
            raise ArtifactEscrowError("blob digest must be lowercase sha256")
        if isinstance(self.size, bool) or self.size < 0:
            raise ArtifactEscrowError("blob size must be a non-negative integer")

    @classmethod
    def for_bytes(cls, data: bytes) -> EscrowBlobIdentityV1:
        return cls(digest=_sha256_bytes(data), size=len(data))

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> EscrowBlobIdentityV1:
        raw = _canonical_copy(value, field_name="escrow blob")
        _strict_keys(raw, expected=_BLOB_KEYS, field_name="escrow blob")
        if not isinstance(raw.get("digest"), str):
            raise ArtifactEscrowError("blob digest must be a string")
        size = raw.get("size")
        if not isinstance(size, int) or isinstance(size, bool):
            raise ArtifactEscrowError("blob size must be an integer")
        return cls(
            schema=_text(raw.get("schema"), field_name="blob schema"),
            algorithm=_text(raw.get("algorithm"), field_name="blob algorithm"),
            digest=cast(str, raw["digest"]),
            size=size,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "algorithm": self.algorithm,
            "digest": self.digest,
            "size": self.size,
        }


@dataclass(frozen=True, slots=True)
class EscrowArtifactBindingV1:
    """Bind one LRD logical identity to exact preserved bytes."""

    role: ReplayArtifactRole
    logical_identity: ContentAddress
    blob: EscrowBlobIdentityV1
    kind: EscrowArtifactKind
    binding_identity: ContentAddress
    schema: str = ESCROW_BINDING_SCHEMA_V1

    @classmethod
    def build(
        cls,
        *,
        role: ReplayArtifactRole,
        logical_identity: ContentAddress,
        blob: EscrowBlobIdentityV1,
        kind: EscrowArtifactKind = EscrowArtifactKind.BLOB,
    ) -> EscrowArtifactBindingV1:
        body = {
            "schema": ESCROW_BINDING_SCHEMA_V1,
            "role": role.value,
            "logical_identity": logical_identity.canonical_dict(),
            "blob": blob.canonical_dict(),
            "kind": kind.value,
        }
        return cls(
            role=role,
            logical_identity=logical_identity,
            blob=blob,
            kind=kind,
            binding_identity=ContentAddress.for_value(body),
        )

    def __post_init__(self) -> None:
        if self.schema != ESCROW_BINDING_SCHEMA_V1:
            raise ArtifactEscrowError(f"unsupported escrow binding schema: {self.schema}")
        expected = ContentAddress.for_value(self.body_dict())
        if expected != self.binding_identity:
            raise ArtifactEscrowError("escrow binding identity mismatch")

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> EscrowArtifactBindingV1:
        raw = _canonical_copy(value, field_name="escrow binding")
        _strict_keys(raw, expected=_BINDING_KEYS, field_name="escrow binding")
        try:
            role = ReplayArtifactRole(_text(raw.get("role"), field_name="escrow role"))
            kind = EscrowArtifactKind(_text(raw.get("kind"), field_name="escrow kind"))
        except ValueError as exc:
            raise ArtifactEscrowError("unknown escrow role/kind") from exc
        blob_raw = raw.get("blob")
        if not isinstance(blob_raw, Mapping):
            raise ArtifactEscrowError("escrow binding blob must be an object")
        return cls(
            schema=_text(raw.get("schema"), field_name="escrow binding schema"),
            role=role,
            logical_identity=_address(
                raw.get("logical_identity"),
                field_name="escrow logical identity",
            ),
            blob=EscrowBlobIdentityV1.from_dict(cast(Mapping[str, object], blob_raw)),
            kind=kind,
            binding_identity=_address(
                raw.get("binding_identity"),
                field_name="escrow binding identity",
            ),
        )

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "role": self.role.value,
            "logical_identity": self.logical_identity.canonical_dict(),
            "blob": self.blob.canonical_dict(),
            "kind": self.kind.value,
        }

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "binding_identity": self.binding_identity.canonical_dict()}


@dataclass(frozen=True, slots=True)
class ArtifactEscrowManifestV1:
    """Content-addressed physical-preservation projection over one immutable LRD manifest."""

    case_id: str
    long_range_manifest_identity: ContentAddress
    bindings: tuple[EscrowArtifactBindingV1, ...]
    escrow_manifest_identity: ContentAddress
    schema: str = ARTIFACT_ESCROW_MANIFEST_SCHEMA_V1

    @classmethod
    def build(
        cls,
        *,
        long_range_manifest: LongRangeReplayManifestV1,
        bindings: Sequence[EscrowArtifactBindingV1],
    ) -> ArtifactEscrowManifestV1:
        long_range_manifest.verify()
        ordered = tuple(sorted(bindings, key=lambda item: item.role.value))
        candidate = cls(
            case_id=long_range_manifest.case_id,
            long_range_manifest_identity=long_range_manifest.manifest_identity,
            bindings=ordered,
            escrow_manifest_identity=ContentAddress.for_value(
                {
                    "schema": ARTIFACT_ESCROW_MANIFEST_SCHEMA_V1,
                    "case_id": long_range_manifest.case_id,
                    "long_range_manifest_identity": (
                        long_range_manifest.manifest_identity.canonical_dict()
                    ),
                    "bindings": [item.canonical_dict() for item in ordered],
                }
            ),
        )
        candidate.verify_against(long_range_manifest)
        return candidate

    def __post_init__(self) -> None:
        if self.schema != ARTIFACT_ESCROW_MANIFEST_SCHEMA_V1:
            raise ArtifactEscrowError(f"unsupported escrow manifest schema: {self.schema}")
        _text(self.case_id, field_name="escrow case_id")
        roles = tuple(item.role.value for item in self.bindings)
        if tuple(sorted(set(roles))) != roles:
            raise ArtifactEscrowError("escrow bindings must be unique and sorted")
        expected = ContentAddress.for_value(self.body_dict())
        if expected != self.escrow_manifest_identity:
            raise ArtifactEscrowError("escrow manifest identity mismatch")

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ArtifactEscrowManifestV1:
        raw = _canonical_copy(value, field_name="escrow manifest")
        _strict_keys(raw, expected=_MANIFEST_KEYS, field_name="escrow manifest")
        raw_bindings = raw.get("bindings")
        if not isinstance(raw_bindings, list):
            raise ArtifactEscrowError("escrow manifest bindings must be a list")
        bindings: list[EscrowArtifactBindingV1] = []
        for item in raw_bindings:
            if not isinstance(item, Mapping):
                raise ArtifactEscrowError("escrow binding must be an object")
            bindings.append(
                EscrowArtifactBindingV1.from_dict(cast(Mapping[str, object], item))
            )
        return cls(
            schema=_text(raw.get("schema"), field_name="escrow manifest schema"),
            case_id=_text(raw.get("case_id"), field_name="escrow case_id"),
            long_range_manifest_identity=_address(
                raw.get("long_range_manifest_identity"),
                field_name="long_range_manifest_identity",
            ),
            bindings=tuple(bindings),
            escrow_manifest_identity=_address(
                raw.get("escrow_manifest_identity"),
                field_name="escrow_manifest_identity",
            ),
        )

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "long_range_manifest_identity": self.long_range_manifest_identity.canonical_dict(),
            "bindings": [item.canonical_dict() for item in self.bindings],
        }

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.body_dict(),
            "escrow_manifest_identity": self.escrow_manifest_identity.canonical_dict(),
        }

    def verify_against(self, long_range_manifest: LongRangeReplayManifestV1) -> None:
        long_range_manifest.verify()
        if self.case_id != long_range_manifest.case_id:
            raise ArtifactEscrowError("escrow manifest case does not match LRD manifest")
        if self.long_range_manifest_identity != long_range_manifest.manifest_identity:
            raise ArtifactEscrowError("escrow manifest is bound to a different LRD manifest")

        lrd_by_role = {item.role: item for item in long_range_manifest.artifacts}
        binding_by_role = {item.role: item for item in self.bindings}
        preserved = {
            role
            for role, item in lrd_by_role.items()
            if item.preservation is ReplayPreservationStatus.PRESERVED
        }
        if set(binding_by_role) != preserved:
            missing = (
                ",".join(sorted(role.value for role in preserved - set(binding_by_role))) or "-"
            )
            unexpected = ",".join(
                sorted(role.value for role in set(binding_by_role) - preserved)
            ) or "-"
            raise ArtifactEscrowError(
                "escrow bindings must exactly cover PRESERVED LRD roles: "
                f"missing={missing}; unexpected={unexpected}"
            )
        for role, binding in binding_by_role.items():
            if binding.logical_identity != lrd_by_role[role].identity:
                raise ArtifactEscrowError(
                    f"escrow logical identity mismatch for role {role.value}"
                )


class ArtifactEscrowBackendV1(Protocol):
    """Minimal replaceable byte-store contract."""

    def publish(self, data: bytes, *, limits: EscrowLimitsV1) -> EscrowBlobIdentityV1: ...

    def read(
        self,
        identity: EscrowBlobIdentityV1,
        *,
        limits: EscrowLimitsV1,
    ) -> bytes: ...


class FileSystemEscrowBackendV1:
    """Immutable content-addressed filesystem backend.

    The backend has no update/delete API.  Every read re-verifies size and sha256, so
    external mutation is detected rather than trusted.
    """

    def __init__(self, root: str | Path, *, create: bool = True) -> None:
        self.root = _secure_root(root, field_name="escrow root")
        if create:
            self.root.mkdir(parents=True, exist_ok=True)
        elif not self.root.is_dir():
            raise ArtifactEscrowError("escrow root does not exist")

    def _path(self, identity: EscrowBlobIdentityV1) -> Path:
        relative = PurePosixPath("sha256", identity.digest[:2], identity.digest)
        return _reject_symlink_chain(self.root, relative)

    def publish(self, data: bytes, *, limits: EscrowLimitsV1) -> EscrowBlobIdentityV1:
        if len(data) > limits.max_blob_bytes:
            raise ArtifactEscrowError("artifact exceeds max_blob_bytes")
        identity = EscrowBlobIdentityV1.for_bytes(data)
        path = self._path(identity)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = self.read(identity, limits=limits)
            if existing != data:
                raise ArtifactEscrowError("content-addressed escrow path collision")
            return identity

        fd: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            flags |= getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(path, flags, 0o600)
            with os.fdopen(fd, "wb", closefd=True) as handle:
                fd = None
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(path, 0o444)
        except FileExistsError:
            existing = self.read(identity, limits=limits)
            if existing != data:
                raise ArtifactEscrowError("content-addressed escrow path collision") from None
        except BaseException:
            if fd is not None:
                os.close(fd)
            try:
                if path.exists() and not path.is_symlink():
                    path.unlink()
            except OSError:
                pass
            raise
        self.read(identity, limits=limits)
        return identity

    def read(
        self,
        identity: EscrowBlobIdentityV1,
        *,
        limits: EscrowLimitsV1,
    ) -> bytes:
        if identity.size > limits.max_blob_bytes:
            raise ArtifactEscrowError("declared blob exceeds max_blob_bytes")
        path = self._path(identity)
        try:
            details = path.lstat()
        except OSError as exc:
            raise ArtifactEscrowError("escrow blob is unavailable") from exc
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
            raise ArtifactEscrowError("escrow blob must be a regular non-symlink file")
        if details.st_size != identity.size:
            raise ArtifactEscrowError("escrow blob size mismatch")
        digest = hashlib.sha256()
        collected = bytearray()
        try:
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(limits.io_chunk_bytes)
                    if not chunk:
                        break
                    collected.extend(chunk)
                    digest.update(chunk)
                    if len(collected) > identity.size:
                        raise ArtifactEscrowError("escrow blob grew during verified read")
        except OSError as exc:
            raise ArtifactEscrowError("cannot read escrow blob") from exc
        if len(collected) != identity.size or digest.hexdigest() != identity.digest:
            raise ArtifactEscrowError("escrow blob digest mismatch")
        return bytes(collected)

    def restore_blob(
        self,
        identity: EscrowBlobIdentityV1,
        *,
        destination_root: str | Path,
        relative_path: str,
        limits: EscrowLimitsV1,
    ) -> Path:
        data = self.read(identity, limits=limits)
        root = _secure_root(destination_root, field_name="destination root")
        root.mkdir(parents=True, exist_ok=True)
        relative = _safe_relative_path(relative_path, field_name="restore path")
        destination = _reject_symlink_chain(root, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        _reject_symlink_chain(root, relative)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(destination, flags, 0o600)
        except FileExistsError as exc:
            raise ArtifactEscrowError("restore destination already exists") from exc
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        return destination


def migrate_verified_blob(
    identity: EscrowBlobIdentityV1,
    *,
    source: ArtifactEscrowBackendV1,
    target: ArtifactEscrowBackendV1,
    limits: EscrowLimitsV1,
) -> EscrowBlobIdentityV1:
    """Copy verified bytes to another backend/location without changing canonical identity."""

    data = source.read(identity, limits=limits)
    restored = target.publish(data, limits=limits)
    if restored != identity:
        raise ArtifactEscrowError("alternate-storage restore changed blob identity")
    if target.read(restored, limits=limits) != data:
        raise ArtifactEscrowError("alternate-storage restore verification failed")
    return restored


def _zip_member_kind(info: zipfile.ZipInfo) -> str:
    mode = (info.external_attr >> 16) & 0xFFFF
    if stat.S_ISLNK(mode):
        return "symlink"
    if info.is_dir():
        return "directory"
    file_type = stat.S_IFMT(mode)
    if file_type not in {0, stat.S_IFREG}:
        return "special"
    return "file"


def validate_zip_bytes(data: bytes, *, limits: EscrowLimitsV1) -> tuple[zipfile.ZipInfo, ...]:
    """Fail-closed bounded ZIP preflight before any extraction write."""

    if len(data) > limits.max_archive_bytes:
        raise ArtifactEscrowError("archive exceeds max_archive_bytes")
    try:
        with zipfile.ZipFile(io.BytesIO(data), mode="r") as archive:
            members = tuple(archive.infolist())
    except zipfile.BadZipFile as exc:
        raise ArtifactEscrowError("invalid ZIP archive") from exc

    if len(members) > limits.max_archive_members:
        raise ArtifactEscrowError("archive member count exceeds limit")

    expanded = 0
    seen: set[str] = set()
    for info in members:
        name = info.filename.rstrip("/")
        if not name:
            raise ArtifactEscrowError("blank/root archive member is forbidden")
        relative = _safe_relative_path(name, field_name="archive member path")
        canonical = relative.as_posix()
        if canonical in seen:
            raise ArtifactEscrowError(f"duplicate archive path: {canonical}")
        seen.add(canonical)
        kind = _zip_member_kind(info)
        if kind == "symlink":
            raise ArtifactEscrowError(f"archive symlink rejected: {canonical}")
        if kind == "special":
            raise ArtifactEscrowError(f"archive special member rejected: {canonical}")
        if info.flag_bits & 0x1:
            raise ArtifactEscrowError("encrypted ZIP members are unsupported")
        if kind == "directory":
            continue
        if info.file_size > limits.max_member_bytes:
            raise ArtifactEscrowError("archive member exceeds max_member_bytes")
        expanded += info.file_size
        if expanded > limits.max_expanded_bytes:
            raise ArtifactEscrowError("archive expanded size exceeds limit")
        if info.file_size:
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > limits.max_compression_ratio:
                raise ArtifactEscrowError("archive compression ratio exceeds limit")
    return members


def extract_verified_zip(
    identity: EscrowBlobIdentityV1,
    *,
    backend: ArtifactEscrowBackendV1,
    destination: str | Path,
    limits: EscrowLimitsV1,
) -> Path:
    """Atomically extract a verified ZIP to a new directory.

    Validation rejects traversal/symlink/special members and decompression bombs before
    any destination publication.  Extraction occurs in a sibling temporary directory.
    """

    data = backend.read(identity, limits=limits)
    members = validate_zip_bytes(data, limits=limits)
    destination_path = _secure_root(destination, field_name="archive destination")
    if destination_path.exists():
        raise ArtifactEscrowError("archive destination must not already exist")
    parent = _secure_root(destination_path.parent, field_name="archive destination parent")
    parent.mkdir(parents=True, exist_ok=True)

    temporary = Path(tempfile.mkdtemp(prefix=".lukart-escrow-", dir=parent))
    published = False
    try:
        temporary_root = temporary.resolve(strict=False)
        with zipfile.ZipFile(io.BytesIO(data), mode="r") as archive:
            for info in members:
                name = info.filename.rstrip("/")
                relative = _safe_relative_path(name, field_name="archive member path")
                target = _reject_symlink_chain(temporary_root, relative)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                _reject_symlink_chain(temporary_root, relative)
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                flags |= getattr(os, "O_NOFOLLOW", 0)
                fd = os.open(target, flags, 0o600)
                written = 0
                try:
                    with os.fdopen(fd, "wb") as output, archive.open(info, "r") as member:
                        while True:
                            chunk = member.read(limits.io_chunk_bytes)
                            if not chunk:
                                break
                            written += len(chunk)
                            if written > info.file_size or written > limits.max_member_bytes:
                                raise ArtifactEscrowError(
                                    "archive member exceeded declared/bounded size"
                                )
                            output.write(chunk)
                    if written != info.file_size:
                        raise ArtifactEscrowError("archive member size mismatch")
                except BaseException:
                    try:
                        target.unlink()
                    except OSError:
                        pass
                    raise
        os.rename(temporary, destination_path)
        published = True
        return destination_path
    except (OSError, zipfile.BadZipFile) as exc:
        raise ArtifactEscrowError("verified ZIP extraction failed") from exc
    finally:
        if not published:
            shutil.rmtree(temporary, ignore_errors=True)


def _worker_payload_mapping(
    value: object,
    *,
    field_name: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ArtifactEscrowError(f"{field_name} must be an object")
    return cast(Mapping[str, object], value)


def offline_verify_escrow_worker(payload: Mapping[str, object]) -> dict[str, object]:
    """Fixed allow-listed worker used by the LRD-01C offline runner."""

    root = _text(payload.get("escrow_root"), field_name="escrow_root")
    expected_case_id = _text(payload.get("expected_case_id"), field_name="expected_case_id")
    limits = EscrowLimitsV1.from_dict(
        _worker_payload_mapping(payload.get("limits"), field_name="limits")
    )
    long_range = LongRangeReplayManifestV1.from_dict(
        _worker_payload_mapping(
            payload.get("long_range_manifest"),
            field_name="long_range_manifest",
        )
    )
    escrow = ArtifactEscrowManifestV1.from_dict(
        _worker_payload_mapping(payload.get("escrow_manifest"), field_name="escrow_manifest")
    )
    if long_range.case_id != expected_case_id or escrow.case_id != expected_case_id:
        raise ArtifactEscrowError("offline runner tenant/case scope mismatch")
    escrow.verify_against(long_range)

    try:
        socket.getaddrinfo("network-probe.invalid", 443)
    except PermissionError:
        network_probe = "DENIED"
    else:
        raise ArtifactEscrowError("offline network guard is not active")

    backend = FileSystemEscrowBackendV1(root, create=False)
    for binding in escrow.bindings:
        data = backend.read(binding.blob, limits=limits)
        if binding.kind is EscrowArtifactKind.ZIP:
            validate_zip_bytes(data, limits=limits)

    return {
        "result": "PASS",
        "case_id": expected_case_id,
        "long_range_manifest_identity": str(long_range.manifest_identity),
        "escrow_manifest_identity": str(escrow.escrow_manifest_identity),
        "verified_blob_count": len(escrow.bindings),
        "network_probe": network_probe,
    }


@dataclass(frozen=True, slots=True)
class OfflineReplayReceiptV1:
    case_id: str
    long_range_manifest_identity: ContentAddress
    escrow_manifest_identity: ContentAddress
    task_digest: str
    output_digest: str
    verified_blob_count: int
    network_mode: str
    network_enforcement: str
    process_enforcement: str
    native_ffi_enforcement: str
    filesystem_enforcement: str
    kernel_sandbox: bool
    receipt_identity: ContentAddress
    schema: str = OFFLINE_REPLAY_RECEIPT_SCHEMA_V1

    @classmethod
    def build(
        cls,
        *,
        case_id: str,
        long_range_manifest_identity: ContentAddress,
        escrow_manifest_identity: ContentAddress,
        task_digest: str,
        output_digest: str,
        verified_blob_count: int,
        network_enforcement: str,
        process_enforcement: str,
        native_ffi_enforcement: str,
        filesystem_enforcement: str,
        kernel_sandbox: bool,
    ) -> OfflineReplayReceiptV1:
        body = {
            "schema": OFFLINE_REPLAY_RECEIPT_SCHEMA_V1,
            "case_id": case_id,
            "long_range_manifest_identity": long_range_manifest_identity.canonical_dict(),
            "escrow_manifest_identity": escrow_manifest_identity.canonical_dict(),
            "task_digest": task_digest,
            "output_digest": output_digest,
            "verified_blob_count": verified_blob_count,
            "network_mode": "OFF",
            "network_enforcement": network_enforcement,
            "process_enforcement": process_enforcement,
            "native_ffi_enforcement": native_ffi_enforcement,
            "filesystem_enforcement": filesystem_enforcement,
            "kernel_sandbox": kernel_sandbox,
        }
        return cls(
            case_id=case_id,
            long_range_manifest_identity=long_range_manifest_identity,
            escrow_manifest_identity=escrow_manifest_identity,
            task_digest=task_digest,
            output_digest=output_digest,
            verified_blob_count=verified_blob_count,
            network_mode="OFF",
            network_enforcement=network_enforcement,
            process_enforcement=process_enforcement,
            native_ffi_enforcement=native_ffi_enforcement,
            filesystem_enforcement=filesystem_enforcement,
            kernel_sandbox=kernel_sandbox,
            receipt_identity=ContentAddress.for_value(body),
        )

    def __post_init__(self) -> None:
        if self.schema != OFFLINE_REPLAY_RECEIPT_SCHEMA_V1:
            raise ArtifactEscrowError(f"unsupported offline receipt schema: {self.schema}")
        if self.network_mode != "OFF":
            raise ArtifactEscrowError("LRD offline receipt must declare network OFF")
        if self.network_enforcement != "python-runtime-guard":
            raise ArtifactEscrowError("required offline network enforcement was not observed")
        if self.process_enforcement != "python-audit-hook-deny":
            raise ArtifactEscrowError("offline runner must deny process spawn")
        if self.native_ffi_enforcement != "python-audit-hook-deny":
            raise ArtifactEscrowError("offline runner must deny native FFI")
        if not self.filesystem_enforcement.startswith("python-audit-hook-read-roots"):
            raise ArtifactEscrowError("offline runner filesystem boundary was not observed")
        if self.kernel_sandbox:
            raise ArtifactEscrowError(
                "LRD-01C receipt cannot claim a kernel sandbox not provided by this runner"
            )
        if self.verified_blob_count < 0:
            raise ArtifactEscrowError("verified_blob_count cannot be negative")
        if ContentAddress.for_value(self.body_dict()) != self.receipt_identity:
            raise ArtifactEscrowError("offline replay receipt identity mismatch")

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> OfflineReplayReceiptV1:
        raw = _canonical_copy(value, field_name="offline replay receipt")
        _strict_keys(raw, expected=_RECEIPT_KEYS, field_name="offline replay receipt")
        count = raw.get("verified_blob_count")
        kernel = raw.get("kernel_sandbox")
        if not isinstance(count, int) or isinstance(count, bool):
            raise ArtifactEscrowError("verified_blob_count must be an integer")
        if not isinstance(kernel, bool):
            raise ArtifactEscrowError("kernel_sandbox must be boolean")
        return cls(
            schema=_text(raw.get("schema"), field_name="receipt schema"),
            case_id=_text(raw.get("case_id"), field_name="receipt case_id"),
            long_range_manifest_identity=_address(
                raw.get("long_range_manifest_identity"),
                field_name="receipt LRD identity",
            ),
            escrow_manifest_identity=_address(
                raw.get("escrow_manifest_identity"),
                field_name="receipt escrow identity",
            ),
            task_digest=_text(raw.get("task_digest"), field_name="task_digest"),
            output_digest=_text(raw.get("output_digest"), field_name="output_digest"),
            verified_blob_count=count,
            network_mode=_text(raw.get("network_mode"), field_name="network_mode"),
            network_enforcement=_text(
                raw.get("network_enforcement"),
                field_name="network_enforcement",
            ),
            process_enforcement=_text(
                raw.get("process_enforcement"),
                field_name="process_enforcement",
            ),
            native_ffi_enforcement=_text(
                raw.get("native_ffi_enforcement"),
                field_name="native_ffi_enforcement",
            ),
            filesystem_enforcement=_text(
                raw.get("filesystem_enforcement"),
                field_name="filesystem_enforcement",
            ),
            kernel_sandbox=kernel,
            receipt_identity=_address(
                raw.get("receipt_identity"),
                field_name="receipt_identity",
            ),
        )

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "long_range_manifest_identity": self.long_range_manifest_identity.canonical_dict(),
            "escrow_manifest_identity": self.escrow_manifest_identity.canonical_dict(),
            "task_digest": self.task_digest,
            "output_digest": self.output_digest,
            "verified_blob_count": self.verified_blob_count,
            "network_mode": self.network_mode,
            "network_enforcement": self.network_enforcement,
            "process_enforcement": self.process_enforcement,
            "native_ffi_enforcement": self.native_ffi_enforcement,
            "filesystem_enforcement": self.filesystem_enforcement,
            "kernel_sandbox": self.kernel_sandbox,
        }

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "receipt_identity": self.receipt_identity.canonical_dict()}


class OfflineReplayRunnerV1:
    """Fixed-entrypoint, read-only LRD material verifier with declared network OFF."""

    def __init__(self, *, limits: EscrowLimitsV1 | None = None) -> None:
        self.limits = limits or EscrowLimitsV1()

    def verify(
        self,
        *,
        expected_case_id: str,
        long_range_manifest: LongRangeReplayManifestV1,
        escrow_manifest: ArtifactEscrowManifestV1,
        escrow_root: str | Path,
    ) -> OfflineReplayReceiptV1:
        normalized_case = _text(expected_case_id, field_name="expected_case_id")
        long_range_manifest.verify()
        escrow_manifest.verify_against(long_range_manifest)
        if long_range_manifest.case_id != normalized_case:
            raise ArtifactEscrowError("offline runner tenant/case scope mismatch")

        root = _secure_root(escrow_root, field_name="offline runner escrow root")
        if not root.is_dir():
            raise ArtifactEscrowError("offline runner escrow root must be a directory")

        policy = IsolationPolicy(
            timeout_seconds=self.limits.runner_timeout_seconds,
            memory_bytes=self.limits.runner_memory_bytes,
            cpu_seconds=self.limits.runner_cpu_seconds,
            network_allowed=False,
            allowed_entrypoints=(OFFLINE_REPLAY_ENTRYPOINT_V1,),
            allowed_read_roots=(str(root),),
            process_spawn_allowed=False,
            native_ffi_allowed=False,
            workspace_write_only=True,
        )
        task = IsolatedTask(
            module="core.artifact_escrow_v1",
            function="offline_verify_escrow_worker",
            payload={
                "expected_case_id": normalized_case,
                "escrow_root": str(root),
                "limits": self.limits.canonical_dict(),
                "long_range_manifest": long_range_manifest.canonical_dict(),
                "escrow_manifest": escrow_manifest.canonical_dict(),
            },
        )
        try:
            result = ProcessIsolationExecutor(policy).run(task)
        except IsolatedExecutionError as exc:
            raise ArtifactEscrowError(f"offline runner failed: {exc}") from exc
        if result.output.get("result") != "PASS":
            raise ArtifactEscrowError("offline worker did not return PASS")
        if result.output.get("network_probe") != "DENIED":
            raise ArtifactEscrowError("offline worker network probe was not denied")
        if result.output.get("case_id") != normalized_case:
            raise ArtifactEscrowError("offline worker returned wrong case")
        if result.output.get("verified_blob_count") != len(escrow_manifest.bindings):
            raise ArtifactEscrowError("offline worker verified blob count mismatch")

        return OfflineReplayReceiptV1.build(
            case_id=normalized_case,
            long_range_manifest_identity=long_range_manifest.manifest_identity,
            escrow_manifest_identity=escrow_manifest.escrow_manifest_identity,
            task_digest=result.task_digest,
            output_digest=result.output_digest,
            verified_blob_count=len(escrow_manifest.bindings),
            network_enforcement=result.controls.network_control,
            process_enforcement=result.controls.process_control,
            native_ffi_enforcement=result.controls.native_ffi_control,
            filesystem_enforcement=result.controls.filesystem_control,
            kernel_sandbox=result.controls.kernel_sandbox,
        )
