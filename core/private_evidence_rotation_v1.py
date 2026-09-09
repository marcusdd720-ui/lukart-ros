"""Immutable key rotation for CASE-OPS-01 private evidence envelopes."""

from __future__ import annotations

import base64
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.enterprise.contracts import EnterpriseContractError, Permission
from core.private_evidence_v1 import (
    ALGORITHM,
    NONCE_BYTES,
    SCHEMA_ENVELOPE,
    SCHEMA_MANIFEST,
    EvidenceKind,
    ImportedEvidence,
    PrivateEvidenceError,
    PrivateEvidenceManifestV1,
    PrivateEvidenceStore,
    canonical_json,
    digest_hex,
    digest_object,
)

SCHEMA_REENCRYPT_RECEIPT = "lukart.evidence-reencryption-receipt.v1"


def _load_mapping(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise PrivateEvidenceError("rotation source object missing or symlinked")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrivateEvidenceError("rotation source object is invalid JSON") from exc
    if not isinstance(value, dict):
        raise PrivateEvidenceError("rotation source object must be a mapping")
    return value


def _required_str(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PrivateEvidenceError(f"invalid rotation manifest field: {key}")
    return value


def _required_int(mapping: dict[str, object], key: str, *, minimum: int = 0) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise PrivateEvidenceError(f"invalid rotation manifest field: {key}")
    return value


def _object_path(root: Path, category: str, digest: str) -> Path:
    value = digest_hex(digest)
    base = root / category
    target = base / value[:2] / f"{value}.json"
    if base.is_symlink() or target.parent.is_symlink():
        raise PrivateEvidenceError("rotation object path contains a symlink")
    return target


def _exclusive_json(path: Path, value: object) -> None:
    payload = canonical_json(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise PrivateEvidenceError("rotation object path contains a symlink")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != payload:
            raise PrivateEvidenceError("rotation immutable object divergence detected") from None
        return
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def reencrypt_evidence(
    store: PrivateEvidenceStore,
    imported: ImportedEvidence,
    *,
    target_key_id: str,
    target_key_version: int,
) -> ImportedEvidence:
    """Create a new encrypted envelope without redefining plaintext evidence identity.

    The original immutable envelope remains readable. The returned receipt binds the
    predecessor manifest to the rotated manifest so CCL can record the transition
    without making the private store a case-history authority.
    """
    key_id = target_key_id.strip()
    if not key_id or target_key_version < 1:
        raise PrivateEvidenceError("target key id and positive key version are required")
    try:
        store.authorization.require(
            Permission.EVIDENCE_WRITE,
            tenant_id=store.tenant_id,
            case_id=store.case_id,
            strict_scope=True,
        )
    except EnterpriseContractError as exc:
        raise PrivateEvidenceError(str(exc)) from exc

    store.verify(imported)
    old_manifest = _load_mapping(imported.manifest_path)
    if digest_object(old_manifest) != imported.manifest_digest:
        raise PrivateEvidenceError("rotation source manifest digest mismatch")
    if _required_str(old_manifest, "evidence_id") != imported.evidence_id:
        raise PrivateEvidenceError("rotation source evidence identity mismatch")
    if _required_str(old_manifest, "case_scope_digest") != store.case_scope_digest:
        raise PrivateEvidenceError("rotation source belongs to a different case scope")
    old_key_id = _required_str(old_manifest, "key_id")
    old_key_version = _required_int(old_manifest, "key_version", minimum=1)
    if key_id == old_key_id and target_key_version == old_key_version:
        raise PrivateEvidenceError("rotation target must differ from current key identity")

    evidence_kind = _required_str(old_manifest, "evidence_kind")
    try:
        EvidenceKind(evidence_kind)
    except ValueError as exc:
        raise PrivateEvidenceError("unsupported evidence kind in rotation source") from exc
    media_type = _required_str(old_manifest, "media_type")
    source_ref_digest = _required_str(old_manifest, "source_ref_digest")
    digest_hex(source_ref_digest)
    size_bytes = _required_int(old_manifest, "size_bytes")

    plaintext = store.read(imported)
    if len(plaintext) != size_bytes:
        raise PrivateEvidenceError("rotation plaintext size mismatch")

    key = store.key_provider.get_key(key_id, target_key_version)
    if not isinstance(key, bytes) or len(key) != 32:
        raise PrivateEvidenceError("AES-256-GCM requires exactly 32 target key bytes")
    aad = {
        "schema": SCHEMA_ENVELOPE,
        "case_scope_digest": store.case_scope_digest,
        "evidence_id": imported.evidence_id,
        "size_bytes": len(plaintext),
        "key_id": key_id,
        "key_version": target_key_version,
    }
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, canonical_json(aad))
    envelope = {
        "schema": SCHEMA_ENVELOPE,
        "algorithm": ALGORITHM,
        "key_id": key_id,
        "key_version": target_key_version,
        "aad": aad,
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
    }
    envelope_digest = digest_object(envelope)
    envelope_path = _object_path(store.root, "objects", envelope_digest)
    _exclusive_json(envelope_path, envelope)

    manifest = PrivateEvidenceManifestV1(
        schema=SCHEMA_MANIFEST,
        evidence_id=imported.evidence_id,
        plaintext_sha256=digest_hex(imported.evidence_id),
        size_bytes=len(plaintext),
        media_type=media_type,
        evidence_kind=evidence_kind,
        case_scope_digest=store.case_scope_digest,
        source_ref_digest=source_ref_digest,
        envelope_digest=envelope_digest,
        algorithm=ALGORITHM,
        key_id=key_id,
        key_version=target_key_version,
    )
    manifest_dict = manifest.canonical_dict()
    manifest_digest = digest_object(manifest_dict)
    manifest_path = _object_path(store.root, "manifests", manifest_digest)
    _exclusive_json(manifest_path, manifest_dict)

    receipt = {
        "schema": SCHEMA_REENCRYPT_RECEIPT,
        "operation": "REENCRYPTED",
        "evidence_id": imported.evidence_id,
        "manifest_digest": manifest_digest,
        "previous_manifest_digest": imported.manifest_digest,
        "case_scope_digest": store.case_scope_digest,
        "source_ref_digest": source_ref_digest,
        "target_key_id": key_id,
        "target_key_version": target_key_version,
        "imported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    receipt_digest = digest_object(receipt)
    receipt_path = _object_path(store.root, "receipts", receipt_digest)
    _exclusive_json(receipt_path, receipt)

    rotated = ImportedEvidence(
        evidence_id=imported.evidence_id,
        manifest_digest=manifest_digest,
        receipt_digest=receipt_digest,
        manifest_path=manifest_path,
        receipt_path=receipt_path,
        envelope_path=envelope_path,
    )
    store.verify(rotated)
    return rotated
