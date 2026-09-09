"""Encrypted, content-addressed private evidence intake for CASE-OPS-01."""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.enterprise.contracts import AuthorizationContext, EnterpriseContractError, Permission

SCHEMA_MANIFEST = "lukart.private-evidence-manifest.v1"
SCHEMA_RECEIPT = "lukart.evidence-import-receipt.v1"
SCHEMA_ENVELOPE = "lukart.private-evidence-envelope.v1"
SCHEMA_SOURCE_INDEX = "lukart.private-evidence-source-index.v1"
ALGORITHM = "AES-256-GCM"
NONCE_BYTES = 12


class PrivateEvidenceError(RuntimeError):
    """Fail-closed error at the private-evidence trust boundary."""


class EvidenceKind(StrEnum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    DERIVED = "DERIVED"


class EvidenceKeyProvider(Protocol):
    """Resolve key bytes without persisting key material in evidence metadata."""

    def get_key(self, key_id: str, key_version: int) -> bytes: ...


@dataclass(frozen=True, slots=True)
class PrivateEvidenceManifestV1:
    schema: str
    evidence_id: str
    plaintext_sha256: str
    size_bytes: int
    media_type: str
    evidence_kind: str
    case_scope_digest: str
    source_ref_digest: str
    envelope_digest: str
    algorithm: str
    key_id: str
    key_version: int

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EvidenceImportReceiptV1:
    schema: str
    evidence_id: str
    manifest_digest: str
    case_scope_digest: str
    source_ref_digest: str
    imported_at: str
    operation: str = "IMPORT_ACCEPTED"

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ImportedEvidence:
    evidence_id: str
    manifest_digest: str
    receipt_digest: str
    manifest_path: Path
    receipt_path: Path
    envelope_path: Path


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def content_id(payload: bytes) -> str:
    return f"sha256:{sha256_hex(payload)}"


def opaque_digest(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise PrivateEvidenceError("opaque identity input cannot be blank")
    return content_id(normalized.encode("utf-8"))


def digest_object(value: object) -> str:
    return content_id(canonical_json(value))


def digest_hex(identifier: str) -> str:
    prefix, separator, value = identifier.partition(":")
    if separator != ":" or prefix != "sha256" or len(value) != 64:
        raise PrivateEvidenceError("invalid sha256 content identifier")
    try:
        int(value, 16)
    except ValueError as exc:
        raise PrivateEvidenceError("invalid sha256 content identifier") from exc
    return value


def media_type_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _safe_media_type(value: str) -> str:
    media_type = value.strip().lower()
    if not media_type or "/" not in media_type or any(ch.isspace() for ch in media_type):
        raise PrivateEvidenceError("invalid media type")
    return media_type


def _exclusive_json(path: Path, value: object) -> None:
    payload = canonical_json(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise PrivateEvidenceError("immutable object path contains a symlink")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != payload:
            raise PrivateEvidenceError("immutable object divergence detected") from None
        return
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _load_json(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise PrivateEvidenceError("required immutable object missing or symlinked")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrivateEvidenceError("invalid immutable JSON object") from exc
    if not isinstance(value, dict):
        raise PrivateEvidenceError("immutable JSON object must be a mapping")
    return value


class PrivateEvidenceStore:
    """Case-scoped evidence byte store; it is not a case-history authority."""

    def __init__(
        self,
        root: Path,
        *,
        key_provider: EvidenceKeyProvider,
        authorization: AuthorizationContext,
        tenant_id: str,
        case_id: str,
        key_id: str,
        key_version: int = 1,
    ) -> None:
        self.root = root.expanduser().resolve()
        self.key_provider = key_provider
        self.authorization = authorization
        self.tenant_id = tenant_id.strip()
        self.case_id = case_id.strip()
        self.key_id = key_id.strip()
        self.key_version = key_version
        if not self.tenant_id or not self.case_id or not self.key_id or key_version < 1:
            raise PrivateEvidenceError("tenant, case, key id and key version are required")
        self._require(Permission.EVIDENCE_READ)
        self._prepare_root()
        self.case_scope_digest = digest_object(
            {"tenant_id": self.tenant_id, "case_id": self.case_id}
        )

    def _prepare_root(self) -> None:
        if self.root.exists() and self.root.is_symlink():
            raise PrivateEvidenceError("private evidence root cannot be a symlink")
        self.root.mkdir(parents=True, exist_ok=True)
        current = self.root
        while True:
            if current.is_symlink():
                raise PrivateEvidenceError("private evidence root contains a symlink")
            if current.parent == current:
                break
            current = current.parent
        try:
            self.root.chmod(0o700)
        except OSError:
            pass

    def _require(self, permission: Permission) -> None:
        try:
            self.authorization.require(
                permission,
                tenant_id=self.tenant_id,
                case_id=self.case_id,
                strict_scope=True,
            )
        except EnterpriseContractError as exc:
            raise PrivateEvidenceError(str(exc)) from exc

    def _key(self, key_id: str | None = None, key_version: int | None = None) -> bytes:
        resolved_id = key_id or self.key_id
        resolved_version = key_version or self.key_version
        key = self.key_provider.get_key(resolved_id, resolved_version)
        if not isinstance(key, bytes) or len(key) != 32:
            raise PrivateEvidenceError("AES-256-GCM requires exactly 32 key bytes")
        return key

    def _path(self, category: str, digest: str) -> Path:
        value = digest_hex(digest)
        base = self.root / category
        target = base / value[:2] / f"{value}.json"
        if base.is_symlink() or target.parent.is_symlink():
            raise PrivateEvidenceError("private evidence object path contains a symlink")
        return target

    def _source_index_path(self, source_ref_digest: str) -> Path:
        return self._path("source-index", source_ref_digest)

    def import_file(
        self,
        source: Path,
        *,
        source_ref: str,
        kind: EvidenceKind = EvidenceKind.PRIMARY,
        media_type: str | None = None,
    ) -> ImportedEvidence:
        path = source.expanduser().resolve()
        if not path.is_file() or path.is_symlink():
            raise PrivateEvidenceError("source must be a regular non-symlink file")
        before = path.stat()
        payload = path.read_bytes()
        after = path.stat()
        if (
            before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
        ):
            raise PrivateEvidenceError("source changed during ingestion")
        return self.import_bytes(
            payload,
            source_ref=source_ref,
            kind=kind,
            media_type=media_type or media_type_for(path),
        )

    def import_bytes(
        self,
        payload: bytes,
        *,
        source_ref: str,
        kind: EvidenceKind = EvidenceKind.PRIMARY,
        media_type: str = "application/octet-stream",
    ) -> ImportedEvidence:
        self._require(Permission.EVIDENCE_WRITE)
        if not isinstance(payload, bytes):
            raise PrivateEvidenceError("evidence payload must be bytes")
        evidence_id = content_id(payload)
        source_ref_digest = opaque_digest(source_ref)
        index_path = self._source_index_path(source_ref_digest)
        if index_path.exists():
            index = _load_json(index_path)
            existing = str(index.get("evidence_id", ""))
            if existing != evidence_id:
                raise PrivateEvidenceError(
                    "logical source mutation detected; use a new source identity"
                )
            return self._load_imported(
                evidence_id=evidence_id,
                manifest_digest=str(index.get("manifest_digest", "")),
                receipt_digest=str(index.get("receipt_digest", "")),
            )

        aad = {
            "schema": SCHEMA_ENVELOPE,
            "case_scope_digest": self.case_scope_digest,
            "evidence_id": evidence_id,
            "size_bytes": len(payload),
            "key_id": self.key_id,
            "key_version": self.key_version,
        }
        nonce = os.urandom(NONCE_BYTES)
        ciphertext = AESGCM(self._key()).encrypt(nonce, payload, canonical_json(aad))
        envelope = {
            "schema": SCHEMA_ENVELOPE,
            "algorithm": ALGORITHM,
            "key_id": self.key_id,
            "key_version": self.key_version,
            "aad": aad,
            "nonce_b64": base64.b64encode(nonce).decode("ascii"),
            "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
        }
        envelope_digest = digest_object(envelope)
        envelope_path = self._path("objects", envelope_digest)
        _exclusive_json(envelope_path, envelope)

        manifest = PrivateEvidenceManifestV1(
            schema=SCHEMA_MANIFEST,
            evidence_id=evidence_id,
            plaintext_sha256=digest_hex(evidence_id),
            size_bytes=len(payload),
            media_type=_safe_media_type(media_type),
            evidence_kind=kind.value,
            case_scope_digest=self.case_scope_digest,
            source_ref_digest=source_ref_digest,
            envelope_digest=envelope_digest,
            algorithm=ALGORITHM,
            key_id=self.key_id,
            key_version=self.key_version,
        )
        manifest_dict = manifest.canonical_dict()
        manifest_digest = digest_object(manifest_dict)
        manifest_path = self._path("manifests", manifest_digest)
        _exclusive_json(manifest_path, manifest_dict)

        receipt = EvidenceImportReceiptV1(
            schema=SCHEMA_RECEIPT,
            evidence_id=evidence_id,
            manifest_digest=manifest_digest,
            case_scope_digest=self.case_scope_digest,
            source_ref_digest=source_ref_digest,
            imported_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        )
        receipt_dict = receipt.canonical_dict()
        receipt_digest = digest_object(receipt_dict)
        receipt_path = self._path("receipts", receipt_digest)
        _exclusive_json(receipt_path, receipt_dict)
        _exclusive_json(
            index_path,
            {
                "schema": SCHEMA_SOURCE_INDEX,
                "evidence_id": evidence_id,
                "manifest_digest": manifest_digest,
                "receipt_digest": receipt_digest,
            },
        )
        return ImportedEvidence(
            evidence_id=evidence_id,
            manifest_digest=manifest_digest,
            receipt_digest=receipt_digest,
            manifest_path=manifest_path,
            receipt_path=receipt_path,
            envelope_path=envelope_path,
        )

    def _load_imported(
        self,
        *,
        evidence_id: str,
        manifest_digest: str,
        receipt_digest: str,
    ) -> ImportedEvidence:
        manifest_path = self._path("manifests", manifest_digest)
        receipt_path = self._path("receipts", receipt_digest)
        manifest = _load_json(manifest_path)
        receipt = _load_json(receipt_path)
        if digest_object(manifest) != manifest_digest:
            raise PrivateEvidenceError("manifest digest mismatch")
        if digest_object(receipt) != receipt_digest:
            raise PrivateEvidenceError("receipt digest mismatch")
        if str(manifest.get("evidence_id", "")) != evidence_id:
            raise PrivateEvidenceError("manifest evidence identity mismatch")
        if str(receipt.get("evidence_id", "")) != evidence_id:
            raise PrivateEvidenceError("receipt evidence identity mismatch")
        if str(receipt.get("manifest_digest", "")) != manifest_digest:
            raise PrivateEvidenceError("receipt does not bind the manifest")
        if str(manifest.get("case_scope_digest", "")) != self.case_scope_digest:
            raise PrivateEvidenceError("manifest belongs to a different case scope")
        envelope_digest = str(manifest.get("envelope_digest", ""))
        return ImportedEvidence(
            evidence_id=evidence_id,
            manifest_digest=manifest_digest,
            receipt_digest=receipt_digest,
            manifest_path=manifest_path,
            receipt_path=receipt_path,
            envelope_path=self._path("objects", envelope_digest),
        )

    def read(self, imported: ImportedEvidence) -> bytes:
        self._require(Permission.EVIDENCE_READ)
        resolved = self._load_imported(
            evidence_id=imported.evidence_id,
            manifest_digest=imported.manifest_digest,
            receipt_digest=imported.receipt_digest,
        )
        manifest = _load_json(resolved.manifest_path)
        envelope = _load_json(resolved.envelope_path)
        if digest_object(envelope) != str(manifest.get("envelope_digest", "")):
            raise PrivateEvidenceError("encrypted envelope digest mismatch")
        if envelope.get("schema") != SCHEMA_ENVELOPE or envelope.get("algorithm") != ALGORITHM:
            raise PrivateEvidenceError("unsupported encrypted evidence envelope")
        aad = envelope.get("aad")
        expected_aad = {
            "schema": SCHEMA_ENVELOPE,
            "case_scope_digest": self.case_scope_digest,
            "evidence_id": imported.evidence_id,
            "size_bytes": int(manifest.get("size_bytes", -1)),
            "key_id": str(manifest.get("key_id", "")),
            "key_version": int(manifest.get("key_version", 0)),
        }
        if aad != expected_aad:
            raise PrivateEvidenceError("encrypted envelope metadata substitution detected")
        if not isinstance(aad, dict):
            raise PrivateEvidenceError("encrypted envelope AAD missing")
        try:
            nonce = base64.b64decode(str(envelope["nonce_b64"]), validate=True)
            ciphertext = base64.b64decode(str(envelope["ciphertext_b64"]), validate=True)
            if len(nonce) != NONCE_BYTES:
                raise PrivateEvidenceError("invalid AES-GCM nonce length")
            plaintext = AESGCM(
                self._key(str(manifest["key_id"]), int(manifest["key_version"]))
            ).decrypt(nonce, ciphertext, canonical_json(aad))
        except PrivateEvidenceError:
            raise
        except Exception as exc:
            raise PrivateEvidenceError("encrypted evidence authentication failed") from exc
        if content_id(plaintext) != imported.evidence_id:
            raise PrivateEvidenceError("plaintext evidence identity mismatch")
        if len(plaintext) != int(manifest["size_bytes"]):
            raise PrivateEvidenceError("plaintext evidence size mismatch")
        return plaintext

    def verify(self, imported: ImportedEvidence) -> None:
        self.read(imported)

    def ccl_reference(self, imported: ImportedEvidence) -> dict[str, str]:
        """Return the exact immutable reference for a CCL event payload."""
        self.verify(imported)
        return {
            "evidence_id": imported.evidence_id,
            "manifest_digest": imported.manifest_digest,
            "receipt_digest": imported.receipt_digest,
            "case_scope_digest": self.case_scope_digest,
        }

    def backup_to(self, destination: Path) -> Path:
        """Copy ciphertext/provenance only; plaintext is never materialized."""
        self._require(Permission.EVIDENCE_READ)
        target = destination.expanduser().resolve()
        if target.exists():
            raise PrivateEvidenceError("backup destination must not already exist")
        if self.root == target or self.root in target.parents:
            raise PrivateEvidenceError("backup destination cannot be inside evidence root")
        shutil.copytree(self.root, target, symlinks=False)
        return target

    @classmethod
    def restore_from(
        cls,
        source: Path,
        destination: Path,
        *,
        key_provider: EvidenceKeyProvider,
        authorization: AuthorizationContext,
        tenant_id: str,
        case_id: str,
        key_id: str,
        key_version: int = 1,
    ) -> PrivateEvidenceStore:
        source_root = source.expanduser().resolve()
        target = destination.expanduser().resolve()
        if not source_root.is_dir() or source_root.is_symlink():
            raise PrivateEvidenceError("backup source must be a regular directory")
        if target.exists():
            raise PrivateEvidenceError("restore destination must not already exist")
        for candidate in source_root.rglob("*"):
            if candidate.is_symlink():
                raise PrivateEvidenceError("backup contains a symlink")
        shutil.copytree(source_root, target, symlinks=False)
        return cls(
            target,
            key_provider=key_provider,
            authorization=authorization,
            tenant_id=tenant_id,
            case_id=case_id,
            key_id=key_id,
            key_version=key_version,
        )
