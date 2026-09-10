from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from core.enterprise.contracts import AuthorizationContext, Permission
from core.private_evidence_recovery_ops_v1 import (
    OPERATOR_ASSERTION_CLASS,
    PrivateEvidenceRecoveryOpsError,
    RecoveryOperatorAssertionsV1,
    load_recovery_set_record,
    rotate_recovery_set_secrets,
    run_operator_recovery_drill,
    validate_operator_evidence_shape,
    write_operator_drill_evidence,
    write_recovery_set_record,
    write_redundant_recovery_set_records,
    write_rotation_receipt,
)
from core.private_evidence_recovery_set_v1 import (
    RecoverySetResultV1,
    create_redundant_recovery_set,
    restore_recovery_set_member,
)
from core.private_evidence_rotation_v1 import reencrypt_evidence
from core.private_evidence_v1 import (
    ImportedEvidence,
    PrivateEvidenceError,
    PrivateEvidenceStore,
    canonical_json,
)

OLD_A = "synthetic-old-recovery-passphrase-alpha"
OLD_B = "synthetic-old-recovery-passphrase-bravo"
NEW_A = "synthetic-new-recovery-passphrase-charlie"
NEW_B = "synthetic-new-recovery-passphrase-delta"


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


def auth() -> AuthorizationContext:
    return AuthorizationContext(
        subject_id="synthetic-case-ops-05-operator",
        tenant_id="tenant-a",
        roles=("case-worker",),
        permissions=(Permission.EVIDENCE_READ, Permission.EVIDENCE_WRITE),
        case_ids=("CASE-A",),
    )


def make_store(
    tmp_path: Path,
) -> tuple[PrivateEvidenceStore, ImportedEvidence, ImportedEvidence, bytes]:
    initial = PrivateEvidenceStore(
        tmp_path / "private-evidence",
        key_provider=KeyProvider(),
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
        key_id="key-a",
        key_version=1,
    )
    payload = b"synthetic CASE-OPS-05 recovery evidence"
    original = initial.import_bytes(
        payload,
        source_ref="document-slot:1",
        media_type="text/plain",
    )
    rotated = reencrypt_evidence(
        initial,
        original,
        target_key_id="key-b",
        target_key_version=2,
    )
    active = PrivateEvidenceStore(
        initial.root,
        key_provider=KeyProvider(),
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
        key_id="key-b",
        key_version=2,
    )
    return active, original, rotated, payload


def install_device_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_device_id(path: Path) -> int:
        parts = path.resolve().parts
        mapping = {
            "device-a": 2,
            "device-b": 3,
            "device-c": 4,
            "device-d": 5,
            "rotation-stage": 6,
        }
        for name, device_id in mapping.items():
            if name in parts:
                return device_id
        return 1

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
    store, original, rotated, payload = make_store(tmp_path)
    install_device_probe(monkeypatch)
    device_a = tmp_path / "device-a"
    device_b = tmp_path / "device-b"
    device_a.mkdir()
    device_b.mkdir()
    result = create_redundant_recovery_set(
        store,
        (
            device_a / "case-a.mvros-recovery",
            device_b / "case-b.mvros-recovery",
        ),
        passphrases=(OLD_A, OLD_B),
    )
    return store, original, rotated, payload, result


def test_recovery_set_record_is_canonical_digest_only_and_redundant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _original, _rotated, _payload, result = create_set(tmp_path, monkeypatch)

    records = write_redundant_recovery_set_records(
        result.recovery_set,
        result.member_paths,
    )
    first = records[0].read_bytes()
    second = records[1].read_bytes()
    assert first == second
    assert first == canonical_json(result.recovery_set.canonical_dict()) + b"\n"
    assert load_recovery_set_record(records[0]).recovery_set_id == (
        result.recovery_set.recovery_set_id
    )
    text = first.decode("utf-8")
    assert OLD_A not in text
    assert OLD_B not in text
    assert str(result.member_paths[0]) not in text
    assert str(result.member_paths[1]) not in text


def test_recovery_set_record_rejects_tamper_and_repository_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _original, _rotated, _payload, result = create_set(tmp_path, monkeypatch)
    record = tmp_path / "set.mvros-recovery-set.json"
    write_recovery_set_record(result.recovery_set, record)

    value = json.loads(record.read_text(encoding="utf-8"))
    value["unexpected"] = True
    record.write_bytes(canonical_json(value) + b"\n")
    with pytest.raises(PrivateEvidenceRecoveryOpsError, match="record is invalid"):
        load_recovery_set_record(record)

    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(PrivateEvidenceRecoveryOpsError, match="outside the public repository"):
        write_recovery_set_record(
            result.recovery_set,
            repo / "blocked.mvros-recovery-set.json",
            repo_root=repo,
        )


def test_operator_drill_keeps_machine_proof_separate_from_human_assertions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _original, _rotated, _payload, result = create_set(tmp_path, monkeypatch)
    assertions = RecoveryOperatorAssertionsV1(
        source_workstation_unavailable=True,
        network_disconnected=True,
        media_physically_separate=True,
        recovery_secrets_separately_custodied=True,
    )
    evidence = run_operator_recovery_drill(
        result.recovery_set,
        result.member_paths,
        (tmp_path / "restore-a", tmp_path / "restore-b"),
        passphrases=(OLD_A, OLD_B),
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
        assertions=assertions,
    )
    validate_operator_evidence_shape(evidence)
    assert evidence.machine_receipt.result == "PASS"
    assert evidence.status == "OPERATOR_ATTESTED_MACHINE_PASS"
    assert evidence.assertion_class == OPERATOR_ASSERTION_CLASS

    record = tmp_path / "drill.mvros-recovery-drill.json"
    write_operator_drill_evidence(evidence, record)
    text = record.read_text(encoding="utf-8")
    assert OLD_A not in text
    assert OLD_B not in text
    assert str(result.member_paths[0]) not in text
    assert str(tmp_path / "restore-a") not in text


