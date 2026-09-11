from __future__ import annotations

import copy
import hashlib

import pytest

from core.artifact_escrow_v1 import (
    EscrowLimitsV1,
    FileSystemEscrowBackendV1,
    migrate_verified_blob,
)
from core.cross_environment_replay_v1 import (
    ReplayExecutionStatus,
    build_environment_profile,
    build_observed_environment_receipt,
    build_replay_plan,
    build_replay_receipt,
    build_replay_report,
    capture_environment_snapshot,
    digest_value,
)
from core.p3.contracts import RuntimeIdentity
from core.replay_revalidation_baseline_v1 import (
    ReplayRevalidationBaselineError,
    ReplayRevalidationBaselineV1,
    publish_revalidation_baseline_v1,
    restore_revalidation_baseline_v1,
)
from core.replay_revalidation_invalidation_v1 import (
    ReplayChangeDomain,
    ReplayRevalidationFingerprintV1,
    ReplayRevalidationState,
    evaluate_revalidation_requirement_v1,
)


def h(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _runtime(code_sha: str) -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha=code_sha,
        schema_version="case-v2",
        config_digest=h("config"),
        corpus_digest=h("corpus"),
        provider_identities=("provider.alpha@1",),
        plugin_identities=("plugin.alpha@1",),
        input_digests=(h("input"),),
        evidence_digests=(h("evidence"),),
        provider_inventory_declared=True,
        plugin_inventory_declared=True,
        input_inventory_declared=True,
        evidence_inventory_declared=True,
        dependency_lock_digest=h("lock"),
        python_implementation="CPython",
        python_version="3.14.7",
        platform_tag="manylinux_2_39_x86_64",
        project_version="1.1.0.dev0",
        build_backend="lukart_build_backend",
        execution_environment_declared=True,
    )


def _replay_material() -> tuple[dict[str, object], dict[str, object]]:
    verifier = h("verifier")
    policy = h("environment-policy")
    snapshot = capture_environment_snapshot()
    profile = build_environment_profile(
        name="current",
        observed=snapshot,
        dependency_lock_digest=h("lock"),
        physical_dependency_artifact_identities=[
            str(snapshot["installed_artifact_inventory_digest"])
        ],
        canonicalization_profile_digest=h("canon"),
        migration_registry_digest=h("migration"),
        crypto_profile_digest=h("crypto"),
        lrd01i_bundle_digest=h("bundle"),
        replay_verifier_digest=verifier,
        environment_policy_digest=policy,
    )
    observed = build_observed_environment_receipt(
        snapshot,
        declared_profile_digest=str(profile["profile_digest"]),
        verifier_digest=verifier,
        environment_policy_digest=policy,
    )
    other = dict(profile)
    other["name"] = "materially-other"
    other["profile_digest"] = digest_value(
        {key: value for key, value in other.items() if key != "profile_digest"}
    )
    observed_other = copy.deepcopy(observed)
    observed_other["os_build"] = str(observed_other["os_build"]) + "-other-runner"
    observed_other["declared_profile_digest"] = other["profile_digest"]
    observed_other["observed_environment_digest"] = digest_value(
        {
            key: value
            for key, value in observed_other.items()
            if key != "observed_environment_digest"
        }
    )
    profiles = [str(profile["profile_digest"]), str(other["profile_digest"])]
    plan = build_replay_plan(
        lrd01i_bundle_digest=h("bundle"),
        ssc02_manifest_digest=h("ssc"),
        environment_profile_digests=profiles,
        reference_profile_digest=str(profile["profile_digest"]),
        replay_policy_digest=h("replay-policy"),
        migration_registry_digest=h("migration"),
        canonicalization_profile_digest=h("canon"),
        crypto_profile_digest=h("crypto"),
        expected_matrix=profiles,
        hard_bounds={"network": "DENY"},
    )
    receipts = [
        build_replay_receipt(
            plan=plan,
            profile=current_profile,
            observed=current_observed,
            verifier_digest=verifier,
            semantic_result_identity=h("semantic"),
            invariant_report_identity=h("invariants"),
            lrd01d_classification="NO_DRIFT",
            execution_status=ReplayExecutionStatus.VERIFIED,
        )
        for current_profile, current_observed in (
            (profile, observed),
            (other, observed_other),
        )
    ]
    report = build_replay_report(
        plan=plan,
        profiles=[profile, other],
        observed_environments=[observed, observed_other],
        receipts=receipts,
    )
    return plan, report


