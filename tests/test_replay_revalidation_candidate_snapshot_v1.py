from __future__ import annotations

from copy import deepcopy

import pytest

from core.replay_revalidation_candidate_snapshot_v1 import (
    ReplayRevalidationCandidateSnapshotError,
    ReplayRevalidationCandidateSnapshotV1,
    ReplayRevalidationRuntimeMaterialV1,
    materialize_revalidation_candidate_snapshot_v1,
)
from core.replay_revalidation_invalidation_v1 import ReplayRevalidationFingerprintV1

REPOSITORY_SHA = "a" * 40


def _runtime_material() -> ReplayRevalidationRuntimeMaterialV1:
    return ReplayRevalidationRuntimeMaterialV1(
        schema_version="case-schema-v7",
        config_digest="1" * 64,
        corpus_digest="2" * 64,
        provider_identities=("provider-b@2", "provider-a@1"),
        plugin_identities=("plugin-a@4",),
        input_digests=("3" * 64, "4" * 64),
        evidence_digests=("5" * 64,),
        dependency_lock_digest="6" * 64,
        python_implementation="CPython",
        python_version="3.14.4",
        platform_tag="linux-x86_64",
        project_version="1.1.0.dev0",
        build_backend="uv-build@0.8",
    )


def _snapshot(
    *,
    repository_sha: str = REPOSITORY_SHA,
    lrd01i_bundle_digest: str = "7" * 64,
) -> ReplayRevalidationCandidateSnapshotV1:
    return materialize_revalidation_candidate_snapshot_v1(
        candidate_repository_sha=repository_sha,
        runtime_material=_runtime_material(),
        lrd01i_bundle_digest=lrd01i_bundle_digest,
        ssc02_manifest_digest="8" * 64,
        environment_profile_digests=("9" * 64, "a" * 64),
        replay_policy_digest="b" * 64,
        migration_registry_digest="c" * 64,
        canonicalization_profile_digest="d" * 64,
        crypto_profile_digest="e" * 64,
        storage_profile_digests=("f" * 64,),
    )


def test_materializes_complete_runtime_and_01m_fingerprint_from_one_exact_sha() -> None:
    snapshot = _snapshot()

    runtime = snapshot.runtime_identity
    assert runtime.complete_for_replay is True
    assert runtime.code_sha == REPOSITORY_SHA
    assert snapshot.fingerprint.runtime_identity_digest == runtime.digest()
    assert snapshot.candidate is snapshot.fingerprint
    candidate, candidate_runtime, repository_sha = snapshot.handoff_inputs()
    assert candidate is snapshot.fingerprint
    assert candidate_runtime == runtime
    assert repository_sha == REPOSITORY_SHA


def test_materialization_is_deterministic_and_content_addressed() -> None:
    left = _snapshot()
    right = _snapshot()
    changed = _snapshot(lrd01i_bundle_digest="0" * 64)

    assert left == right
    assert left.snapshot_digest == right.snapshot_digest
    assert changed.snapshot_digest != left.snapshot_digest
    assert changed.fingerprint.fingerprint_digest != left.fingerprint.fingerprint_digest


def test_runtime_material_normalizes_existing_runtime_identity_inventories() -> None:
    material = _runtime_material()

    assert material.provider_identities == ("provider-a@1", "provider-b@2")
    assert material.input_digests == ("3" * 64, "4" * 64)
    assert material.build_runtime_identity(repository_sha=REPOSITORY_SHA).canonical_dict()[
        "inventories_declared"
    ] == {
        "providers": True,
        "plugins": True,
        "inputs": True,
        "evidence": True,
        "execution_environment": True,
    }


def test_snapshot_round_trip_is_strict_and_canonical() -> None:
    snapshot = _snapshot()
    payload = snapshot.canonical_dict()

    restored = ReplayRevalidationCandidateSnapshotV1.from_dict(payload)

    assert restored == snapshot
    assert restored.snapshot_digest == snapshot.snapshot_digest


def test_runtime_material_from_dict_rejects_noncanonical_inventory_order() -> None:
    payload = _runtime_material().canonical_dict()
    payload["provider_identities"] = ["provider-b@2", "provider-a@1"]

    with pytest.raises(
        ReplayRevalidationCandidateSnapshotError,
        match="runtime material is not canonical",
    ):
        ReplayRevalidationRuntimeMaterialV1.from_dict(payload)


@pytest.mark.parametrize(
    "repository_sha",
    [
        "main",
        "a" * 39,
        "A" * 40,
        " a" + "a" * 39,
        "a" * 64,
    ],
)
def test_rejects_mutable_or_noncanonical_repository_identity(
    repository_sha: str,
) -> None:
    with pytest.raises(ReplayRevalidationCandidateSnapshotError):
        _snapshot(repository_sha=repository_sha)


