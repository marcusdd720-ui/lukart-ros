from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.enterprise.contracts import AuthorizationContext, Permission
from core.private_evidence_derivation_v1 import derive_utf8_text
from core.private_evidence_recovery_v1 import (
    PrivateEvidenceRecoveryError,
    create_recovery_capsule,
    restore_recovery_capsule,
    verify_recovery_capsule,
)
from core.private_evidence_rotation_v1 import reencrypt_evidence
from core.private_evidence_v1 import (
    ImportedEvidence,
    PrivateEvidenceError,
    PrivateEvidenceStore,
)

PASSPHRASE = "correct-horse-battery-staple"


class KeyProvider:
    def __init__(self, *, include_old: bool = True, include_new: bool = True) -> None:
        self.keys: dict[tuple[str, int], bytes] = {}
        if include_old:
            self.keys[("key-a", 1)] = b"A" * 32
        if include_new:
            self.keys[("key-b", 2)] = b"B" * 32

    def get_key(self, key_id: str, key_version: int) -> bytes:
        try:
            return self.keys[(key_id, key_version)]
        except KeyError as exc:
            raise PrivateEvidenceError("synthetic key unavailable") from exc


def auth(
    *,
    tenant: str = "tenant-a",
    case_id: str = "CASE-A",
    write: bool = True,
) -> AuthorizationContext:
    permissions = [Permission.EVIDENCE_READ]
    if write:
        permissions.append(Permission.EVIDENCE_WRITE)
    return AuthorizationContext(
        subject_id="synthetic-recovery-operator",
        tenant_id=tenant,
        roles=("case-worker",),
        permissions=tuple(permissions),
        case_ids=(case_id,),
    )


def make_rotated_store(
    tmp_path: Path,
) -> tuple[PrivateEvidenceStore, ImportedEvidence, ImportedEvidence, bytes]:
    store = PrivateEvidenceStore(
        tmp_path / "private-evidence",
        key_provider=KeyProvider(),
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
        key_id="key-a",
        key_version=1,
    )
    payload = b"synthetic private recovery evidence"
    original = store.import_bytes(
        payload,
        source_ref="document-slot:1",
        media_type="text/plain",
    )
    rotated = reencrypt_evidence(
        store,
        original,
        target_key_id="key-b",
        target_key_version=2,
    )
    active_store = PrivateEvidenceStore(
        store.root,
        key_provider=KeyProvider(),
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
        key_id="key-b",
        key_version=2,
    )
    return active_store, original, rotated, payload


def test_multikey_rotation_roundtrip_and_keys_remain_in_memory(tmp_path: Path) -> None:
    store, original, rotated, payload = make_rotated_store(tmp_path)
    capsule = create_recovery_capsule(
        store,
        tmp_path / "case-a.mvros-recovery",
        passphrase=PASSPHRASE,
    )

    verified = verify_recovery_capsule(
        capsule.capsule_path,
        passphrase=PASSPHRASE,
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
    )
    assert verified.key_provider.identities == (("key-a", 1), ("key-b", 2))

    restored = restore_recovery_capsule(
        capsule.capsule_path,
        tmp_path / "restored-evidence",
        passphrase=PASSPHRASE,
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
    )
    assert restored.store.read(original) == payload
    assert restored.store.read(rotated) == payload
    assert restored.key_provider.identities == (("key-a", 1), ("key-b", 2))


def test_snapshot_identity_is_stable_while_wrapped_key_envelope_is_randomized(
    tmp_path: Path,
) -> None:
    store, _original, _rotated, _payload = make_rotated_store(tmp_path)
    first = create_recovery_capsule(
        store,
        tmp_path / "first.mvros-recovery",
        passphrase=PASSPHRASE,
    )
    second = create_recovery_capsule(
        store,
        tmp_path / "second.mvros-recovery",
        passphrase=PASSPHRASE,
    )

    assert first.snapshot_digest == second.snapshot_digest
    assert first.key_envelope_digest != second.key_envelope_digest


def test_capsule_never_persists_plaintext_raw_keys_or_passphrase(tmp_path: Path) -> None:
    store, _original, _rotated, payload = make_rotated_store(tmp_path)
    capsule = create_recovery_capsule(
        store,
        tmp_path / "private.mvros-recovery",
        passphrase=PASSPHRASE,
    )

    forbidden = (payload, b"A" * 32, b"B" * 32, PASSPHRASE.encode())
    for path in capsule.capsule_path.rglob("*"):
        if path.is_file():
            persisted = path.read_bytes()
            for secret in forbidden:
                assert secret not in persisted


def test_wrong_passphrase_fails_closed(tmp_path: Path) -> None:
    store, _original, _rotated, _payload = make_rotated_store(tmp_path)
    capsule = create_recovery_capsule(
        store,
        tmp_path / "wrong-pass.mvros-recovery",
        passphrase=PASSPHRASE,
    )

    with pytest.raises(PrivateEvidenceRecoveryError, match="passphrase|authentication"):
        verify_recovery_capsule(
            capsule.capsule_path,
            passphrase="this-is-the-wrong-passphrase",
            authorization=auth(),
            tenant_id="tenant-a",
            case_id="CASE-A",
        )


