from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.enterprise.contracts import AuthorizationContext, Permission
from core.private_evidence_v1 import (
    PrivateEvidenceError,
    PrivateEvidenceStore,
)


class KeyProvider:
    def __init__(self, key: bytes = b"A" * 32) -> None:
        self.key = key

    def get_key(self, key_id: str, key_version: int) -> bytes:
        assert key_id == "key-main"
        assert key_version == 1
        return self.key


def authorization(
    *,
    case_ids: tuple[str, ...] = ("CASE-A",),
    write: bool = True,
) -> AuthorizationContext:
    permissions = [Permission.EVIDENCE_READ]
    if write:
        permissions.append(Permission.EVIDENCE_WRITE)
    return AuthorizationContext(
        subject_id="synthetic-worker",
        tenant_id="tenant-test",
        roles=("case-worker",),
        permissions=tuple(permissions),
        case_ids=case_ids,
    )


def store(
    root: Path,
    *,
    provider: KeyProvider | None = None,
    auth: AuthorizationContext | None = None,
    case_id: str = "CASE-A",
) -> PrivateEvidenceStore:
    return PrivateEvidenceStore(
        root,
        key_provider=provider or KeyProvider(),
        authorization=auth or authorization(),
        tenant_id="tenant-test",
        case_id=case_id,
        key_id="key-main",
    )


def test_roundtrip_uses_plaintext_hash_as_evidence_identity(tmp_path: Path) -> None:
    evidence_store = store(tmp_path / "evidence")
    payload = b"synthetic private evidence bytes"

    imported = evidence_store.import_bytes(
        payload,
        source_ref="source-slot-a",
        media_type="text/plain",
    )

    assert imported.evidence_id.startswith("sha256:")
    assert evidence_store.read(imported) == payload
    evidence_store.verify(imported)


def test_duplicate_is_idempotent_and_mutation_fails_closed(tmp_path: Path) -> None:
    evidence_store = store(tmp_path / "evidence")
    first = evidence_store.import_bytes(b"v1", source_ref="logical-source")
    duplicate = evidence_store.import_bytes(b"v1", source_ref="logical-source")

    assert duplicate == first
    with pytest.raises(PrivateEvidenceError, match="mutation"):
        evidence_store.import_bytes(b"v2", source_ref="logical-source")


def test_rename_does_not_change_evidence_identity_and_nonce_changes_envelope(
    tmp_path: Path,
) -> None:
    evidence_store = store(tmp_path / "evidence")
    first = evidence_store.import_bytes(b"same bytes", source_ref="name-a")
    renamed = evidence_store.import_bytes(b"same bytes", source_ref="name-b")

    assert first.evidence_id == renamed.evidence_id
    assert first.envelope_path != renamed.envelope_path


def test_write_permission_is_deny_by_default(tmp_path: Path) -> None:
    evidence_store = store(
        tmp_path / "evidence",
        auth=authorization(write=False),
    )
    with pytest.raises(PrivateEvidenceError, match="permission denied"):
        evidence_store.import_bytes(b"blocked", source_ref="slot")


def test_cross_case_scope_is_denied(tmp_path: Path) -> None:
    with pytest.raises(PrivateEvidenceError, match="case scope denied"):
        store(
            tmp_path / "evidence",
            auth=authorization(case_ids=("CASE-B",)),
            case_id="CASE-A",
        )


def test_wrong_key_and_ciphertext_tamper_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    evidence_store = store(root)
    imported = evidence_store.import_bytes(b"authenticated bytes", source_ref="slot")

    wrong_key_store = store(root, provider=KeyProvider(b"B" * 32))
    with pytest.raises(PrivateEvidenceError, match="authentication failed"):
        wrong_key_store.read(imported)

    envelope = json.loads(imported.envelope_path.read_text(encoding="utf-8"))
    envelope["ciphertext_b64"] = envelope["ciphertext_b64"][:-4] + "AAAA"
    imported.envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(PrivateEvidenceError, match="envelope digest mismatch"):
        evidence_store.read(imported)