def _fingerprint(
    runtime_identity: RuntimeIdentity,
    plan: dict[str, object],
) -> ReplayRevalidationFingerprintV1:
    profiles = plan["environment_profile_digests"]
    assert isinstance(profiles, list)
    return ReplayRevalidationFingerprintV1.build(
        runtime_identity=runtime_identity,
        lrd01i_bundle_digest=str(plan["lrd01i_bundle_digest"]),
        ssc02_manifest_digest=str(plan["ssc02_manifest_digest"]),
        environment_profile_digests=tuple(str(item) for item in profiles),
        replay_policy_digest=str(plan["replay_policy_digest"]),
        migration_registry_digest=str(plan["migration_registry_digest"]),
        canonicalization_profile_digest=str(plan["canonicalization_profile_digest"]),
        crypto_profile_digest=str(plan["crypto_profile_digest"]),
        storage_profile_digests=(h("storage-profile"),),
    )


def _baseline() -> ReplayRevalidationBaselineV1:
    plan, report = _replay_material()
    runtime = _runtime("a" * 40)
    fingerprint = _fingerprint(runtime, plan)
    return ReplayRevalidationBaselineV1.build(
        repository_sha=runtime.code_sha,
        replay_repository_sha=runtime.code_sha,
        runtime_identity=runtime,
        fingerprint=fingerprint,
        replay_report=report,
    )


def test_baseline_is_canonical_content_addressed_and_round_trips() -> None:
    baseline = _baseline()
    restored = ReplayRevalidationBaselineV1.from_dict(baseline.canonical_dict())
    assert restored == baseline
    assert restored.baseline_digest == baseline.baseline_digest
    assert restored.canonical_bytes() == baseline.canonical_bytes()


def test_baseline_round_trips_through_existing_escrow_and_alternate_store(tmp_path) -> None:
    baseline = _baseline()
    limits = EscrowLimitsV1()
    source = FileSystemEscrowBackendV1(tmp_path / "source")
    target = FileSystemEscrowBackendV1(tmp_path / "target")
    blob = publish_revalidation_baseline_v1(baseline, backend=source, limits=limits)
    migrated = migrate_verified_blob(blob, source=source, target=target, limits=limits)
    assert migrated == blob
    assert restore_revalidation_baseline_v1(
        migrated,
        backend=target,
        limits=limits,
    ) == baseline


def test_restored_baseline_supplies_exact_lrd01m_inputs() -> None:
    baseline = _baseline()
    baseline_fingerprint, baseline_runtime = baseline.invalidation_inputs()
    plan = baseline.replay_report["plan"]
    assert isinstance(plan, dict)
    candidate_runtime = _runtime("b" * 40)
    candidate = _fingerprint(candidate_runtime, plan)
    decision = evaluate_revalidation_requirement_v1(
        baseline=baseline_fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline_runtime,
        candidate_runtime_identity=candidate_runtime,
    )
    assert decision.state is ReplayRevalidationState.REVALIDATION_REQUIRED
    assert ReplayChangeDomain.CODE in decision.changed_domains
    assert "runtime.code_sha" in decision.changed_fields


def test_repository_runtime_or_replay_sha_substitution_fails_closed() -> None:
    baseline = _baseline()
    with pytest.raises(ReplayRevalidationBaselineError, match="repository identity substitution"):
        ReplayRevalidationBaselineV1.build(
            repository_sha="b" * 40,
            replay_repository_sha=baseline.repository_sha,
            runtime_identity=baseline.runtime_identity,
            fingerprint=baseline.fingerprint,
            replay_report=baseline.replay_report,
        )
    with pytest.raises(ReplayRevalidationBaselineError, match="repository identity substitution"):
        ReplayRevalidationBaselineV1.build(
            repository_sha=baseline.repository_sha,
            replay_repository_sha="b" * 40,
            runtime_identity=baseline.runtime_identity,
            fingerprint=baseline.fingerprint,
            replay_report=baseline.replay_report,
        )


def test_fingerprint_runtime_substitution_fails_closed() -> None:
    baseline = _baseline()
    plan = baseline.replay_report["plan"]
    assert isinstance(plan, dict)
    foreign_runtime = _runtime("b" * 40)
    foreign_fingerprint = _fingerprint(foreign_runtime, plan)
    with pytest.raises(
        ReplayRevalidationBaselineError,
        match="fingerprint RuntimeIdentity mismatch",
    ):
        ReplayRevalidationBaselineV1.build(
            repository_sha=baseline.repository_sha,
            replay_repository_sha=baseline.repository_sha,
            runtime_identity=baseline.runtime_identity,
            fingerprint=foreign_fingerprint,
            replay_report=baseline.replay_report,
        )