def test_rejects_incomplete_runtime_execution_identity() -> None:
    with pytest.raises(
        ReplayRevalidationCandidateSnapshotError,
        match="invalid runtime material",
    ):
        ReplayRevalidationRuntimeMaterialV1(
            schema_version="case-schema-v7",
            config_digest="1" * 64,
            corpus_digest="2" * 64,
            provider_identities=(),
            plugin_identities=(),
            input_digests=(),
            evidence_digests=(),
            dependency_lock_digest="6" * 64,
            python_implementation="CPython",
            python_version="",
            platform_tag="linux-x86_64",
            project_version="1.1.0.dev0",
            build_backend="uv-build@0.8",
        )


def test_rejects_incomplete_environment_profile_inventory() -> None:
    with pytest.raises(
        ReplayRevalidationCandidateSnapshotError,
        match="environment_profile_digest requires at least 2",
    ):
        materialize_revalidation_candidate_snapshot_v1(
            candidate_repository_sha=REPOSITORY_SHA,
            runtime_material=_runtime_material(),
            lrd01i_bundle_digest="7" * 64,
            ssc02_manifest_digest="8" * 64,
            environment_profile_digests=("9" * 64,),
            replay_policy_digest="b" * 64,
            migration_registry_digest="c" * 64,
            canonicalization_profile_digest="d" * 64,
            crypto_profile_digest="e" * 64,
            storage_profile_digests=("f" * 64,),
        )


def test_rejects_missing_storage_profile_inventory() -> None:
    with pytest.raises(
        ReplayRevalidationCandidateSnapshotError,
        match="storage_profile_digest requires at least 1",
    ):
        materialize_revalidation_candidate_snapshot_v1(
            candidate_repository_sha=REPOSITORY_SHA,
            runtime_material=_runtime_material(),
            lrd01i_bundle_digest="7" * 64,
            ssc02_manifest_digest="8" * 64,
            environment_profile_digests=("9" * 64, "a" * 64),
            replay_policy_digest="b" * 64,
            migration_registry_digest="c" * 64,
            canonicalization_profile_digest="d" * 64,
            crypto_profile_digest="e" * 64,
            storage_profile_digests=(),
        )


def test_rejects_fingerprint_runtime_substitution() -> None:
    good = _snapshot()
    substituted = ReplayRevalidationFingerprintV1(
        runtime_identity_digest="0" * 64,
        lrd01i_bundle_digest=good.fingerprint.lrd01i_bundle_digest,
        ssc02_manifest_digest=good.fingerprint.ssc02_manifest_digest,
        environment_profile_digests=good.fingerprint.environment_profile_digests,
        replay_policy_digest=good.fingerprint.replay_policy_digest,
        migration_registry_digest=good.fingerprint.migration_registry_digest,
        canonicalization_profile_digest=good.fingerprint.canonicalization_profile_digest,
        crypto_profile_digest=good.fingerprint.crypto_profile_digest,
        storage_profile_digests=good.fingerprint.storage_profile_digests,
    )

    with pytest.raises(
        ReplayRevalidationCandidateSnapshotError,
        match="fingerprint/RuntimeIdentity substitution detected",
    ):
        ReplayRevalidationCandidateSnapshotV1(
            candidate_repository_sha=REPOSITORY_SHA,
            runtime_material=good.runtime_material,
            fingerprint=substituted,
        )


def test_rejects_serialized_runtime_identity_substitution() -> None:
    payload = deepcopy(_snapshot().canonical_dict())
    runtime = payload["runtime_identity"]
    assert isinstance(runtime, dict)
    runtime["code_sha"] = "b" * 40

    with pytest.raises(
        ReplayRevalidationCandidateSnapshotError,
        match="serialized RuntimeIdentity does not match",
    ):
        ReplayRevalidationCandidateSnapshotV1.from_dict(payload)


def test_rejects_snapshot_digest_tampering() -> None:
    payload = _snapshot().canonical_dict()
    payload["snapshot_digest"] = "0" * 64

    with pytest.raises(
        ReplayRevalidationCandidateSnapshotError,
        match="candidate snapshot digest mismatch",
    ):
        ReplayRevalidationCandidateSnapshotV1.from_dict(payload)


def test_rejects_unknown_snapshot_field() -> None:
    payload = _snapshot().canonical_dict()
    payload["surprise"] = "not-authoritative"

    with pytest.raises(
        ReplayRevalidationCandidateSnapshotError,
        match="key contract violation",
    ):
        ReplayRevalidationCandidateSnapshotV1.from_dict(payload)


def test_rejects_authority_injection() -> None:
    payload = _snapshot().canonical_dict()
    payload["scheduler_authority"] = True

    with pytest.raises(
        ReplayRevalidationCandidateSnapshotError,
        match="scheduler_authority must remain false",
    ):
        ReplayRevalidationCandidateSnapshotV1.from_dict(payload)


def test_snapshot_exposes_no_new_authority() -> None:
    snapshot = _snapshot()

    assert snapshot.repository_change_detection_authority is False
    assert snapshot.scheduler_authority is False
    assert snapshot.replay_execution_authority is False
    assert snapshot.provider_authority is False
    assert snapshot.storage_authority is False
    assert snapshot.mutable_pointer_authority is False
    assert snapshot.product_write_authority is False
    assert snapshot.ccl_write_authority is False
    assert snapshot.release_authority is False