def test_manifest_and_receipt_tamper_fail_closed(tmp_path: Path) -> None:
    evidence_store = store(tmp_path / "evidence")
    imported = evidence_store.import_bytes(b"manifest-bound", source_ref="slot")

    manifest = json.loads(imported.manifest_path.read_text(encoding="utf-8"))
    manifest["media_type"] = "application/substituted"
    imported.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PrivateEvidenceError, match="manifest digest mismatch"):
        evidence_store.read(imported)

    other_store = store(tmp_path / "other")
    other = other_store.import_bytes(b"receipt-bound", source_ref="slot-two")
    receipt = json.loads(other.receipt_path.read_text(encoding="utf-8"))
    receipt["operation"] = "SUBSTITUTED"
    other.receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(PrivateEvidenceError, match="receipt digest mismatch"):
        other_store.read(other)


def test_truncated_envelope_fails_closed(tmp_path: Path) -> None:
    evidence_store = store(tmp_path / "evidence")
    imported = evidence_store.import_bytes(b"complete", source_ref="slot")
    imported.envelope_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(PrivateEvidenceError, match="envelope digest mismatch"):
        evidence_store.read(imported)


def test_different_case_cannot_replay_manifest(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    source_store = store(
        root,
        auth=authorization(case_ids=("CASE-A", "CASE-B")),
    )
    imported = source_store.import_bytes(b"case scoped", source_ref="slot")
    other_case = store(
        root,
        auth=authorization(case_ids=("CASE-A", "CASE-B")),
        case_id="CASE-B",
    )

    with pytest.raises(PrivateEvidenceError, match="different case scope"):
        other_case.read(imported)


def test_ccl_reference_contains_only_digest_bound_identifiers(tmp_path: Path) -> None:
    evidence_store = store(tmp_path / "evidence")
    imported = evidence_store.import_bytes(b"ccl evidence", source_ref="slot")

    reference = evidence_store.ccl_reference(imported)

    assert reference == {
        "evidence_id": imported.evidence_id,
        "manifest_digest": imported.manifest_digest,
        "receipt_digest": imported.receipt_digest,
        "case_scope_digest": evidence_store.case_scope_digest,
    }


def test_backup_restore_verifies_offline_without_plaintext_copy(tmp_path: Path) -> None:
    evidence_store = store(tmp_path / "evidence")
    payload = b"offline replay bytes"
    imported = evidence_store.import_bytes(payload, source_ref="slot")
    backup = evidence_store.backup_to(tmp_path / "backup")

    restored = PrivateEvidenceStore.restore_from(
        backup,
        tmp_path / "restored",
        key_provider=KeyProvider(),
        authorization=authorization(),
        tenant_id="tenant-test",
        case_id="CASE-A",
        key_id="key-main",
    )

    assert restored.read(imported) == payload
    for candidate in (backup, tmp_path / "restored"):
        for path in candidate.rglob("*"):
            if path.is_file():
                assert payload not in path.read_bytes()


def test_sensitive_source_reference_and_plaintext_are_not_persisted(tmp_path: Path) -> None:
    evidence_store = store(tmp_path / "evidence")
    source_ref = "SYNTHETIC-PERSON|private-reference"
    payload = b"synthetic-sensitive-payload"
    evidence_store.import_bytes(payload, source_ref=source_ref)

    for path in evidence_store.root.rglob("*"):
        if path.is_file():
            persisted = path.read_bytes()
            assert source_ref.encode("utf-8") not in persisted
            assert payload not in persisted


def test_symlink_source_and_root_are_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("synthetic", encoding="utf-8")
    source_link = tmp_path / "source-link.txt"
    root_target = tmp_path / "root-target"
    root_target.mkdir()
    root_link = tmp_path / "root-link"
    try:
        source_link.symlink_to(target)
        root_link.symlink_to(root_target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")

    evidence_store = store(tmp_path / "regular-root")
    with pytest.raises(PrivateEvidenceError, match="non-symlink"):
        evidence_store.import_file(source_link, source_ref="slot")
    with pytest.raises(PrivateEvidenceError, match="symlink"):
        store(root_link)
