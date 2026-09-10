from __future__ import annotations

from pathlib import Path

import pytest

from core.enterprise.contracts import AuthorizationContext, Permission
from core.private_evidence_recovery_set_v1 import (
    PrivateEvidenceRecoverySetError,
    RecoverySetResultV1,
    RecoverySetV1,
    create_redundant_recovery_set,
    restore_recovery_set_member,
    run_recovery_set_drill,
    verify_redundant_recovery_set,
)
from core.private_evidence_recovery_v1 import PrivateEvidenceRecoveryError
from core.private_evidence_rotation_v1 import reencrypt_evidence
from core.private_evidence_v1 import (
    ImportedEvidence,
    PrivateEvidenceError,
    PrivateEvidenceStore,
)

PASSPHRASE_A = "synthetic-recovery-passphrase-alpha"
PASSPHRASE_B = "synthetic-recovery-passphrase-bravo"


class KeyProvider:
    def __init__(self) -> None:
        self.keys = {
            ("key-a", 1): b"A" * 32,
            ("key-b", 2): b"B" * 32,
        }

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
        subject_id="synthetic-recovery-set-operator",
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
    payload = b"synthetic redundant recovery evidence"
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
    active = PrivateEvidenceStore(
        store.root,
        key_provider=KeyProvider(),
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
        key_id="key-b",
        key_version=2,
    )
    return active, original, rotated, payload


def device_layout(tmp_path: Path) -> tuple[Path, Path]:
    first = tmp_path / "device-a"
    second = tmp_path / "device-b"
    first.mkdir()
    second.mkdir()
    return first, second


def install_distinct_device_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_device_id(path: Path) -> int:
        parts = path.resolve().parts
        if "private-evidence" in parts:
            return 1
        if "device-a" in parts:
            return 2
        if "device-b" in parts:
            return 3
        return 4

    monkeypatch.setattr(
        "core.private_evidence_recovery_set_v1._device_id",
        fake_device_id,
    )


def create_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    PrivateEvidenceStore,
    ImportedEvidence,
    ImportedEvidence,
    bytes,
    RecoverySetResultV1,
]:
    store, original, rotated, payload = make_rotated_store(tmp_path)
    device_a, device_b = device_layout(tmp_path)
    install_distinct_device_probe(monkeypatch)
    result = create_redundant_recovery_set(
        store,
        (
            device_a / "slot-a.mvros-recovery",
            device_b / "slot-b.mvros-recovery",
        ),
        passphrases=(PASSPHRASE_A, PASSPHRASE_B),
    )
    return store, original, rotated, payload, result


def test_recovery_set_has_independent_wrapping_and_one_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _original, _rotated, _payload, result = create_set(tmp_path, monkeypatch)
    recovery_set = result.recovery_set

    assert recovery_set.recovery_threshold == 1
    assert recovery_set.member_count == 2
    assert recovery_set.members[0].snapshot_digest == recovery_set.snapshot_digest
    assert recovery_set.members[1].snapshot_digest == recovery_set.snapshot_digest
    assert recovery_set.members[0].capsule_id != recovery_set.members[1].capsule_id
    assert (
        recovery_set.members[0].key_envelope_digest
        != recovery_set.members[1].key_envelope_digest
    )
    assert result.member_paths[0].is_dir()
    assert result.member_paths[1].is_dir()


