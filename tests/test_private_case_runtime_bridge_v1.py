from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from core.case_ingestion import ingest_directory
from core.case_ledger.ledger import CanonicalCaseLedger
from core.enterprise.contracts import AuthorizationContext, Permission
from core.p3.contracts import RuntimeIdentity
from core.private_case_runtime_bridge_v1 import (
    RUNTIME_INVENTORY_SOURCE_REF,
    PrivateCaseRuntimeBridgeError,
    load_verified_projection,
    migrate_legacy_inventory,
    register_projection_in_ccl,
)
from core.private_evidence_keyfile_v1 import LocalFileEvidenceKeyProvider
from core.private_evidence_v1 import PrivateEvidenceError, PrivateEvidenceStore, digest_hex, opaque_digest
from knowledge.models.case_manifest import CaseManifest
from knowledge.models.local_case_runtime import build_local_case_workspace


class KeyProvider:
    def get_key(self, key_id: str, key_version: int) -> bytes:
        if key_id != "key-main" or key_version != 1:
            raise PrivateEvidenceError("synthetic key unavailable")
        return b"K" * 32


def authorization(
    case_id: str = "CASE-A",
    *,
    case_write: bool = False,
    tenant_id: str = "tenant-a",
) -> AuthorizationContext:
    permissions = [Permission.EVIDENCE_READ, Permission.EVIDENCE_WRITE]
    if case_write:
        permissions.append(Permission.CASE_WRITE)
    return AuthorizationContext(
        subject_id="synthetic-local-operator",
        tenant_id=tenant_id,
        roles=("case-worker",),
        permissions=tuple(permissions),
        case_ids=(case_id,),
    )


def evidence_store(case_dir: Path, *, auth: AuthorizationContext | None = None) -> PrivateEvidenceStore:
    return PrivateEvidenceStore(
        case_dir / ".private-evidence",
        key_provider=KeyProvider(),
        authorization=auth or authorization(case_dir.name),
        tenant_id=(auth.tenant_id if auth else "tenant-a"),
        case_id=case_dir.name,
        key_id="key-main",
    )


def create_case(tmp_path: Path, *, documents: int = 2) -> tuple[Path, PrivateEvidenceStore]:
    case_dir = tmp_path / "cases" / "CASE-A"
    case_dir.mkdir(parents=True)
    CaseManifest(case_key="CASE-A", case_id="CASE-A").save(case_dir)
    source = tmp_path / "source"
    source.mkdir()
    for index in range(1, documents + 1):
        (source / f"synthetic-{index}.txt").write_text(
            f"Synthetic evidence {index}.\n", encoding="utf-8"
        )
    ingest_directory(
        case_dir,
        source,
        authorization=authorization(),
        key_provider=KeyProvider(),
        tenant_id="tenant-a",
        key_id="key-main",
    )
    return case_dir, evidence_store(case_dir)


def runtime_identity(projection_id: str) -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="a" * 40,
        schema_version="case-ops-02-test",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        evidence_digests=(digest_hex(projection_id),),
        evidence_inventory_declared=True,
    )


def test_projection_is_deterministic_and_ignores_plaintext_inventory_mutation(tmp_path: Path) -> None:
    case_dir, store = create_case(tmp_path)
    first = load_verified_projection(store)

    compatibility = case_dir / "document_inventory.json"
    compatibility.write_text("[]\n", encoding="utf-8")
    second = load_verified_projection(store)
    workspace = build_local_case_workspace(
        "CASE-A", data_root=tmp_path, evidence_store=store
    )

    assert second == first
    assert second.projection_id == first.projection_id
    assert len(second.documents) == 2
    assert len(workspace.case.evidence_items) == 2


def test_runtime_inventory_source_index_tamper_fails_closed(tmp_path: Path) -> None:
    _case_dir, store = create_case(tmp_path, documents=1)
    source_digest = opaque_digest(RUNTIME_INVENTORY_SOURCE_REF)
    value = digest_hex(source_digest)
    index_path = store.root / "source-index" / value[:2] / f"{value}.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["evidence_id"] = "sha256:" + "0" * 64
    index_path.write_text(json.dumps(index), encoding="utf-8")

    with pytest.raises(PrivateCaseRuntimeBridgeError):
        load_verified_projection(store)


