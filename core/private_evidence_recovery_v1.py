"""Offline non-cloud recovery capsule for CASE-OPS private evidence.

CASE-OPS-03 protects recovery completeness and key custody without introducing
another case-history authority. Capsules contain ciphertext/provenance plus a
passphrase-wrapped keyset. Plaintext evidence and raw key files are never
persisted by this module.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from core.enterprise.contracts import AuthorizationContext, EnterpriseContractError, Permission
from core.local_case_store import PrivacyViolation, validate_untrusted_path
from core.private_evidence_derivation_v1 import load_derivation
from core.private_evidence_rotation_v1 import SCHEMA_REENCRYPT_RECEIPT
from core.private_evidence_v1 import (
    ALGORITHM,
    SCHEMA_MANIFEST,
    SCHEMA_RECEIPT,
    SCHEMA_SOURCE_INDEX,
    ImportedEvidence,
    PrivateEvidenceError,
    PrivateEvidenceManifestV1,
    PrivateEvidenceStore,
    canonical_json,
    content_id,
    digest_hex,
    digest_object,
)

SCHEMA_RECOVERY_SNAPSHOT = "lukart.private-evidence-recovery-snapshot.v1"
SCHEMA_RECOVERY_KEYSET = "lukart.private-evidence-recovery-keyset.v1"
SCHEMA_RECOVERY_KEY_ENVELOPE = "lukart.private-evidence-recovery-key-envelope.v1"
SCHEMA_RECOVERY_CAPSULE = "lukart.private-evidence-recovery-capsule.v1"
RECOVERY_SUFFIX = ".mvros-recovery"
RECOVERY_ALGORITHM = "AES-256-GCM"
RECOVERY_KDF = "SCRYPT"
RECOVERY_KDF_N = 1 << 15
RECOVERY_KDF_R = 8
RECOVERY_KDF_P = 1
RECOVERY_SALT_BYTES = 16
RECOVERY_NONCE_BYTES = 12
RECOVERY_KEY_BYTES = 32
MIN_PASSPHRASE_BYTES = 12
MAX_RECOVERY_FILES = 50_000
MAX_RECOVERY_FILE_BYTES = 64 * 1024 * 1024
MAX_RECOVERY_TOTAL_BYTES = 16 * 1024 * 1024 * 1024
_ALLOWED_CATEGORIES = frozenset(
    {"objects", "manifests", "receipts", "source-index", "derivations"}
)
_MANIFEST_FIELDS = frozenset(PrivateEvidenceManifestV1.__dataclass_fields__)
_IMPORT_RECEIPT_FIELDS = frozenset(
    {
        "schema",
        "evidence_id",
        "manifest_digest",
        "case_scope_digest",
        "source_ref_digest",
        "imported_at",
        "operation",
    }
)
_REENCRYPT_RECEIPT_FIELDS = frozenset(
    {
        "schema",
        "operation",
        "evidence_id",
        "manifest_digest",
        "previous_manifest_digest",
        "case_scope_digest",
        "source_ref_digest",
        "target_key_id",
        "target_key_version",
        "imported_at",
    }
)
_SOURCE_INDEX_FIELDS = frozenset(
    {"schema", "evidence_id", "manifest_digest", "receipt_digest"}
)


class PrivateEvidenceRecoveryError(RuntimeError):
    """Fail-closed error at the CASE-OPS-03 recovery boundary."""


class _KeyProvider(Protocol):
    def get_key(self, key_id: str, key_version: int) -> bytes: ...


@dataclass(frozen=True, slots=True)
class RecoveryFileV1:
    path: str
    size_bytes: int
    file_digest: str

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RecoveryCapsuleResultV1:
    capsule_path: Path
    capsule_id: str
    snapshot_digest: str
    key_envelope_digest: str
    file_count: int
    total_bytes: int


@dataclass(frozen=True, slots=True)
class VerifiedRecoveryCapsuleV1:
    capsule_path: Path
    capsule_id: str
    snapshot_digest: str
    key_envelope_digest: str
    file_count: int
    total_bytes: int
    active_key_id: str
    active_key_version: int
    key_provider: RecoveredEvidenceKeyProvider


@dataclass(frozen=True, slots=True)
class RestoredPrivateEvidenceV1:
    store: PrivateEvidenceStore
    key_provider: RecoveredEvidenceKeyProvider
    capsule_id: str
    snapshot_digest: str


class RecoveredEvidenceKeyProvider:
    """In-memory provider reconstructed from a passphrase-authenticated capsule."""

    def __init__(self, keys: dict[tuple[str, int], bytes]) -> None:
        normalized: dict[tuple[str, int], bytes] = {}
        for (key_id, key_version), key in keys.items():
            identifier = key_id.strip()
            if not identifier or key_version < 1:
                raise PrivateEvidenceRecoveryError("recovered key identity is invalid")
            if not isinstance(key, bytes) or len(key) != RECOVERY_KEY_BYTES:
                raise PrivateEvidenceRecoveryError("recovered AES key has invalid length")
            normalized[(identifier, key_version)] = bytes(key)
        if not normalized:
            raise PrivateEvidenceRecoveryError("recovery keyset cannot be empty")
        self._keys = normalized

    @property
    def identities(self) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(self._keys))

    def get_key(self, key_id: str, key_version: int) -> bytes:
        try:
            return self._keys[(key_id.strip(), key_version)]
        except KeyError as exc:
            raise PrivateEvidenceError("requested recovery key identity is unavailable") from exc


def _require_permission(
    authorization: AuthorizationContext,
    permission: Permission,
    *,
    tenant_id: str,
    case_id: str,
) -> None:
    try:
        authorization.require(
            permission,
            tenant_id=tenant_id,
            case_id=case_id,
            strict_scope=True,
        )
    except EnterpriseContractError as exc:
        raise PrivateEvidenceRecoveryError(str(exc)) from exc


def _safe_absolute(path: Path, *, label: str) -> Path:
    try:
        unresolved = validate_untrusted_path(path, label=label)
    except PrivacyViolation as exc:
        raise PrivateEvidenceRecoveryError(str(exc)) from exc
    return unresolved.resolve()


def _outside_repo(path: Path, repo_root: Path | None, *, label: str) -> None:
    if repo_root is None:
        return
    root = _safe_absolute(repo_root, label="repository root")
    candidate = _safe_absolute(path, label=label)
    if candidate == root or root in candidate.parents:
        raise PrivateEvidenceRecoveryError(f"{label} must be outside the public repository tree")


def _read_mapping(path: Path, *, label: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise PrivateEvidenceRecoveryError(f"{label} missing, non-regular, or symlinked")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrivateEvidenceRecoveryError(f"{label} is invalid JSON") from exc
    if not isinstance(value, dict):
        raise PrivateEvidenceRecoveryError(f"{label} must be a JSON mapping")
    return value


def _write_json(path: Path, value: object) -> None:
    payload = canonical_json(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise PrivateEvidenceRecoveryError("recovery capsule path contains a symlink")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _validate_digest(value: object, *, label: str) -> str:
    if not isinstance(value, str):
        raise PrivateEvidenceRecoveryError(f"{label} must be a sha256 content identifier")
    try:
        digest_hex(value)
    except PrivateEvidenceError as exc:
        raise PrivateEvidenceRecoveryError(f"{label} must be a sha256 content identifier") from exc
    return value


def _validate_positive_int(value: object, *, label: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise PrivateEvidenceRecoveryError(f"{label} must be an integer >= {minimum}")
    return value


def _object_identity_from_path(root: Path, path: Path) -> tuple[str, str]:
    relative = path.relative_to(root)
    if len(relative.parts) != 3:
        raise PrivateEvidenceRecoveryError("private evidence object layout is invalid")
    category, shard, filename = relative.parts
    if category not in _ALLOWED_CATEGORIES:
        raise PrivateEvidenceRecoveryError("private evidence category is unsupported")
    if len(shard) != 2 or not filename.endswith(".json"):
        raise PrivateEvidenceRecoveryError("private evidence digest path is invalid")
    stem = filename[:-5]
    digest = f"sha256:{stem}"
    try:
        digest_hex(digest)
    except PrivateEvidenceError as exc:
        raise PrivateEvidenceRecoveryError("private evidence digest path is invalid") from exc
    if not stem.startswith(shard):
        raise PrivateEvidenceRecoveryError("private evidence digest shard mismatch")
    return category, digest


def _inventory(root: Path) -> tuple[RecoveryFileV1, ...]:
    if root.is_symlink() or not root.is_dir():
        raise PrivateEvidenceRecoveryError("private evidence root is missing or symlinked")
    files: list[RecoveryFileV1] = []
    total = 0
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise PrivateEvidenceRecoveryError("private evidence tree contains a symlink")
        if path.is_dir():
            continue
        if not path.is_file():
            raise PrivateEvidenceRecoveryError("private evidence tree contains a non-regular entry")
        _object_identity_from_path(root, path)
        size = path.stat().st_size
        if size < 1 or size > MAX_RECOVERY_FILE_BYTES:
            raise PrivateEvidenceRecoveryError("private evidence file size budget exceeded")
        total += size
        if total > MAX_RECOVERY_TOTAL_BYTES:
            raise PrivateEvidenceRecoveryError("private evidence total size budget exceeded")
        files.append(
            RecoveryFileV1(
                path=path.relative_to(root).as_posix(),
                size_bytes=size,
                file_digest=content_id(path.read_bytes()),
            )
        )
        if len(files) > MAX_RECOVERY_FILES:
            raise PrivateEvidenceRecoveryError("private evidence file count budget exceeded")
    if not files:
        raise PrivateEvidenceRecoveryError("private evidence store is empty")
    return tuple(files)


def _snapshot(
    root: Path,
    *,
    case_scope_digest: str,
) -> tuple[dict[str, object], str]:
    files = _inventory(root)
    snapshot = {
        "schema": SCHEMA_RECOVERY_SNAPSHOT,
        "case_scope_digest": case_scope_digest,
        "file_count": len(files),
        "total_bytes": sum(item.size_bytes for item in files),
        "files": [item.canonical_dict() for item in files],
    }
    return snapshot, digest_object(snapshot)


def _parse_snapshot(
    snapshot: dict[str, object],
    *,
    expected_case_scope_digest: str,
) -> tuple[RecoveryFileV1, ...]:
    expected_fields = {"schema", "case_scope_digest", "file_count", "total_bytes", "files"}
    if set(snapshot) != expected_fields:
        raise PrivateEvidenceRecoveryError("unknown or missing recovery snapshot fields")
    if snapshot.get("schema") != SCHEMA_RECOVERY_SNAPSHOT:
        raise PrivateEvidenceRecoveryError("unsupported recovery snapshot schema")
    if snapshot.get("case_scope_digest") != expected_case_scope_digest:
        raise PrivateEvidenceRecoveryError("recovery snapshot case scope mismatch")
    raw_files = snapshot.get("files")
    if not isinstance(raw_files, list):
        raise PrivateEvidenceRecoveryError("recovery snapshot files must be a list")
    file_count = _validate_positive_int(
        snapshot.get("file_count"), label="recovery snapshot file_count"
    )
    total_bytes = _validate_positive_int(
        snapshot.get("total_bytes"), label="recovery snapshot total_bytes"
    )
    if file_count != len(raw_files) or file_count > MAX_RECOVERY_FILES:
        raise PrivateEvidenceRecoveryError("recovery snapshot file count mismatch")
    parsed: list[RecoveryFileV1] = []
    seen: set[str] = set()
    running_total = 0
    for item in raw_files:
        if not isinstance(item, dict) or set(item) != {"path", "size_bytes", "file_digest"}:
            raise PrivateEvidenceRecoveryError("recovery snapshot file entry is invalid")
        path = item.get("path")
        if not isinstance(path, str) or not path or "\\" in path:
            raise PrivateEvidenceRecoveryError("recovery snapshot path is invalid")
        pure = Path(path)
        if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
            raise PrivateEvidenceRecoveryError("recovery snapshot path traversal detected")
        if path in seen:
            raise PrivateEvidenceRecoveryError("duplicate recovery snapshot path")
        seen.add(path)
        size = _validate_positive_int(item.get("size_bytes"), label="snapshot file size")
        if size > MAX_RECOVERY_FILE_BYTES:
            raise PrivateEvidenceRecoveryError("snapshot file size budget exceeded")
        digest = _validate_digest(item.get("file_digest"), label="snapshot file digest")
        running_total += size
        if running_total > MAX_RECOVERY_TOTAL_BYTES:
            raise PrivateEvidenceRecoveryError("snapshot total size budget exceeded")
        parsed.append(RecoveryFileV1(path=path, size_bytes=size, file_digest=digest))
    if total_bytes != running_total:
        raise PrivateEvidenceRecoveryError("recovery snapshot total size mismatch")
    if [item.path for item in parsed] != sorted(item.path for item in parsed):
        raise PrivateEvidenceRecoveryError("recovery snapshot file order is non-canonical")
    return tuple(parsed)


def _verify_inventory_against_snapshot(
    evidence_root: Path,
    files: tuple[RecoveryFileV1, ...],
) -> None:
    actual = _inventory(evidence_root)
    if actual != files:
        raise PrivateEvidenceRecoveryError(
            "recovery snapshot does not match encrypted evidence tree"
        )


def _manifest_from_path(
    path: Path,
    expected_digest: str,
    case_scope_digest: str,
) -> dict[str, object]:
    manifest = _read_mapping(path, label="evidence manifest")
    if set(manifest) != _MANIFEST_FIELDS:
        raise PrivateEvidenceRecoveryError("unknown or missing evidence manifest fields")
    if manifest.get("schema") != SCHEMA_MANIFEST:
        raise PrivateEvidenceRecoveryError("unsupported evidence manifest schema")
    if digest_object(manifest) != expected_digest:
        raise PrivateEvidenceRecoveryError("evidence manifest digest mismatch")
    if manifest.get("case_scope_digest") != case_scope_digest:
        raise PrivateEvidenceRecoveryError("evidence manifest case scope mismatch")
    _validate_digest(manifest.get("evidence_id"), label="manifest evidence_id")
    _validate_digest(manifest.get("envelope_digest"), label="manifest envelope_digest")
    _validate_digest(manifest.get("source_ref_digest"), label="manifest source_ref_digest")
    if manifest.get("algorithm") != ALGORITHM:
        raise PrivateEvidenceRecoveryError("unsupported evidence manifest algorithm")
    key_id = manifest.get("key_id")
    if not isinstance(key_id, str) or not key_id.strip():
        raise PrivateEvidenceRecoveryError("manifest key id is invalid")
    _validate_positive_int(manifest.get("key_version"), label="manifest key_version")
    return manifest


def _receipt_binding(
    path: Path,
    expected_digest: str,
    case_scope_digest: str,
) -> tuple[str, str]:
    receipt = _read_mapping(path, label="evidence receipt")
    if digest_object(receipt) != expected_digest:
        raise PrivateEvidenceRecoveryError("evidence receipt digest mismatch")
    schema = receipt.get("schema")
    if schema == SCHEMA_RECEIPT:
        if set(receipt) != _IMPORT_RECEIPT_FIELDS:
            raise PrivateEvidenceRecoveryError("unknown or missing import receipt fields")
        if receipt.get("operation") != "IMPORT_ACCEPTED":
            raise PrivateEvidenceRecoveryError("unsupported import receipt operation")
    elif schema == SCHEMA_REENCRYPT_RECEIPT:
        if set(receipt) != _REENCRYPT_RECEIPT_FIELDS:
            raise PrivateEvidenceRecoveryError("unknown or missing reencryption receipt fields")
        if receipt.get("operation") != "REENCRYPTED":
            raise PrivateEvidenceRecoveryError("unsupported reencryption receipt operation")
        _validate_digest(
            receipt.get("previous_manifest_digest"),
            label="reencryption predecessor manifest digest",
        )
    else:
        raise PrivateEvidenceRecoveryError("unsupported evidence receipt schema")
    if receipt.get("case_scope_digest") != case_scope_digest:
        raise PrivateEvidenceRecoveryError("evidence receipt case scope mismatch")
    evidence_id = _validate_digest(receipt.get("evidence_id"), label="receipt evidence_id")
    manifest_digest = _validate_digest(
        receipt.get("manifest_digest"), label="receipt manifest_digest"
    )
    _validate_digest(receipt.get("source_ref_digest"), label="receipt source_ref_digest")
    return evidence_id, manifest_digest


def _verify_source_indexes(
    store: PrivateEvidenceStore,
    indexes: list[tuple[str, Path]],
) -> None:
    for source_ref_digest, path in indexes:
        value = _read_mapping(path, label="source index")
        if set(value) != _SOURCE_INDEX_FIELDS or value.get("schema") != SCHEMA_SOURCE_INDEX:
            raise PrivateEvidenceRecoveryError("unknown or invalid source-index fields")
        evidence_id = _validate_digest(value.get("evidence_id"), label="source-index evidence_id")
        manifest_digest = _validate_digest(
            value.get("manifest_digest"), label="source-index manifest_digest"
        )
        receipt_digest = _validate_digest(
            value.get("receipt_digest"), label="source-index receipt_digest"
        )
        imported = store._load_imported(
            evidence_id=evidence_id,
            manifest_digest=manifest_digest,
            receipt_digest=receipt_digest,
        )
        store.verify(imported)
        manifest = _read_mapping(imported.manifest_path, label="source-index manifest")
        if manifest.get("source_ref_digest") != source_ref_digest:
            raise PrivateEvidenceRecoveryError("source-index path does not bind source identity")


def _verify_store(store: PrivateEvidenceStore) -> tuple[tuple[str, int], ...]:
    """Verify the whole immutable private-evidence graph and return required key identities."""
    inventory = _inventory(store.root)
    manifests: dict[str, tuple[Path, dict[str, object]]] = {}
    receipts: dict[str, tuple[Path, str, str]] = {}
    object_ids: set[str] = set()
    derivation_ids: list[str] = []
    indexes: list[tuple[str, Path]] = []

    for item in inventory:
        path = store.root / item.path
        category, logical_digest = _object_identity_from_path(store.root, path)
        if category == "manifests":
            manifests[logical_digest] = (
                path,
                _manifest_from_path(path, logical_digest, store.case_scope_digest),
            )
        elif category == "receipts":
            evidence_id, manifest_digest = _receipt_binding(
                path, logical_digest, store.case_scope_digest
            )
            receipts[logical_digest] = (path, evidence_id, manifest_digest)
        elif category == "objects":
            payload = _read_mapping(path, label="encrypted envelope")
            if digest_object(payload) != logical_digest:
                raise PrivateEvidenceRecoveryError("encrypted envelope digest mismatch")
            object_ids.add(logical_digest)
        elif category == "derivations":
            derivation_ids.append(logical_digest)
        elif category == "source-index":
            indexes.append((logical_digest, path))

    if not manifests or not receipts or not object_ids:
        raise PrivateEvidenceRecoveryError("private evidence graph is incomplete")

    referenced_objects: set[str] = set()
    used_receipts: set[str] = set()
    required_keys: set[tuple[str, int]] = set()

    for manifest_digest in sorted(manifests):
        manifest_path, manifest = manifests[manifest_digest]
        evidence_id = str(manifest["evidence_id"])
        envelope_digest = str(manifest["envelope_digest"])
        referenced_objects.add(envelope_digest)
        matching = [
            receipt_digest
            for receipt_digest, (
                _,
                receipt_evidence_id,
                receipt_manifest_digest,
            ) in receipts.items()
            if receipt_evidence_id == evidence_id and receipt_manifest_digest == manifest_digest
        ]
        if not matching:
            raise PrivateEvidenceRecoveryError("evidence manifest has no bound receipt")
        for receipt_digest in matching:
            imported = ImportedEvidence(
                evidence_id=evidence_id,
                manifest_digest=manifest_digest,
                receipt_digest=receipt_digest,
                manifest_path=manifest_path,
                receipt_path=receipts[receipt_digest][0],
                envelope_path=store._path("objects", envelope_digest),
            )
            try:
                store.verify(imported)
            except PrivateEvidenceError as exc:
                raise PrivateEvidenceRecoveryError("private evidence verification failed") from exc
            used_receipts.add(receipt_digest)
        key_id = str(manifest["key_id"]).strip()
        key_version = int(manifest["key_version"])
        required_keys.add((key_id, key_version))

    if object_ids != referenced_objects:
        raise PrivateEvidenceRecoveryError(
            "encrypted object set does not exactly match manifest references"
        )
    if set(receipts) != used_receipts:
        raise PrivateEvidenceRecoveryError("orphan or unbound evidence receipt detected")

    try:
        _verify_source_indexes(store, indexes)
        for derivation_digest in sorted(derivation_ids):
            load_derivation(store, derivation_digest)
    except PrivateEvidenceError as exc:
        raise PrivateEvidenceRecoveryError(
            "private evidence provenance verification failed"
        ) from exc

    active_identity = (store.key_id, store.key_version)
    if active_identity not in required_keys:
        raise PrivateEvidenceRecoveryError("active evidence key identity is not used by the store")
    return tuple(sorted(required_keys))


def _resolve_keys(
    provider: _KeyProvider,
    identities: tuple[tuple[str, int], ...],
) -> dict[tuple[str, int], bytes]:
    keys: dict[tuple[str, int], bytes] = {}
    for key_id, key_version in identities:
        try:
            key = provider.get_key(key_id, key_version)
        except Exception as exc:
            raise PrivateEvidenceRecoveryError(
                f"required evidence key is unavailable: {key_id}@{key_version}"
            ) from exc
        if not isinstance(key, bytes) or len(key) != RECOVERY_KEY_BYTES:
            raise PrivateEvidenceRecoveryError(
                "required evidence key must contain exactly 32 bytes"
            )
        keys[(key_id, key_version)] = bytes(key)
    return keys


def _passphrase_bytes(passphrase: str) -> bytes:
    if not isinstance(passphrase, str):
        raise PrivateEvidenceRecoveryError("recovery passphrase must be text")
    payload = passphrase.encode("utf-8")
    if len(payload) < MIN_PASSPHRASE_BYTES:
        raise PrivateEvidenceRecoveryError(
            f"recovery passphrase must contain at least {MIN_PASSPHRASE_BYTES} UTF-8 bytes"
        )
    return payload


def _derive_wrap_key(passphrase: str, salt: bytes) -> bytes:
    try:
        return Scrypt(
            salt=salt,
            length=RECOVERY_KEY_BYTES,
            n=RECOVERY_KDF_N,
            r=RECOVERY_KDF_R,
            p=RECOVERY_KDF_P,
        ).derive(_passphrase_bytes(passphrase))
    except PrivateEvidenceRecoveryError:
        raise
    except Exception as exc:
        raise PrivateEvidenceRecoveryError("recovery key derivation failed") from exc


def _key_envelope(
    *,
    passphrase: str,
    snapshot_digest: str,
    case_scope_digest: str,
    active_key_id: str,
    active_key_version: int,
    keys: dict[tuple[str, int], bytes],
) -> tuple[dict[str, object], str]:
    keyset = {
        "schema": SCHEMA_RECOVERY_KEYSET,
        "case_scope_digest": case_scope_digest,
        "active_key_id": active_key_id,
        "active_key_version": active_key_version,
        "keys": [
            {
                "key_id": key_id,
                "key_version": key_version,
                "key_b64": base64.b64encode(key).decode("ascii"),
            }
            for (key_id, key_version), key in sorted(keys.items())
        ],
    }
    salt = secrets.token_bytes(RECOVERY_SALT_BYTES)
    nonce = secrets.token_bytes(RECOVERY_NONCE_BYTES)
    aad = {
        "schema": SCHEMA_RECOVERY_KEY_ENVELOPE,
        "algorithm": RECOVERY_ALGORITHM,
        "kdf": RECOVERY_KDF,
        "kdf_n": RECOVERY_KDF_N,
        "kdf_r": RECOVERY_KDF_R,
        "kdf_p": RECOVERY_KDF_P,
        "case_scope_digest": case_scope_digest,
        "snapshot_digest": snapshot_digest,
        "key_count": len(keys),
    }
    wrap_key = _derive_wrap_key(passphrase, salt)
    ciphertext = AESGCM(wrap_key).encrypt(nonce, canonical_json(keyset), canonical_json(aad))
    envelope = {
        "schema": SCHEMA_RECOVERY_KEY_ENVELOPE,
        "algorithm": RECOVERY_ALGORITHM,
        "kdf": RECOVERY_KDF,
        "kdf_n": RECOVERY_KDF_N,
        "kdf_r": RECOVERY_KDF_R,
        "kdf_p": RECOVERY_KDF_P,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "aad": aad,
        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
    }
    return envelope, digest_object(envelope)


def _recover_keys(
    envelope: dict[str, object],
    *,
    passphrase: str,
    expected_snapshot_digest: str,
    expected_case_scope_digest: str,
) -> tuple[RecoveredEvidenceKeyProvider, str, int]:
    fields = {
        "schema",
        "algorithm",
        "kdf",
        "kdf_n",
        "kdf_r",
        "kdf_p",
        "salt_b64",
        "nonce_b64",
        "aad",
        "ciphertext_b64",
    }
    if set(envelope) != fields:
        raise PrivateEvidenceRecoveryError("unknown or missing recovery key-envelope fields")
    fixed = (
        envelope.get("schema") == SCHEMA_RECOVERY_KEY_ENVELOPE
        and envelope.get("algorithm") == RECOVERY_ALGORITHM
        and envelope.get("kdf") == RECOVERY_KDF
        and envelope.get("kdf_n") == RECOVERY_KDF_N
        and envelope.get("kdf_r") == RECOVERY_KDF_R
        and envelope.get("kdf_p") == RECOVERY_KDF_P
    )
    if not fixed:
        raise PrivateEvidenceRecoveryError("unsupported recovery key-envelope profile")
    aad = envelope.get("aad")
    if not isinstance(aad, dict):
        raise PrivateEvidenceRecoveryError("recovery key-envelope AAD is missing")
    expected_aad_fields = {
        "schema",
        "algorithm",
        "kdf",
        "kdf_n",
        "kdf_r",
        "kdf_p",
        "case_scope_digest",
        "snapshot_digest",
        "key_count",
    }
    if set(aad) != expected_aad_fields:
        raise PrivateEvidenceRecoveryError("unknown or missing recovery key-envelope AAD fields")
    if (
        aad.get("schema") != SCHEMA_RECOVERY_KEY_ENVELOPE
        or aad.get("algorithm") != RECOVERY_ALGORITHM
        or aad.get("kdf") != RECOVERY_KDF
        or aad.get("kdf_n") != RECOVERY_KDF_N
        or aad.get("kdf_r") != RECOVERY_KDF_R
        or aad.get("kdf_p") != RECOVERY_KDF_P
        or aad.get("case_scope_digest") != expected_case_scope_digest
        or aad.get("snapshot_digest") != expected_snapshot_digest
    ):
        raise PrivateEvidenceRecoveryError("recovery key-envelope AAD binding mismatch")
    key_count = _validate_positive_int(aad.get("key_count"), label="recovery key_count")
    try:
        salt = base64.b64decode(str(envelope["salt_b64"]), validate=True)
        nonce = base64.b64decode(str(envelope["nonce_b64"]), validate=True)
        ciphertext = base64.b64decode(str(envelope["ciphertext_b64"]), validate=True)
    except Exception as exc:
        raise PrivateEvidenceRecoveryError("recovery key-envelope encoding is invalid") from exc
    if len(salt) != RECOVERY_SALT_BYTES or len(nonce) != RECOVERY_NONCE_BYTES:
        raise PrivateEvidenceRecoveryError("recovery key-envelope salt/nonce length is invalid")
    try:
        plaintext = AESGCM(_derive_wrap_key(passphrase, salt)).decrypt(
            nonce, ciphertext, canonical_json(aad)
        )
        keyset = json.loads(plaintext.decode("utf-8"))
    except PrivateEvidenceRecoveryError:
        raise
    except Exception as exc:
        raise PrivateEvidenceRecoveryError(
            "recovery passphrase or key-envelope authentication is invalid"
        ) from exc
    if not isinstance(keyset, dict):
        raise PrivateEvidenceRecoveryError("recovered keyset must be a mapping")
    fields = {
        "schema",
        "case_scope_digest",
        "active_key_id",
        "active_key_version",
        "keys",
    }
    if set(keyset) != fields or keyset.get("schema") != SCHEMA_RECOVERY_KEYSET:
        raise PrivateEvidenceRecoveryError("unknown or unsupported recovery keyset")
    if keyset.get("case_scope_digest") != expected_case_scope_digest:
        raise PrivateEvidenceRecoveryError("recovered keyset case scope mismatch")
    active_key_id = keyset.get("active_key_id")
    if not isinstance(active_key_id, str) or not active_key_id.strip():
        raise PrivateEvidenceRecoveryError("recovered active key id is invalid")
    active_key_version = _validate_positive_int(
        keyset.get("active_key_version"), label="recovered active key version"
    )
    raw_keys = keyset.get("keys")
    if not isinstance(raw_keys, list) or len(raw_keys) != key_count:
        raise PrivateEvidenceRecoveryError("recovered key count mismatch")
    keys: dict[tuple[str, int], bytes] = {}
    previous: tuple[str, int] | None = None
    for item in raw_keys:
        if not isinstance(item, dict) or set(item) != {"key_id", "key_version", "key_b64"}:
            raise PrivateEvidenceRecoveryError("recovered key entry is invalid")
        key_id = item.get("key_id")
        if not isinstance(key_id, str) or not key_id.strip():
            raise PrivateEvidenceRecoveryError("recovered key id is invalid")
        key_version = _validate_positive_int(item.get("key_version"), label="recovered key version")
        identity = (key_id.strip(), key_version)
        if previous is not None and identity <= previous:
            raise PrivateEvidenceRecoveryError("recovered keyset ordering is non-canonical")
        previous = identity
        try:
            key = base64.b64decode(str(item["key_b64"]), validate=True)
        except Exception as exc:
            raise PrivateEvidenceRecoveryError("recovered key encoding is invalid") from exc
        if len(key) != RECOVERY_KEY_BYTES or identity in keys:
            raise PrivateEvidenceRecoveryError("recovered key entry is invalid")
        keys[identity] = key
    provider = RecoveredEvidenceKeyProvider(keys)
    if (active_key_id.strip(), active_key_version) not in provider.identities:
        raise PrivateEvidenceRecoveryError("recovered active key is absent from keyset")
    return provider, active_key_id.strip(), active_key_version


def _capsule_metadata(
    *,
    case_scope_digest: str,
    snapshot_digest: str,
    key_envelope_digest: str,
    file_count: int,
    total_bytes: int,
) -> dict[str, object]:
    return {
        "schema": SCHEMA_RECOVERY_CAPSULE,
        "case_scope_digest": case_scope_digest,
        "snapshot_digest": snapshot_digest,
        "key_envelope_digest": key_envelope_digest,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


def _copy_evidence(source: Path, target: Path) -> None:
    if target.exists():
        raise PrivateEvidenceRecoveryError("recovery copy target already exists")
    try:
        shutil.copytree(source, target, symlinks=False)
    except OSError as exc:
        raise PrivateEvidenceRecoveryError("encrypted evidence copy failed") from exc


def _staging_path(target: Path) -> Path:
    return target.parent / f".{target.name}.tmp-{secrets.token_hex(8)}"


def _require_capsule_suffix(path: Path) -> None:
    if not path.name.endswith(RECOVERY_SUFFIX):
        raise PrivateEvidenceRecoveryError(
            f"recovery capsule path must end with {RECOVERY_SUFFIX}"
        )


def create_recovery_capsule(
    store: PrivateEvidenceStore,
    destination: Path,
    *,
    passphrase: str,
    repo_root: Path | None = None,
) -> RecoveryCapsuleResultV1:
    """Create an authenticated offline recovery capsule without plaintext persistence."""
    _require_permission(
        store.authorization,
        Permission.EVIDENCE_WRITE,
        tenant_id=store.tenant_id,
        case_id=store.case_id,
    )
    _passphrase_bytes(passphrase)
    target = Path(os.path.abspath(destination.expanduser()))
    _require_capsule_suffix(target)
    _outside_repo(target, repo_root, label="recovery capsule")
    if target.exists():
        raise PrivateEvidenceRecoveryError("recovery capsule destination already exists")
    if store.root == target or store.root in target.parents:
        raise PrivateEvidenceRecoveryError("recovery capsule cannot be inside evidence root")
    target.parent.mkdir(parents=True, exist_ok=True)
    _outside_repo(target.parent, repo_root, label="recovery capsule parent")

    required_identities = _verify_store(store)
    keys = _resolve_keys(store.key_provider, required_identities)
    snapshot, snapshot_digest = _snapshot(
        store.root, case_scope_digest=store.case_scope_digest
    )
    envelope, key_envelope_digest = _key_envelope(
        passphrase=passphrase,
        snapshot_digest=snapshot_digest,
        case_scope_digest=store.case_scope_digest,
        active_key_id=store.key_id,
        active_key_version=store.key_version,
        keys=keys,
    )
    file_count = _validate_positive_int(
        snapshot.get("file_count"), label="recovery snapshot file_count"
    )
    total_bytes = _validate_positive_int(
        snapshot.get("total_bytes"), label="recovery snapshot total_bytes"
    )
    capsule = _capsule_metadata(
        case_scope_digest=store.case_scope_digest,
        snapshot_digest=snapshot_digest,
        key_envelope_digest=key_envelope_digest,
        file_count=file_count,
        total_bytes=total_bytes,
    )
    stage = _staging_path(target)
    try:
        stage.mkdir(mode=0o700)
        _copy_evidence(store.root, stage / "evidence")
        copied_snapshot, copied_digest = _snapshot(
            stage / "evidence", case_scope_digest=store.case_scope_digest
        )
        if copied_snapshot != snapshot or copied_digest != snapshot_digest:
            raise PrivateEvidenceRecoveryError("evidence changed while recovery capsule was copied")
        _write_json(stage / "snapshot.json", snapshot)
        _write_json(stage / "key-envelope.json", envelope)
        _write_json(stage / "capsule.json", capsule)
        _verify_capsule_root(
            stage,
            passphrase=passphrase,
            authorization=store.authorization,
            tenant_id=store.tenant_id,
            case_id=store.case_id,
        )
        os.replace(stage, target)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return RecoveryCapsuleResultV1(
        capsule_path=target,
        capsule_id=digest_object(capsule),
        snapshot_digest=snapshot_digest,
        key_envelope_digest=key_envelope_digest,
        file_count=file_count,
        total_bytes=total_bytes,
    )


def _verify_capsule_root(
    root: Path,
    *,
    passphrase: str,
    authorization: AuthorizationContext,
    tenant_id: str,
    case_id: str,
) -> VerifiedRecoveryCapsuleV1:
    _require_permission(
        authorization,
        Permission.EVIDENCE_READ,
        tenant_id=tenant_id,
        case_id=case_id,
    )
    case_scope_digest = digest_object({"tenant_id": tenant_id, "case_id": case_id})
    if root.is_symlink() or not root.is_dir():
        raise PrivateEvidenceRecoveryError("recovery capsule root is missing or symlinked")
    expected_names = {"capsule.json", "snapshot.json", "key-envelope.json", "evidence"}
    actual_names = {item.name for item in root.iterdir()}
    if actual_names != expected_names:
        raise PrivateEvidenceRecoveryError("recovery capsule root contains unexpected entries")
    for item in root.iterdir():
        if item.is_symlink():
            raise PrivateEvidenceRecoveryError("recovery capsule contains a symlink")

    capsule = _read_mapping(root / "capsule.json", label="recovery capsule metadata")
    fields = {
        "schema",
        "case_scope_digest",
        "snapshot_digest",
        "key_envelope_digest",
        "file_count",
        "total_bytes",
        "created_at",
    }
    if set(capsule) != fields or capsule.get("schema") != SCHEMA_RECOVERY_CAPSULE:
        raise PrivateEvidenceRecoveryError("unknown or unsupported recovery capsule metadata")
    if capsule.get("case_scope_digest") != case_scope_digest:
        raise PrivateEvidenceRecoveryError("recovery capsule case scope mismatch")
    created_at = capsule.get("created_at")
    if not isinstance(created_at, str) or not created_at.strip():
        raise PrivateEvidenceRecoveryError("recovery capsule timestamp is invalid")
    snapshot_digest = _validate_digest(
        capsule.get("snapshot_digest"), label="capsule snapshot_digest"
    )
    key_envelope_digest = _validate_digest(
        capsule.get("key_envelope_digest"), label="capsule key_envelope_digest"
    )
    file_count = _validate_positive_int(capsule.get("file_count"), label="capsule file_count")
    total_bytes = _validate_positive_int(capsule.get("total_bytes"), label="capsule total_bytes")

    snapshot = _read_mapping(root / "snapshot.json", label="recovery snapshot")
    if digest_object(snapshot) != snapshot_digest:
        raise PrivateEvidenceRecoveryError("recovery snapshot digest mismatch")
    files = _parse_snapshot(snapshot, expected_case_scope_digest=case_scope_digest)
    if file_count != len(files) or total_bytes != sum(item.size_bytes for item in files):
        raise PrivateEvidenceRecoveryError("recovery capsule summary does not bind snapshot")
    _verify_inventory_against_snapshot(root / "evidence", files)

    key_envelope = _read_mapping(root / "key-envelope.json", label="recovery key envelope")
    if digest_object(key_envelope) != key_envelope_digest:
        raise PrivateEvidenceRecoveryError("recovery key-envelope digest mismatch")
    provider, active_key_id, active_key_version = _recover_keys(
        key_envelope,
        passphrase=passphrase,
        expected_snapshot_digest=snapshot_digest,
        expected_case_scope_digest=case_scope_digest,
    )
    store = PrivateEvidenceStore(
        root / "evidence",
        key_provider=provider,
        authorization=authorization,
        tenant_id=tenant_id,
        case_id=case_id,
        key_id=active_key_id,
        key_version=active_key_version,
    )
    required_identities = _verify_store(store)
    if provider.identities != required_identities:
        raise PrivateEvidenceRecoveryError(
            "recovery keyset does not exactly match keys required by evidence store"
        )
    return VerifiedRecoveryCapsuleV1(
        capsule_path=root,
        capsule_id=digest_object(capsule),
        snapshot_digest=snapshot_digest,
        key_envelope_digest=key_envelope_digest,
        file_count=file_count,
        total_bytes=total_bytes,
        active_key_id=active_key_id,
        active_key_version=active_key_version,
        key_provider=provider,
    )


def verify_recovery_capsule(
    capsule: Path,
    *,
    passphrase: str,
    authorization: AuthorizationContext,
    tenant_id: str,
    case_id: str,
    repo_root: Path | None = None,
) -> VerifiedRecoveryCapsuleV1:
    """Verify capsule completeness, key custody, and every encrypted evidence object offline."""
    _passphrase_bytes(passphrase)
    root = _safe_absolute(capsule, label="recovery capsule")
    _require_capsule_suffix(root)
    _outside_repo(root, repo_root, label="recovery capsule")
    return _verify_capsule_root(
        root,
        passphrase=passphrase,
        authorization=authorization,
        tenant_id=tenant_id.strip(),
        case_id=case_id.strip(),
    )


def restore_recovery_capsule(
    capsule: Path,
    destination: Path,
    *,
    passphrase: str,
    authorization: AuthorizationContext,
    tenant_id: str,
    case_id: str,
    repo_root: Path | None = None,
) -> RestoredPrivateEvidenceV1:
    """Restore verified ciphertext/provenance and keep recovered keys in memory only."""
    tenant = tenant_id.strip()
    case = case_id.strip()
    _require_permission(
        authorization,
        Permission.EVIDENCE_WRITE,
        tenant_id=tenant,
        case_id=case,
    )
    verified = verify_recovery_capsule(
        capsule,
        passphrase=passphrase,
        authorization=authorization,
        tenant_id=tenant,
        case_id=case,
        repo_root=repo_root,
    )
    target = Path(os.path.abspath(destination.expanduser()))
    _outside_repo(target, repo_root, label="recovery restore destination")
    if target.exists():
        raise PrivateEvidenceRecoveryError("recovery restore destination already exists")
    capsule_root = verified.capsule_path
    if target == capsule_root or capsule_root in target.parents:
        raise PrivateEvidenceRecoveryError("restore destination cannot be inside recovery capsule")
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = _staging_path(target)
    try:
        _copy_evidence(capsule_root / "evidence", stage)
        snapshot = _read_mapping(capsule_root / "snapshot.json", label="recovery snapshot")
        files = _parse_snapshot(
            snapshot,
            expected_case_scope_digest=digest_object(
                {"tenant_id": tenant, "case_id": case}
            ),
        )
        _verify_inventory_against_snapshot(stage, files)
        staged_store = PrivateEvidenceStore(
            stage,
            key_provider=verified.key_provider,
            authorization=authorization,
            tenant_id=tenant,
            case_id=case,
            key_id=verified.active_key_id,
            key_version=verified.active_key_version,
        )
        required_identities = _verify_store(staged_store)
        if required_identities != verified.key_provider.identities:
            raise PrivateEvidenceRecoveryError("restored evidence key identities changed")
        os.replace(stage, target)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise

    final_store = PrivateEvidenceStore(
        target,
        key_provider=verified.key_provider,
        authorization=authorization,
        tenant_id=tenant,
        case_id=case,
        key_id=verified.active_key_id,
        key_version=verified.active_key_version,
    )
    _verify_store(final_store)
    return RestoredPrivateEvidenceV1(
        store=final_store,
        key_provider=verified.key_provider,
        capsule_id=verified.capsule_id,
        snapshot_digest=verified.snapshot_digest,
    )
