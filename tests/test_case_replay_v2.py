from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.case_ledger import CanonicalCaseLedger, CaseId, ObjectId
from core.case_replay_v2 import (
    CASE_REPLAY_BUNDLE_SCHEMA_V2,
    CaseReplayBundleV2,
    CaseReplayV2Error,
    compare_case_replay_manifests,
    verify_case_replay_bundle,
)
from core.p3.contracts import ReplayRelation, RuntimeIdentity, canonical_json
from core.p3.versioning import CaseMigrationRegistry, MigrationStep
from knowledge.epistemic import KnowledgeStatus
from knowledge.epistemic_assertions import EpistemicLedgerService, EpistemicPolicyV2
from knowledge.evidence_trust_graph import TrustPolicyV1


def _runtime(*, schema_version: str = "case.v1", code: str = "a") -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha=code * 40,
        schema_version=schema_version,
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        provider_identities=("provider-a@1",),
        plugin_identities=(),
        input_digests=("d" * 64,),
        evidence_digests=("e" * 64,),
        provider_inventory_declared=True,
        plugin_inventory_declared=True,
        input_inventory_declared=True,
        evidence_inventory_declared=True,
        dependency_lock_digest="f" * 64,
        python_implementation="CPython",
        python_version="3.13.7",
        platform_tag="linux-x86_64",
        project_version="1.1.0.dev0",
        build_backend="lukart_build_backend",
        execution_environment_declared=True,
    )


def _incomplete_runtime() -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="a" * 40,
        schema_version="case.v1",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        provider_identities=("provider-a@1",),
        provider_inventory_declared=True,
    )


def _registry(*, with_upgrade: bool = False) -> CaseMigrationRegistry:
    registry = CaseMigrationRegistry()
    if with_upgrade:
        registry.register(
            MigrationStep(
                source_version="case.v1",
                target_version="case.v2",
                migrate=lambda payload: {**payload, "schema_upgraded": True},
            )
        )
    return registry


def _bundle(
    tmp_path: Path,
    *,
    runtime: RuntimeIdentity | None = None,
    registry: CaseMigrationRegistry | None = None,
) -> CaseReplayBundleV2:
    case_id = CaseId("CASE-REPLAY-001")
    with CanonicalCaseLedger(tmp_path / "canonical.db") as ledger:
        if ledger.head(case_id) is None:
            service = EpistemicLedgerService(ledger)
            service.create_assertion(
                case_id=case_id,
                subject_id=ObjectId("OBJ-1"),
                assertion_type="claim.v1",
                content={"value": "fixture"},
                initial_status=KnowledgeStatus.CLAIM,
                evidence_refs=(),
                runtime_identity=_runtime(),
                expected_head=None,
            )
        ledger_bundle = ledger.export_case(case_id)

    return CaseReplayBundleV2.build(
        ledger_bundle=ledger_bundle,
        runtime_identity=runtime or _runtime(),
        migration_registry=registry or _registry(),
        epistemic_policy=EpistemicPolicyV2.reference(),
        trust_policy=TrustPolicyV1.reference(),
    )


def _serialized(bundle: CaseReplayBundleV2) -> dict[str, object]:
    decoded = json.loads(canonical_json(bundle.canonical_dict()))
    assert isinstance(decoded, dict)
    return decoded


def test_offline_bundle_rebuilds_exact_epistemic_and_trust_projection(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)

    verification = verify_case_replay_bundle(_serialized(bundle))

    assert verification.manifest_identity == bundle.manifest.manifest_identity
    assert verification.ledger_head == bundle.manifest.ledger_head
    assert (
        verification.epistemic_projection_identity
        == bundle.manifest.epistemic_projection_identity
    )
    assert verification.trust_graph_identity == bundle.manifest.trust_graph_identity
    assert verification.runtime_identity_digest == bundle.manifest.runtime_identity_digest
    bundle.verify()


def test_identical_manifest_requires_complete_exact_identity(tmp_path: Path) -> None:
    first = _bundle(tmp_path)
    second = _bundle(tmp_path)

    comparison = compare_case_replay_manifests(
        first.manifest,
        second.manifest,
        migration_registry=_registry(),
    )

    assert comparison.relation is ReplayRelation.IDENTICAL
    assert comparison.differing_fields == ()


def test_incomplete_runtime_cannot_create_replay_bundle(tmp_path: Path) -> None:
    with pytest.raises(CaseReplayV2Error, match="incomplete"):
        _bundle(tmp_path, runtime=_incomplete_runtime())


def test_code_identity_change_is_not_identical_replay(tmp_path: Path) -> None:
    first = _bundle(tmp_path, runtime=_runtime(code="a"))
    second = _bundle(tmp_path, runtime=_runtime(code="1"))

    comparison = compare_case_replay_manifests(
        first.manifest,
        second.manifest,
        migration_registry=_registry(),
    )

    assert comparison.relation is ReplayRelation.DIFFERENT
    assert "runtime_identity_digest" in comparison.differing_fields