def test_report_tamper_and_plan_substitution_fail_closed() -> None:
    baseline = _baseline()
    tampered = copy.deepcopy(baseline.replay_report)
    receipts = tampered["receipts"]
    assert isinstance(receipts, list)
    assert isinstance(receipts[0], dict)
    receipts[0]["semantic_result_identity"] = h("tampered")
    with pytest.raises(ReplayRevalidationBaselineError, match="invalid LRD-01K replay evidence"):
        ReplayRevalidationBaselineV1.build(
            repository_sha=baseline.repository_sha,
            replay_repository_sha=baseline.repository_sha,
            runtime_identity=baseline.runtime_identity,
            fingerprint=baseline.fingerprint,
            replay_report=tampered,
        )

    plan = baseline.replay_report["plan"]
    assert isinstance(plan, dict)
    foreign_fingerprint = ReplayRevalidationFingerprintV1.build(
        runtime_identity=baseline.runtime_identity,
        lrd01i_bundle_digest=str(plan["lrd01i_bundle_digest"]),
        ssc02_manifest_digest=str(plan["ssc02_manifest_digest"]),
        environment_profile_digests=baseline.fingerprint.environment_profile_digests,
        replay_policy_digest=h("different-policy"),
        migration_registry_digest=str(plan["migration_registry_digest"]),
        canonicalization_profile_digest=str(plan["canonicalization_profile_digest"]),
        crypto_profile_digest=str(plan["crypto_profile_digest"]),
        storage_profile_digests=baseline.fingerprint.storage_profile_digests,
    )
    with pytest.raises(ReplayRevalidationBaselineError, match="replay_policy_digest"):
        ReplayRevalidationBaselineV1.build(
            repository_sha=baseline.repository_sha,
            replay_repository_sha=baseline.repository_sha,
            runtime_identity=baseline.runtime_identity,
            fingerprint=foreign_fingerprint,
            replay_report=baseline.replay_report,
        )


def test_unacceptable_semantic_replay_cannot_seed_baseline() -> None:
    plan, report = _replay_material()
    receipts = report["receipts"]
    profiles = report["profiles"]
    observed = report["observed_environments"]
    assert isinstance(receipts, list)
    assert isinstance(profiles, list)
    assert isinstance(observed, list)
    observed_by_profile = {
        str(item["declared_profile_digest"]): item
        for item in observed
        if isinstance(item, dict)
    }
    drift_receipts: list[dict[str, object]] = []
    for profile in profiles:
        assert isinstance(profile, dict)
        profile_digest = str(profile["profile_digest"])
        observation = observed_by_profile[profile_digest]
        drift_receipts.append(
            build_replay_receipt(
                plan=plan,
                profile=profile,
                observed=observation,
                verifier_digest=str(profile["replay_verifier_digest"]),
                semantic_result_identity=h("drift-semantic"),
                invariant_report_identity=h("drift-invariants"),
                lrd01d_classification="SEMANTIC_DRIFT",
                execution_status=ReplayExecutionStatus.VERIFIED,
            )
        )
    drift_report = build_replay_report(
        plan=plan,
        profiles=profiles,
        observed_environments=observed,
        receipts=drift_receipts,
    )
    runtime = _runtime("a" * 40)
    fingerprint = _fingerprint(runtime, plan)
    with pytest.raises(ReplayRevalidationBaselineError, match="classification is not acceptable"):
        ReplayRevalidationBaselineV1.build(
            repository_sha=runtime.code_sha,
            replay_repository_sha=runtime.code_sha,
            runtime_identity=runtime,
            fingerprint=fingerprint,
            replay_report=drift_report,
        )


def test_authority_injection_and_digest_tamper_are_rejected() -> None:
    baseline = _baseline()
    authority = baseline.canonical_dict()
    authority["storage_authority"] = True
    with pytest.raises(ReplayRevalidationBaselineError, match="storage_authority"):
        ReplayRevalidationBaselineV1.from_dict(authority)

    tampered = baseline.canonical_dict()
    tampered["baseline_digest"] = h("wrong")
    with pytest.raises(ReplayRevalidationBaselineError, match="baseline_digest mismatch"):
        ReplayRevalidationBaselineV1.from_dict(tampered)