@pytest.mark.parametrize("mutation", ["missing", "extra", "tamper"])
def test_missing_extra_or_tampered_encrypted_file_fails_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    store, _original, _rotated, _payload = make_rotated_store(tmp_path)
    capsule = create_recovery_capsule(
        store,
        tmp_path / f"{mutation}.mvros-recovery",
        passphrase=PASSPHRASE,
    )
    evidence = capsule.capsule_path / "evidence"
    target = next(path for path in evidence.rglob("*.json") if path.is_file())
    if mutation == "missing":
        target.unlink()
    elif mutation == "extra":
        extra = evidence / "objects" / ("f" * 2) / f"{'f' * 64}.json"
        extra.parent.mkdir(parents=True, exist_ok=True)
        extra.write_text("{}\n", encoding="utf-8")
    else:
        target.write_bytes(target.read_bytes() + b" ")

    with pytest.raises(PrivateEvidenceRecoveryError):
        verify_recovery_capsule(
            capsule.capsule_path,
            passphrase=PASSPHRASE,
            authorization=auth(),
            tenant_id="tenant-a",
            case_id="CASE-A",
        )


def test_cross_tenant_and_cross_case_scope_fail_closed(tmp_path: Path) -> None:
    store, _original, _rotated, _payload = make_rotated_store(tmp_path)
    capsule = create_recovery_capsule(
        store,
        tmp_path / "scope.mvros-recovery",
        passphrase=PASSPHRASE,
    )

    with pytest.raises(PrivateEvidenceRecoveryError):
        verify_recovery_capsule(
            capsule.capsule_path,
            passphrase=PASSPHRASE,
            authorization=auth(tenant="tenant-b"),
            tenant_id="tenant-b",
            case_id="CASE-A",
        )
    with pytest.raises(PrivateEvidenceRecoveryError):
        verify_recovery_capsule(
            capsule.capsule_path,
            passphrase=PASSPHRASE,
            authorization=auth(case_id="CASE-B"),
            tenant_id="tenant-a",
            case_id="CASE-B",
        )


def test_missing_historical_rotation_key_blocks_capsule_creation(tmp_path: Path) -> None:
    store, _original, _rotated, _payload = make_rotated_store(tmp_path)
    incomplete = PrivateEvidenceStore(
        store.root,
        key_provider=KeyProvider(include_old=False),
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
        key_id="key-b",
        key_version=2,
    )

    with pytest.raises(PrivateEvidenceRecoveryError):
        create_recovery_capsule(
            incomplete,
            tmp_path / "missing-old.mvros-recovery",
            passphrase=PASSPHRASE,
        )


def test_derivation_tamper_blocks_capsule_creation(tmp_path: Path) -> None:
    store = PrivateEvidenceStore(
        tmp_path / "private-evidence",
        key_provider=KeyProvider(include_new=False),
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
        key_id="key-a",
        key_version=1,
    )
    source = store.import_bytes(
        b"synthetic UTF-8 evidence\n",
        source_ref="document-slot:1",
        media_type="text/plain",
    )
    derived = derive_utf8_text(store, source)
    receipt = json.loads(derived.derivation_receipt_path.read_text(encoding="utf-8"))
    receipt["replay_class"] = "ENVIRONMENT_BOUND"
    derived.derivation_receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(PrivateEvidenceRecoveryError, match="provenance|derivation"):
        create_recovery_capsule(
            store,
            tmp_path / "tampered-derivation.mvros-recovery",
            passphrase=PASSPHRASE,
        )


def test_restore_refuses_existing_target(tmp_path: Path) -> None:
    store, _original, _rotated, _payload = make_rotated_store(tmp_path)
    capsule = create_recovery_capsule(
        store,
        tmp_path / "existing-target.mvros-recovery",
        passphrase=PASSPHRASE,
    )
    target = tmp_path / "existing"
    target.mkdir()

    with pytest.raises(PrivateEvidenceRecoveryError, match="already exists"):
        restore_recovery_capsule(
            capsule.capsule_path,
            target,
            passphrase=PASSPHRASE,
            authorization=auth(),
            tenant_id="tenant-a",
            case_id="CASE-A",
        )


def test_capsule_destination_inside_repo_is_rejected(tmp_path: Path) -> None:
    store, _original, _rotated, _payload = make_rotated_store(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    with pytest.raises(PrivateEvidenceRecoveryError, match="outside"):
        create_recovery_capsule(
            store,
            repo / "forbidden.mvros-recovery",
            passphrase=PASSPHRASE,
            repo_root=repo,
        )


def test_symlink_inside_capsule_is_rejected(tmp_path: Path) -> None:
    store, _original, _rotated, _payload = make_rotated_store(tmp_path)
    capsule = create_recovery_capsule(
        store,
        tmp_path / "symlink.mvros-recovery",
        passphrase=PASSPHRASE,
    )
    snapshot = capsule.capsule_path / "snapshot.json"
    real = capsule.capsule_path / "snapshot-real.json"
    snapshot.rename(real)
    try:
        snapshot.symlink_to(real)
    except OSError:
        real.rename(snapshot)
        pytest.skip("symlink creation unavailable")

    with pytest.raises(PrivateEvidenceRecoveryError, match="symlink|unexpected"):
        verify_recovery_capsule(
            capsule.capsule_path,
            passphrase=PASSPHRASE,
            authorization=auth(),
            tenant_id="tenant-a",
            case_id="CASE-A",
        )


def test_recovery_export_requires_evidence_write(tmp_path: Path) -> None:
    store, _original, _rotated, _payload = make_rotated_store(tmp_path)
    read_only_store = PrivateEvidenceStore(
        store.root,
        key_provider=KeyProvider(),
        authorization=auth(write=False),
        tenant_id="tenant-a",
        case_id="CASE-A",
        key_id="key-b",
        key_version=2,
    )

    with pytest.raises(PrivateEvidenceRecoveryError, match="permission denied"):
        create_recovery_capsule(
            read_only_store,
            tmp_path / "read-only.mvros-recovery",
            passphrase=PASSPHRASE,
        )