def test_one_member_restores_without_other_passphrase_or_capsule(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, original, rotated, payload, result = create_set(tmp_path, monkeypatch)

    second = result.member_paths[1]
    for path in sorted(second.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    second.rmdir()

    restored = restore_recovery_set_member(
        result.recovery_set,
        slot="A",
        capsule_path=result.member_paths[0],
        passphrase=PASSPHRASE_A,
        destination=tmp_path / "restored-from-a",
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
    )
    assert restored.store.read(original) == payload
    assert restored.store.read(rotated) == payload
    assert restored.snapshot_digest == result.recovery_set.snapshot_digest


def test_same_passphrase_is_rejected_before_any_capsule_is_written(tmp_path: Path) -> None:
    store, _original, _rotated, _payload = make_rotated_store(tmp_path)
    device_a, device_b = device_layout(tmp_path)
    target_a = device_a / "slot-a.mvros-recovery"
    target_b = device_b / "slot-b.mvros-recovery"

    with pytest.raises(PrivateEvidenceRecoverySetError, match="passphrases must be independent"):
        create_redundant_recovery_set(
            store,
            (target_a, target_b),
            passphrases=(PASSPHRASE_A, PASSPHRASE_A),
        )
    assert not target_a.exists()
    assert not target_b.exists()


def test_same_filesystem_device_is_rejected_before_write(tmp_path: Path) -> None:
    store, _original, _rotated, _payload = make_rotated_store(tmp_path)
    device_a, device_b = device_layout(tmp_path)
    target_a = device_a / "slot-a.mvros-recovery"
    target_b = device_b / "slot-b.mvros-recovery"

    with pytest.raises(PrivateEvidenceRecoverySetError, match="two recovery devices distinct"):
        create_redundant_recovery_set(
            store,
            (target_a, target_b),
            passphrases=(PASSPHRASE_A, PASSPHRASE_B),
        )
    assert not target_a.exists()
    assert not target_b.exists()


def test_tampered_member_blocks_full_set_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _original, _rotated, _payload, result = create_set(tmp_path, monkeypatch)
    capsule_json = result.member_paths[1] / "capsule.json"
    original = capsule_json.read_bytes()
    tampered = original.replace(
        b"lukart.private-evidence-recovery-capsule.v1",
        b"lukart.private-evidence-recovery-capsule.v0",
        1,
    )
    assert tampered != original
    capsule_json.write_bytes(tampered)

    with pytest.raises((PrivateEvidenceRecoveryError, PrivateEvidenceRecoverySetError)):
        verify_redundant_recovery_set(
            result.recovery_set,
            result.member_paths,
            passphrases=(PASSPHRASE_A, PASSPHRASE_B),
            authorization=auth(),
            tenant_id="tenant-a",
            case_id="CASE-A",
        )


def test_wrong_member_passphrase_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _original, _rotated, _payload, result = create_set(tmp_path, monkeypatch)

    with pytest.raises(PrivateEvidenceRecoveryError, match="passphrase|authentication"):
        restore_recovery_set_member(
            result.recovery_set,
            slot="B",
            capsule_path=result.member_paths[1],
            passphrase="synthetic-but-wrong-passphrase",
            destination=tmp_path / "wrong-pass",
            authorization=auth(),
            tenant_id="tenant-a",
            case_id="CASE-A",
        )


def test_cross_case_recovery_set_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _original, _rotated, _payload, result = create_set(tmp_path, monkeypatch)

    with pytest.raises(PrivateEvidenceRecoverySetError, match="case scope mismatch"):
        restore_recovery_set_member(
            result.recovery_set,
            slot="A",
            capsule_path=result.member_paths[0],
            passphrase=PASSPHRASE_A,
            destination=tmp_path / "cross-case",
            authorization=auth(case_id="CASE-B"),
            tenant_id="tenant-a",
            case_id="CASE-B",
        )


def test_recovery_set_parser_rejects_unknown_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _original, _rotated, _payload, result = create_set(tmp_path, monkeypatch)
    value = result.recovery_set.canonical_dict()
    value["unexpected"] = True

    with pytest.raises(PrivateEvidenceRecoverySetError, match="unknown or missing"):
        RecoverySetV1.from_dict(value)


def test_full_drill_restores_both_independent_members(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _original, _rotated, _payload, result = create_set(tmp_path, monkeypatch)
    receipt = run_recovery_set_drill(
        result.recovery_set,
        result.member_paths,
        (tmp_path / "drill-a", tmp_path / "drill-b"),
        passphrases=(PASSPHRASE_A, PASSPHRASE_B),
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
    )

    assert receipt.result == "PASS"
    assert receipt.restored_member_count == 2
    assert receipt.recovery_set_id == result.recovery_set.recovery_set_id
    assert receipt.snapshot_digest == result.recovery_set.snapshot_digest
    assert (tmp_path / "drill-a").is_dir()
    assert (tmp_path / "drill-b").is_dir()


def test_receipts_do_not_persist_passphrases_keys_or_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _original, _rotated, _payload, result = create_set(tmp_path, monkeypatch)
    receipt = run_recovery_set_drill(
        result.recovery_set,
        result.member_paths,
        (tmp_path / "receipt-drill-a", tmp_path / "receipt-drill-b"),
        passphrases=(PASSPHRASE_A, PASSPHRASE_B),
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
    )
    persisted_shape = repr(
        {
            "set": result.recovery_set.canonical_dict(),
            "drill": receipt.canonical_dict(),
        }
    )

    assert PASSPHRASE_A not in persisted_shape
    assert PASSPHRASE_B not in persisted_shape
    assert str(tmp_path) not in persisted_shape
    assert (b"A" * 32).hex() not in persisted_shape
    assert (b"B" * 32).hex() not in persisted_shape
