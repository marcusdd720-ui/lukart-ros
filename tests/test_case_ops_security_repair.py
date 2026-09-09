from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.case_ingestion import IngestionError, ingest_directory
from core.enterprise.contracts import AuthorizationContext, Permission
from core.local_case_store import PrivacyViolation, ensure_data_root, save_source_snapshot
from core.private_evidence_rotation_v1 import reencrypt_evidence
from core.private_evidence_v1 import EvidenceKind, PrivateEvidenceError, PrivateEvidenceStore


class RotatingKeyProvider:
    def get_key(self, key_id: str, key_version: int) -> bytes:
        keys = {
            ("key-a", 1): b"A" * 32,
            ("key-b", 2): b"B" * 32,
        }
        try:
            return keys[(key_id, key_version)]
        except KeyError as exc:
            raise PrivateEvidenceError("synthetic key not found") from exc


def _authorization(case_id: str = "CASE-ROTATE") -> AuthorizationContext:
    return AuthorizationContext(
        subject_id="synthetic-case-ops-worker",
        tenant_id="synthetic-tenant",
        roles=("case-worker",),
        permissions=(Permission.EVIDENCE_READ, Permission.EVIDENCE_WRITE),
        case_ids=(case_id,),
    )


def _symlink(link: Path, target: Path, *, directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError:
        pytest.skip("symlink creation unavailable")


def test_ingestion_rejects_symlinked_source_root_before_resolve(tmp_path: Path) -> None:
    actual = tmp_path / "actual-source"
    actual.mkdir()
    (actual / "synthetic.txt").write_text("synthetic", encoding="utf-8")
    linked = tmp_path / "source-link"
    _symlink(linked, actual, directory=True)

    with pytest.raises(IngestionError, match="source directory must use a non-symlink path"):
        ingest_directory(
            tmp_path / "CASE-ROTATE",
            linked,
            authorization=_authorization(),
            key_provider=RotatingKeyProvider(),
            tenant_id="synthetic-tenant",
            key_id="key-a",
        )


def test_ingestion_rejects_symlinked_parent_component(tmp_path: Path) -> None:
    actual_parent = tmp_path / "actual-parent"
    source = actual_parent / "source"
    source.mkdir(parents=True)
    (source / "synthetic.txt").write_text("synthetic", encoding="utf-8")
    linked_parent = tmp_path / "linked-parent"
    _symlink(linked_parent, actual_parent, directory=True)

    with pytest.raises(IngestionError, match="source directory must use a non-symlink path"):
        ingest_directory(
            tmp_path / "CASE-ROTATE",
            linked_parent / "source",
            authorization=_authorization(),
            key_provider=RotatingKeyProvider(),
            tenant_id="synthetic-tenant",
            key_id="key-a",
        )


def test_ingestion_rejects_symlinked_case_root(tmp_path: Path) -> None:
    actual_case = tmp_path / "actual-case"
    actual_case.mkdir()
    linked_case = tmp_path / "linked-case"
    _symlink(linked_case, actual_case, directory=True)
    source = tmp_path / "source"
    source.mkdir()
    (source / "synthetic.txt").write_text("synthetic", encoding="utf-8")

    with pytest.raises(IngestionError, match="case directory must use a non-symlink path"):
        ingest_directory(
            linked_case,
            source,
            authorization=_authorization(actual_case.name),
            key_provider=RotatingKeyProvider(),
            tenant_id="synthetic-tenant",
            key_id="key-a",
        )


def test_data_root_rejects_symlink_before_resolution(tmp_path: Path) -> None:
    actual = tmp_path / "actual-data"
    actual.mkdir()
    linked = tmp_path / "data-link"
    _symlink(linked, actual, directory=True)

    with pytest.raises(PrivacyViolation, match="data root must use a non-symlink path"):
        ensure_data_root(linked)


def test_snapshot_rejects_source_through_symlinked_parent(tmp_path: Path) -> None:
    actual_parent = tmp_path / "actual-parent"
    actual_parent.mkdir()
    source = actual_parent / "synthetic.txt"
    source.write_text("synthetic", encoding="utf-8")
    linked_parent = tmp_path / "linked-parent"
    _symlink(linked_parent, actual_parent, directory=True)

    with pytest.raises(PrivacyViolation, match="source must use a non-symlink path"):
        save_source_snapshot(
            "CASE-ROTATE",
            linked_parent / "synthetic.txt",
            authorization=_authorization(),
            key_provider=RotatingKeyProvider(),
            tenant_id="synthetic-tenant",
            key_id="key-a",
            source_ref="synthetic-source",
            data_root=tmp_path / "private-data",
        )


def test_key_rotation_preserves_evidence_identity_and_source_provenance(tmp_path: Path) -> None:
    store = PrivateEvidenceStore(
        tmp_path / "private-evidence",
        key_provider=RotatingKeyProvider(),
        authorization=_authorization(),
        tenant_id="synthetic-tenant",
        case_id="CASE-ROTATE",
        key_id="key-a",
        key_version=1,
    )
    payload = b"synthetic evidence bytes"
    imported = store.import_bytes(
        payload,
        source_ref="synthetic-logical-source",
        kind=EvidenceKind.SECONDARY,
        media_type="application/pdf",
    )

    rotated = reencrypt_evidence(
        store,
        imported,
        target_key_id="key-b",
        target_key_version=2,
    )

    assert rotated.evidence_id == imported.evidence_id
    assert rotated.manifest_digest != imported.manifest_digest
    assert rotated.receipt_digest != imported.receipt_digest
    assert rotated.envelope_path != imported.envelope_path
    assert store.read(imported) == payload
    assert store.read(rotated) == payload

    old_manifest = json.loads(imported.manifest_path.read_text(encoding="utf-8"))
    new_manifest = json.loads(rotated.manifest_path.read_text(encoding="utf-8"))
    receipt = json.loads(rotated.receipt_path.read_text(encoding="utf-8"))
    assert new_manifest["source_ref_digest"] == old_manifest["source_ref_digest"]
    assert new_manifest["evidence_kind"] == "SECONDARY"
    assert new_manifest["media_type"] == "application/pdf"
    assert new_manifest["key_id"] == "key-b"
    assert new_manifest["key_version"] == 2
    assert receipt["operation"] == "REENCRYPTED"
    assert receipt["previous_manifest_digest"] == imported.manifest_digest
    assert receipt["manifest_digest"] == rotated.manifest_digest

    reference = store.ccl_reference(rotated)
    assert reference["evidence_id"] == imported.evidence_id
    assert reference["receipt_digest"] == rotated.receipt_digest


def test_key_rotation_rejects_same_key_identity(tmp_path: Path) -> None:
    store = PrivateEvidenceStore(
        tmp_path / "private-evidence",
        key_provider=RotatingKeyProvider(),
        authorization=_authorization(),
        tenant_id="synthetic-tenant",
        case_id="CASE-ROTATE",
        key_id="key-a",
        key_version=1,
    )
    imported = store.import_bytes(b"synthetic", source_ref="synthetic-source")

    with pytest.raises(PrivateEvidenceError, match="target must differ"):
        reencrypt_evidence(
            store,
            imported,
            target_key_id="key-a",
            target_key_version=1,
        )
