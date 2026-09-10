from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.case_ingestion import ingest_directory
from core.case_ledger import CanonicalCaseLedger, CaseId, CaseLedgerBundle
from core.enterprise.contracts import AuthorizationContext, Permission
from core.p3.contracts import RuntimeIdentity, canonical_json
from core.private_case_pilot_v1 import (
    PILOT_INPUT_SYNTHETIC,
    PrivateCasePilotError,
    load_ledger_bundle_file,
    load_runtime_identity_mapping,
    run_private_local_pilot,
    write_pilot_receipt,
)
from core.private_case_runtime_bridge_v1 import (
    load_verified_projection,
    register_projection_in_ccl,
)
from core.private_evidence_v1 import PrivateEvidenceError, PrivateEvidenceStore, digest_hex
from knowledge.models.case_manifest import CaseManifest


class KeyProvider:
    def get_key(self, key_id: str, key_version: int) -> bytes:
        if (key_id, key_version) != ("key-main", 1):
            raise PrivateEvidenceError("synthetic key unavailable")
        return b"K" * 32


def auth() -> AuthorizationContext:
    return AuthorizationContext(
        subject_id="synthetic-case-ops-06",
        tenant_id="tenant-a",
        roles=("case-worker",),
        permissions=(
            Permission.EVIDENCE_READ,
            Permission.EVIDENCE_WRITE,
            Permission.CASE_WRITE,
        ),
        case_ids=("CASE-A",),
    )


def runtime(projection_id: str) -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="a" * 40,
        schema_version="case-ops-06-pilot-v1",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        provider_identities=(),
        plugin_identities=(),
        input_digests=("d" * 64,),
        evidence_digests=(digest_hex(projection_id),),
        provider_inventory_declared=True,
        plugin_inventory_declared=True,
        input_inventory_declared=True,
        evidence_inventory_declared=True,
        dependency_lock_digest="e" * 64,
        python_implementation="CPython",
        python_version="3.11.synthetic",
        platform_tag="synthetic-local",
        project_version="1.1.0.dev0",
        build_backend="synthetic-build-backend",
        execution_environment_declared=True,
    )


def make_case(
    tmp_path: Path,
) -> tuple[PrivateEvidenceStore, CaseLedgerBundle, RuntimeIdentity]:
    case_root = tmp_path / "cases" / "CASE-A"
    case_root.mkdir(parents=True)
    CaseManifest(case_key="CASE-A", case_id="CASE-A").save(case_root)
    source = tmp_path / "source"
    source.mkdir()
    (source / "private.txt").write_text(
        "TOP SECRET SYNTHETIC PRIVATE CASE CONTENT\n",
        encoding="utf-8",
    )
    ingest_directory(
        case_root,
        source,
        authorization=auth(),
        key_provider=KeyProvider(),
        tenant_id="tenant-a",
        key_id="key-main",
    )
    store = PrivateEvidenceStore(
        case_root / ".private-evidence",
        key_provider=KeyProvider(),
        authorization=auth(),
        tenant_id="tenant-a",
        case_id="CASE-A",
        key_id="key-main",
    )
    projection = load_verified_projection(store)
    identity = runtime(projection.projection_id)
    with CanonicalCaseLedger(tmp_path / "ledger.db") as ledger:
        event = register_projection_in_ccl(
            ledger=ledger,
            projection=projection,
            runtime_identity=identity,
            authorization=auth(),
            expected_head=None,
        )
        assert event.payload["projection_id"] == projection.projection_id
        bundle = ledger.export_case(CaseId("CASE-A"))
    return store, bundle, identity


def test_private_local_pilot_binds_evidence_ccl_product_and_replay(tmp_path: Path) -> None:
    store, bundle, identity = make_case(tmp_path)
    run = run_private_local_pilot(
        evidence_store=store,
        ledger_bundle=bundle,
        runtime_identity=identity,
        input_class=PILOT_INPUT_SYNTHETIC,
    )

    assert run.receipt.result == "PASS"
    assert run.receipt.ccl_bundle_digest == bundle.bundle_digest.digest
    assert run.receipt.runtime_identity_digest == identity.digest()
    assert run.receipt.private_document_count == 1
    assert run.receipt.reasoning_outcome == "CONCLUDE"
    run.verify()