def test_incomplete_operator_assertions_never_become_attested_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _original, _rotated, _payload, result = create_set(tmp_path, monkeypatch)
    evidence = run_operator_recovery_drill(
        result.recovery_set,
        result.member_paths,
        (tmp_path / "restore-a", tmp_path / "restore-b"),
        passphrases=(OLD_A, OLD_B),
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
        assertions=RecoveryOperatorAssertionsV1(
            source_workstation_unavailable=True,
            network_disconnected=False,
            media_physically_separate=True,
            recovery_secrets_separately_custodied=True,
        ),
    )
    validate_operator_evidence_shape(evidence)
    assert evidence.status == "INCOMPLETE_OPERATOR_ASSERTIONS"


def test_secret_rotation_from_one_surviving_member_preserves_snapshot_and_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, original, rotated, payload, result = create_set(tmp_path, monkeypatch)
    shutil.rmtree(result.member_paths[1])
    staging_parent = tmp_path / "rotation-stage"
    staging_parent.mkdir()
    device_c = tmp_path / "device-c"
    device_d = tmp_path / "device-d"
    device_c.mkdir()
    device_d.mkdir()

    rotated_set = rotate_recovery_set_secrets(
        result.recovery_set,
        source_slot="A",
        source_capsule=result.member_paths[0],
        old_passphrase=OLD_A,
        staging_parent=staging_parent,
        new_destinations=(
            device_c / "rotated-a.mvros-recovery",
            device_d / "rotated-b.mvros-recovery",
        ),
        new_passphrases=(NEW_A, NEW_B),
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
    )

    assert rotated_set.receipt.result == "PASS"
    assert rotated_set.receipt.snapshot_digest == result.recovery_set.snapshot_digest
    assert rotated_set.receipt.old_recovery_set_id == result.recovery_set.recovery_set_id
    assert rotated_set.receipt.new_recovery_set_id != result.recovery_set.recovery_set_id
    assert not any(staging_parent.iterdir())

    restored = restore_recovery_set_member(
        rotated_set.recovery_set_result.recovery_set,
        slot="B",
        capsule_path=rotated_set.recovery_set_result.member_paths[1],
        passphrase=NEW_B,
        destination=tmp_path / "rotated-restore",
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
    )
    assert restored.store.read(original) == payload
    assert restored.store.read(rotated) == payload

    receipt_path = tmp_path / "rotation.mvros-recovery-rotation.json"
    write_rotation_receipt(rotated_set.receipt, receipt_path)
    receipt_text = receipt_path.read_text(encoding="utf-8")
    assert OLD_A not in receipt_text
    assert NEW_A not in receipt_text
    assert NEW_B not in receipt_text
    assert str(result.member_paths[0]) not in receipt_text


def test_secret_rotation_rejects_old_passphrase_reuse_before_restore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _original, _rotated, _payload, result = create_set(tmp_path, monkeypatch)
    staging_parent = tmp_path / "rotation-stage"
    staging_parent.mkdir()
    device_c = tmp_path / "device-c"
    device_d = tmp_path / "device-d"
    device_c.mkdir()
    device_d.mkdir()

    with pytest.raises(PrivateEvidenceRecoveryOpsError, match="must not reuse"):
        rotate_recovery_set_secrets(
            result.recovery_set,
            source_slot="A",
            source_capsule=result.member_paths[0],
            old_passphrase=OLD_A,
            staging_parent=staging_parent,
            new_destinations=(
                device_c / "rotated-a.mvros-recovery",
                device_d / "rotated-b.mvros-recovery",
            ),
            new_passphrases=(OLD_A, NEW_B),
            authorization=auth(),
            tenant_id="tenant-a",
            case_id="CASE-A",
        )
    assert not (device_c / "rotated-a.mvros-recovery").exists()
    assert not (device_d / "rotated-b.mvros-recovery").exists()


def test_wrong_surviving_passphrase_leaves_no_rotation_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _original, _rotated, _payload, result = create_set(tmp_path, monkeypatch)
    staging_parent = tmp_path / "rotation-stage"
    staging_parent.mkdir()
    device_c = tmp_path / "device-c"
    device_d = tmp_path / "device-d"
    device_c.mkdir()
    device_d.mkdir()

    with pytest.raises(RuntimeError, match="passphrase|authentication"):
        rotate_recovery_set_secrets(
            result.recovery_set,
            source_slot="A",
            source_capsule=result.member_paths[0],
            old_passphrase="synthetic-definitely-wrong-passphrase",
            staging_parent=staging_parent,
            new_destinations=(
                device_c / "rotated-a.mvros-recovery",
                device_d / "rotated-b.mvros-recovery",
            ),
            new_passphrases=(NEW_A, NEW_B),
            authorization=auth(),
            tenant_id="tenant-a",
            case_id="CASE-A",
        )
    assert not any(staging_parent.iterdir())
    assert not (device_c / "rotated-a.mvros-recovery").exists()
    assert not (device_d / "rotated-b.mvros-recovery").exists()