def test_cross_version_comparison_requires_explicit_bound_migration_path(tmp_path: Path) -> None:
    baseline = _bundle(tmp_path, runtime=_runtime(schema_version="case.v1"))
    registry = _registry(with_upgrade=True)
    candidate = _bundle(
        tmp_path,
        runtime=_runtime(schema_version="case.v2"),
        registry=registry,
    )

    comparison = compare_case_replay_manifests(
        baseline.manifest,
        candidate.manifest,
        migration_registry=registry,
    )

    assert comparison.relation is ReplayRelation.CROSS_VERSION_COMPARABLE
    assert comparison.migration_path == ("case.v1", "case.v2")
    assert "case_schema_version" in comparison.differing_fields


def test_unknown_migration_path_fails_closed(tmp_path: Path) -> None:
    baseline = _bundle(tmp_path, runtime=_runtime(schema_version="case.v1"))
    empty = _registry()
    candidate = _bundle(
        tmp_path,
        runtime=_runtime(schema_version="case.v2"),
        registry=empty,
    )

    with pytest.raises(CaseReplayV2Error, match="no migration path"):
        compare_case_replay_manifests(
            baseline.manifest,
            candidate.manifest,
            migration_registry=empty,
        )


def test_wrong_registry_identity_fails_cross_version_comparison(tmp_path: Path) -> None:
    baseline = _bundle(tmp_path, runtime=_runtime(schema_version="case.v1"))
    bound_registry = _registry(with_upgrade=True)
    candidate = _bundle(
        tmp_path,
        runtime=_runtime(schema_version="case.v2"),
        registry=bound_registry,
    )

    with pytest.raises(CaseReplayV2Error, match="not bound to supplied migration registry"):
        compare_case_replay_manifests(
            baseline.manifest,
            candidate.manifest,
            migration_registry=_registry(),
        )


def test_tampered_ledger_event_is_rejected_offline(tmp_path: Path) -> None:
    raw = _serialized(_bundle(tmp_path))
    ledger = raw["ledger_bundle"]
    assert isinstance(ledger, dict)
    events = ledger["events"]
    assert isinstance(events, list)
    event = events[0]
    assert isinstance(event, dict)
    event["payload"] = {"tampered": True}

    with pytest.raises((CaseReplayV2Error, ValueError)):
        verify_case_replay_bundle(raw)


def test_tampered_policy_snapshot_is_rejected_offline(tmp_path: Path) -> None:
    raw = _serialized(_bundle(tmp_path))
    policy = raw["trust_policy"]
    assert isinstance(policy, dict)
    policy["attestation_semantics"] = "attestation-is-truth"

    with pytest.raises(CaseReplayV2Error, match="canonical policy"):
        verify_case_replay_bundle(raw)


def test_tampered_migration_registry_snapshot_is_rejected_offline(tmp_path: Path) -> None:
    raw = _serialized(_bundle(tmp_path))
    registry = raw["migration_registry"]
    assert isinstance(registry, dict)
    registry["steps"] = [{"source_version": "forged", "target_version": "case.v99"}]

    with pytest.raises(CaseReplayV2Error, match="migration_registry_digest"):
        verify_case_replay_bundle(raw)


def test_missing_runtime_declaration_is_rejected_offline(tmp_path: Path) -> None:
    raw = _serialized(_bundle(tmp_path))
    runtime = raw["runtime_identity"]
    assert isinstance(runtime, dict)
    declarations = runtime["inventories_declared"]
    assert isinstance(declarations, dict)
    declarations["evidence"] = False

    with pytest.raises(CaseReplayV2Error, match="incomplete"):
        verify_case_replay_bundle(raw)


def test_unknown_bundle_schema_fails_closed(tmp_path: Path) -> None:
    raw = _serialized(_bundle(tmp_path))
    assert raw["schema"] == CASE_REPLAY_BUNDLE_SCHEMA_V2
    raw["schema"] = "lukart.case-replay-bundle.v99"

    with pytest.raises(CaseReplayV2Error, match="unsupported replay bundle schema"):
        verify_case_replay_bundle(raw)


def test_evidence_digest_inventory_is_manifest_bound(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    assert bundle.manifest.evidence_digests == ("e" * 64,)

    raw = _serialized(bundle)
    manifest = raw["manifest"]
    assert isinstance(manifest, dict)
    manifest["evidence_digests"] = ["9" * 64]

    with pytest.raises(CaseReplayV2Error):
        verify_case_replay_bundle(raw)


def test_case_replay_module_has_no_canonical_ledger_write_path() -> None:
    source = Path("core/case_replay_v2.py").read_text(encoding="utf-8")
    assert "CanonicalCaseLedger" not in source
    assert ".append_event(" not in source