def test_pilot_is_deterministic_for_same_exact_inputs(tmp_path: Path) -> None:
    store, bundle, identity = make_case(tmp_path)
    first = run_private_local_pilot(
        evidence_store=store,
        ledger_bundle=bundle,
        runtime_identity=identity,
        input_class=PILOT_INPUT_SYNTHETIC,
    )
    second = run_private_local_pilot(
        evidence_store=store,
        ledger_bundle=bundle,
        runtime_identity=identity,
        input_class=PILOT_INPUT_SYNTHETIC,
    )
    assert first.receipt == second.receipt
    assert first.receipt.receipt_id == second.receipt.receipt_id


def test_pilot_receipt_is_digest_only_and_refuses_repository_output(tmp_path: Path) -> None:
    store, bundle, identity = make_case(tmp_path / "work")
    run = run_private_local_pilot(
        evidence_store=store,
        ledger_bundle=bundle,
        runtime_identity=identity,
        input_class=PILOT_INPUT_SYNTHETIC,
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "pilot.mvros-private-pilot.json"
    write_pilot_receipt(run.receipt, outside, repo_root=repo)
    text = outside.read_text(encoding="utf-8")
    assert "TOP SECRET" not in text
    assert "private.txt" not in text
    assert str(store.root) not in text

    with pytest.raises(PrivateCasePilotError, match="outside the public repository"):
        write_pilot_receipt(
            run.receipt,
            repo / "blocked.mvros-private-pilot.json",
            repo_root=repo,
        )


def test_pilot_rejects_bundle_without_exact_projection_registration(tmp_path: Path) -> None:
    store, _bundle, identity = make_case(tmp_path)
    empty = CaseLedgerBundle.build(case_id=CaseId("CASE-A"), events=())
    with pytest.raises(PrivateCasePilotError, match="exactly one event"):
        run_private_local_pilot(
            evidence_store=store,
            ledger_bundle=empty,
            runtime_identity=identity,
            input_class=PILOT_INPUT_SYNTHETIC,
        )


def test_pilot_rejects_runtime_not_bound_to_projection(tmp_path: Path) -> None:
    store, bundle, identity = make_case(tmp_path)
    wrong = replace(identity, evidence_digests=("f" * 64,))
    with pytest.raises(PrivateCasePilotError, match="does not bind private projection"):
        run_private_local_pilot(
            evidence_store=store,
            ledger_bundle=bundle,
            runtime_identity=wrong,
            input_class=PILOT_INPUT_SYNTHETIC,
        )


def test_pilot_rejects_incomplete_runtime_identity(tmp_path: Path) -> None:
    store, bundle, identity = make_case(tmp_path)
    incomplete = replace(identity, provider_inventory_declared=False)
    with pytest.raises(PrivateCasePilotError, match="incomplete for replay"):
        run_private_local_pilot(
            evidence_store=store,
            ledger_bundle=bundle,
            runtime_identity=incomplete,
            input_class=PILOT_INPUT_SYNTHETIC,
        )


def test_external_ccl_loader_rejects_unbound_fields(tmp_path: Path) -> None:
    _store, bundle, _identity = make_case(tmp_path / "work")
    path = tmp_path / "bundle.json"
    value = bundle.canonical_dict()
    value["unexpected"] = "ignored-by-base-contract"
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")
    with pytest.raises(PrivateCasePilotError, match="unbound or non-canonical"):
        load_ledger_bundle_file(path)


def test_runtime_identity_parser_rejects_unknown_and_incomplete_shape(tmp_path: Path) -> None:
    store, _bundle, identity = make_case(tmp_path)
    projection = load_verified_projection(store)
    assert digest_hex(projection.projection_id) in identity.evidence_digests
    value = identity.canonical_dict()
    parsed = load_runtime_identity_mapping(value)
    assert parsed == identity
    value["unexpected"] = True
    with pytest.raises(PrivateCasePilotError, match="unknown or missing"):
        load_runtime_identity_mapping(value)