def test_missing_encrypted_runtime_inventory_never_falls_back_to_plaintext(tmp_path: Path) -> None:
    case_dir, store = create_case(tmp_path, documents=1)
    source_digest = opaque_digest(RUNTIME_INVENTORY_SOURCE_REF)
    value = digest_hex(source_digest)
    index_path = store.root / "source-index" / value[:2] / f"{value}.json"
    index_path.unlink()

    with pytest.raises(PrivateCaseRuntimeBridgeError, match="required private evidence object"):
        load_verified_projection(store)
    with pytest.raises(ValueError, match="runtime verification failed"):
        build_local_case_workspace("CASE-A", data_root=tmp_path, evidence_store=store)
    assert (case_dir / "document_inventory.json").is_file()


def test_legacy_inventory_migration_is_verified_and_idempotent(tmp_path: Path) -> None:
    case_dir, store = create_case(tmp_path, documents=1)
    source_digest = opaque_digest(RUNTIME_INVENTORY_SOURCE_REF)
    value = digest_hex(source_digest)
    index_path = store.root / "source-index" / value[:2] / f"{value}.json"
    index_path.unlink()

    first = migrate_legacy_inventory(store, case_dir / "document_inventory.json")
    second = migrate_legacy_inventory(store, case_dir / "document_inventory.json")

    assert first == second == load_verified_projection(store)


def test_legacy_inventory_slot_substitution_is_rejected_before_migration(tmp_path: Path) -> None:
    case_dir, store = create_case(tmp_path, documents=2)
    source_digest = opaque_digest(RUNTIME_INVENTORY_SOURCE_REF)
    value = digest_hex(source_digest)
    index_path = store.root / "source-index" / value[:2] / f"{value}.json"
    index_path.unlink()

    inventory_path = case_dir / "document_inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory[0]["evidence_id"], inventory[1]["evidence_id"] = (
        inventory[1]["evidence_id"],
        inventory[0]["evidence_id"],
    )
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")

    with pytest.raises(PrivateCaseRuntimeBridgeError):
        migrate_legacy_inventory(store, inventory_path)


def test_ccl_registration_requires_case_write_and_runtime_projection_binding(tmp_path: Path) -> None:
    _case_dir, store = create_case(tmp_path, documents=1)
    projection = load_verified_projection(store)

    with CanonicalCaseLedger(tmp_path / "ledger.db") as ledger:
        with pytest.raises(PrivateCaseRuntimeBridgeError, match="authorization denied"):
            register_projection_in_ccl(
                ledger=ledger,
                projection=projection,
                runtime_identity=runtime_identity(projection.projection_id),
                authorization=authorization(case_write=False),
                expected_head=None,
            )

        unbound = RuntimeIdentity(
            code_sha="a" * 40,
            schema_version="case-ops-02-test",
            config_digest="b" * 64,
            corpus_digest="c" * 64,
            evidence_digests=("d" * 64,),
            evidence_inventory_declared=True,
        )
        with pytest.raises(PrivateCaseRuntimeBridgeError, match="does not bind"):
            register_projection_in_ccl(
                ledger=ledger,
                projection=projection,
                runtime_identity=unbound,
                authorization=authorization(case_write=True),
                expected_head=None,
            )

        event = register_projection_in_ccl(
            ledger=ledger,
            projection=projection,
            runtime_identity=runtime_identity(projection.projection_id),
            authorization=authorization(case_write=True),
            expected_head=None,
        )

    serialized = json.dumps(event.canonical_dict(), sort_keys=True)
    assert event.event_type == "private.evidence.projection.registered.v1"
    assert projection.projection_id in serialized
    assert "Synthetic evidence" not in serialized
    assert "synthetic-1.txt" not in serialized


def test_local_key_file_provider_is_exact_identity_and_rejects_broad_posix_mode(tmp_path: Path) -> None:
    key_file = tmp_path / "evidence.key"
    key_file.write_bytes(b"Z" * 32)
    if os.name != "nt":
        key_file.chmod(0o600)
    provider = LocalFileEvidenceKeyProvider(key_file, key_id="local-key", key_version=3)

    assert provider.get_key("local-key", 3) == b"Z" * 32
    with pytest.raises(PrivateEvidenceError, match="identity is unavailable"):
        provider.get_key("other-key", 3)

    if os.name != "nt":
        key_file.chmod(0o644)
        with pytest.raises(PrivateEvidenceError, match="permissions are too broad"):
            provider.get_key("local-key", 3)
