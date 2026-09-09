from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from core.case_ingestion import ingest_directory
from core.case_ledger.contracts import CaseId
from core.case_ledger.ledger import CanonicalCaseLedger
from core.enterprise.contracts import AuthorizationContext, Permission
from core.p3.contracts import RuntimeIdentity
from core.private_case_runtime_bridge_v1 import (
    PrivateCaseRuntimeBridgeError,
    load_verified_projection,
    register_projection_in_ccl,
)
from core.private_evidence_keyfile_v1 import LocalFileEvidenceKeyProvider
from core.private_evidence_v1 import PrivateEvidenceError, PrivateEvidenceStore, digest_hex
from knowledge.models.case_manifest import CaseManifest
from knowledge.models.local_case_runtime import build_local_case_workspace


class KeyProvider:
    def get_key(self, key_id: str, key_version: int) -> bytes:
        if (key_id, key_version) != ("key-main", 1):
            raise PrivateEvidenceError("synthetic key unavailable")
        return b"K" * 32


def auth(*, tenant: str = "tenant-a", case_write: bool = False) -> AuthorizationContext:
    permissions = [Permission.EVIDENCE_READ, Permission.EVIDENCE_WRITE]
    if case_write:
        permissions.append(Permission.CASE_WRITE)
    return AuthorizationContext(
        subject_id="synthetic-operator",
        tenant_id=tenant,
        roles=("case-worker",),
        permissions=tuple(permissions),
        case_ids=("CASE-A",),
    )


def make_case(tmp_path: Path, count: int = 2) -> tuple[Path, PrivateEvidenceStore]:
    case_dir = tmp_path / "cases" / "CASE-A"
    case_dir.mkdir(parents=True)
    CaseManifest(case_key="CASE-A", case_id="CASE-A").save(case_dir)
    source = tmp_path / "source"
    source.mkdir()
    for index in range(1, count + 1):
        (source / f"synthetic-{index}.txt").write_text(
            f"Synthetic evidence {index}.\n",
            encoding="utf-8",
        )
    ingest_directory(
        case_dir,
        source,
        authorization=auth(),
        key_provider=KeyProvider(),
        tenant_id="tenant-a",
        key_id="key-main",
    )
    store = PrivateEvidenceStore(
        case_dir / ".private-evidence",
        key_provider=KeyProvider(),
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
        key_id="key-main",
    )
    return case_dir, store


def runtime_identity(projection_id: str) -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="a" * 40,
        schema_version="case-ops-02-repair-test",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        evidence_digests=(digest_hex(projection_id),),
        evidence_inventory_declared=True,
    )


def test_runtime_projection_does_not_trust_compatibility_inventory(tmp_path: Path) -> None:
    case_dir, store = make_case(tmp_path)
    first = load_verified_projection(store)
    (case_dir / "document_inventory.json").write_text("[]\n", encoding="utf-8")
    second = load_verified_projection(store)
    workspace = build_local_case_workspace(
        "CASE-A",
        data_root=tmp_path,
        evidence_store=store,
    )

    assert second == first
    assert second.projection_id == first.projection_id
    assert len(workspace.case.evidence_items) == 2


def test_derivation_receipt_tamper_blocks_runtime_projection(tmp_path: Path) -> None:
    _case_dir, store = make_case(tmp_path, count=1)
    receipt_path = next((store.root / "derivations").rglob("*.json"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["replay_class"] = "SUBSTITUTED"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(PrivateCaseRuntimeBridgeError, match="verification failed"):
        load_verified_projection(store)


def test_missing_derivation_receipts_never_falls_back_to_inventory(tmp_path: Path) -> None:
    case_dir, store = make_case(tmp_path, count=1)
    for path in (store.root / "derivations").rglob("*.json"):
        path.unlink()

    with pytest.raises(PrivateCaseRuntimeBridgeError, match="receipts are missing"):
        load_verified_projection(store)
    with pytest.raises(ValueError, match="runtime verification failed"):
        build_local_case_workspace("CASE-A", data_root=tmp_path, evidence_store=store)
    assert (case_dir / "document_inventory.json").is_file()


def test_unexpected_derivation_layout_fails_closed(tmp_path: Path) -> None:
    _case_dir, store = make_case(tmp_path, count=1)
    rogue = store.root / "derivations" / "rogue.json"
    rogue.write_text("{}\n", encoding="utf-8")

    with pytest.raises(PrivateCaseRuntimeBridgeError, match="layout is invalid"):
        load_verified_projection(store)


def test_ccl_registration_requires_case_write_projection_binding_and_scope(tmp_path: Path) -> None:
    _case_dir, store = make_case(tmp_path, count=1)
    projection = load_verified_projection(store)
    identity = runtime_identity(projection.projection_id)

    with CanonicalCaseLedger(tmp_path / "ledger.db") as ledger:
        with pytest.raises(PrivateCaseRuntimeBridgeError, match="authorization denied"):
            register_projection_in_ccl(
                ledger=ledger,
                projection=projection,
                runtime_identity=identity,
                authorization=auth(case_write=False),
                expected_head=None,
            )
        with pytest.raises(PrivateCaseRuntimeBridgeError, match="scope digest mismatch"):
            register_projection_in_ccl(
                ledger=ledger,
                projection=projection,
                runtime_identity=identity,
                authorization=auth(tenant="tenant-b", case_write=True),
                expected_head=None,
            )
        unbound = RuntimeIdentity(
            code_sha="a" * 40,
            schema_version="case-ops-02-repair-test",
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
                authorization=auth(case_write=True),
                expected_head=None,
            )
        event = register_projection_in_ccl(
            ledger=ledger,
            projection=projection,
            runtime_identity=identity,
            authorization=auth(case_write=True),
            expected_head=None,
        )
        assert len(ledger.events(CaseId("CASE-A"))) == 1

    assert event.payload["projection_id"] == projection.projection_id
    payload_repr = repr(event.payload)
    assert "Synthetic evidence" not in payload_repr
    assert "synthetic-1.txt" not in payload_repr


def test_local_key_provider_rejects_wrong_identity_length_and_posix_permissions(
    tmp_path: Path,
) -> None:
    key_file = tmp_path / "key.mvros-key"
    key_file.write_bytes(b"Z" * 32)
    if os.name != "nt":
        key_file.chmod(0o600)
    provider = LocalFileEvidenceKeyProvider(key_file, key_id="local-key", key_version=2)
    assert provider.get_key("local-key", 2) == b"Z" * 32
    with pytest.raises(PrivateEvidenceError, match="identity is unavailable"):
        provider.get_key("wrong", 2)

    key_file.write_bytes(b"short")
    if os.name != "nt":
        key_file.chmod(0o600)
    with pytest.raises(PrivateEvidenceError, match="exactly 32"):
        provider.get_key("local-key", 2)

    if os.name != "nt":
        key_file.write_bytes(b"Z" * 32)
        key_file.chmod(0o644)
        with pytest.raises(PrivateEvidenceError, match="permissions are too broad"):
            provider.get_key("local-key", 2)
