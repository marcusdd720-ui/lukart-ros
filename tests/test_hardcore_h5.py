from __future__ import annotations

import pytest

from core.p3 import (
    CaseMigrationRegistry,
    MigrationStep,
    P3ContractError,
    ReplayRelation,
    RuntimeIdentity,
    VersionedCase,
)


def _identity(
    *,
    code: str = "a",
    schema: str = "v1",
    config: str = "b",
    corpus: str = "c",
    provider: str = "provider@1.0.0",
    plugin: str = "plugin@1.0.0",
    input_digest: str = "d",
    evidence_digest: str = "e",
    declared: bool = True,
) -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha=code * 40,
        schema_version=schema,
        config_digest=config * 64,
        corpus_digest=corpus * 64,
        provider_identities=(provider,),
        plugin_identities=(plugin,),
        input_digests=(input_digest * 64,),
        evidence_digests=(evidence_digest * 64,),
        provider_inventory_declared=declared,
        plugin_inventory_declared=declared,
        input_inventory_declared=declared,
        evidence_inventory_declared=declared,
    )


def test_h5_identical_requires_complete_exact_identity() -> None:
    registry = CaseMigrationRegistry()
    left = _identity()
    right = _identity()
    comparison = registry.compare_replay(left, right)
    assert comparison.relation is ReplayRelation.IDENTICAL
    assert comparison.differing_fields == ()
    assert comparison.semantic_divergence is False


def test_h5_legacy_or_partial_identity_never_becomes_identical() -> None:
    registry = CaseMigrationRegistry()
    left = _identity(declared=False)
    right = _identity(declared=False)
    comparison = registry.compare_replay(left, right)
    assert comparison.relation is ReplayRelation.INCOMPLETE
    assert comparison.unresolved
    assert "baseline.evidence_digests" in comparison.unresolved


def test_h5_same_schema_identity_drift_is_visible() -> None:
    registry = CaseMigrationRegistry()
    comparison = registry.compare_replay(_identity(), _identity(code="f"))
    assert comparison.relation is ReplayRelation.DIFFERENT
    assert "code_sha" in comparison.differing_fields


def test_h5_cross_version_replay_requires_explicit_migration_and_exposes_semantics() -> None:
    registry = CaseMigrationRegistry()
    registry.register(MigrationStep("v1", "v2", lambda payload: {**payload, "schema": "v2"}))
    source = VersionedCase.build(case_id="SYN", schema_version="v1", payload={"x": 1})
    report = registry.migrate(source, "v2")

    comparison = registry.compare_replay(
        _identity(schema="v1"),
        _identity(schema="v2", code="f"),
        migration_report=report,
    )
    assert comparison.relation is ReplayRelation.CROSS_VERSION_COMPARABLE
    assert comparison.migration_path == ("v1", "v2")
    assert comparison.semantic_divergence is True
    assert comparison.unresolved == ()
    assert "schema_version" in comparison.differing_fields


def test_h5_cross_version_without_semantic_measurement_stays_unresolved() -> None:
    registry = CaseMigrationRegistry()
    registry.register(MigrationStep("v1", "v2", lambda payload: dict(payload)))
    comparison = registry.compare_replay(_identity(schema="v1"), _identity(schema="v2"))
    assert comparison.relation is ReplayRelation.CROSS_VERSION_COMPARABLE
    assert comparison.semantic_divergence is None
    assert comparison.unresolved == ("semantic_divergence_unmeasured",)


def test_h5_unknown_and_ambiguous_migration_paths_fail_closed() -> None:
    registry = CaseMigrationRegistry()
    with pytest.raises(P3ContractError, match="no migration path"):
        registry.compare_replay(_identity(schema="v1"), _identity(schema="v9"))

    registry.register(MigrationStep("v1", "v2", lambda payload: dict(payload)))
    registry.register(MigrationStep("v2", "v3", lambda payload: dict(payload)))
    registry.register(MigrationStep("v1", "v3", lambda payload: dict(payload)))
    with pytest.raises(P3ContractError, match="ambiguous migration path"):
        registry.path("v1", "v3")


def test_h5_migration_report_path_digest_is_deterministic() -> None:
    registry = CaseMigrationRegistry()
    registry.register(MigrationStep("v1", "v2", lambda payload: {**payload, "schema": "v2"}))
    source = VersionedCase.build(case_id="SYN", schema_version="v1", payload={"x": 1})
    first = registry.migrate(source, "v2")
    second = registry.migrate(source, "v2")
    assert first.path_digest == second.path_digest
    assert len(first.path_digest) == 64
