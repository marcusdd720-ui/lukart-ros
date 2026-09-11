from __future__ import annotations

import copy
import hashlib
from functools import lru_cache

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
from core.replay_revalidation_fulfilment_v1 import (
    ReplayRevalidationFulfilmentState,
    ReplayRevalidationFulfilmentV1,
    evaluate_revalidation_fulfilment_v1,
    verify_revalidation_fulfilment_v1,
)
from core.replay_revalidation_invalidation_v1 import (
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


@lru_cache(maxsize=1)
def _cached_replay_material() -> tuple[dict[str, object], dict[str, object]]:
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
    plan = build_replay_plan(
        lrd01i_bundle_digest=h("bundle"),
        ssc02_manifest_digest=h("ssc"),
        environment_profile_digests=[
            str(profile["profile_digest"]),
            str(other["profile_digest"]),
        ],
        reference_profile_digest=str(profile["profile_digest"]),
        replay_policy_digest=h("replay-policy"),
        migration_registry_digest=h("migration"),
        canonicalization_profile_digest=h("canon"),
        crypto_profile_digest=h("crypto"),
        expected_matrix=[str(profile["profile_digest"]), str(other["profile_digest"])],
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


def _material() -> tuple[
    RuntimeIdentity,
    RuntimeIdentity,
    ReplayRevalidationFingerprintV1,
    ReplayRevalidationFingerprintV1,
    object,
    dict[str, object],
]:
    plan, report = copy.deepcopy(_cached_replay_material())
    baseline_runtime = _runtime("a" * 40)
    candidate_runtime = _runtime("b" * 40)
    plan_profiles = plan["environment_profile_digests"]
    assert isinstance(plan_profiles, list)
    fingerprint_args = {
        "lrd01i_bundle_digest": str(plan["lrd01i_bundle_digest"]),
        "ssc02_manifest_digest": str(plan["ssc02_manifest_digest"]),
        "environment_profile_digests": tuple(str(item) for item in plan_profiles),
        "replay_policy_digest": str(plan["replay_policy_digest"]),
        "migration_registry_digest": str(plan["migration_registry_digest"]),
        "canonicalization_profile_digest": str(plan["canonicalization_profile_digest"]),
        "crypto_profile_digest": str(plan["crypto_profile_digest"]),
        "storage_profile_digests": (h("storage-profile"),),
    }
    baseline = ReplayRevalidationFingerprintV1.build(
        runtime_identity=baseline_runtime,
        **fingerprint_args,
    )
    candidate = ReplayRevalidationFingerprintV1.build(
        runtime_identity=candidate_runtime,
        **fingerprint_args,
    )
    decision = evaluate_revalidation_requirement_v1(
        baseline=baseline,
        candidate=candidate,
        baseline_runtime_identity=baseline_runtime,
        candidate_runtime_identity=candidate_runtime,
    )
    assert decision.state is ReplayRevalidationState.REVALIDATION_REQUIRED
    return baseline_runtime, candidate_runtime, baseline, candidate, decision, report


def test_required_change_without_fresh_report_stays_required() -> None:
    baseline_runtime, candidate_runtime, baseline, candidate, decision, _ = _material()
    result = evaluate_revalidation_fulfilment_v1(
        decision=decision,
        baseline=baseline,
        candidate=candidate,
        baseline_runtime_identity=baseline_runtime,
        candidate_runtime_identity=candidate_runtime,
        candidate_repository_sha=candidate_runtime.code_sha,
    )
    assert result.state is ReplayRevalidationFulfilmentState.REVALIDATION_REQUIRED
    assert result.revalidation_satisfied is False
    assert result.baseline_replay_reusable is False
    assert result.replay_report_digest is None


def test_required_change_with_exact_verified_matrix_is_revalidated() -> None:
    baseline_runtime, candidate_runtime, baseline, candidate, decision, report = _material()
    result = evaluate_revalidation_fulfilment_v1(
        decision=decision,
        baseline=baseline,
        candidate=candidate,
        baseline_runtime_identity=baseline_runtime,
        candidate_runtime_identity=candidate_runtime,
        candidate_repository_sha=candidate_runtime.code_sha,
        replay_report=report,
        replay_repository_sha=candidate_runtime.code_sha,
    )
    assert result.state is ReplayRevalidationFulfilmentState.REVALIDATED
    assert result.revalidation_satisfied is True
    assert result.replay_report_digest == report["report_digest"]
    assert ReplayRevalidationFulfilmentV1.from_dict(result.canonical_dict()) == result
    assert verify_revalidation_fulfilment_v1(
        result,
        decision=decision,
        baseline=baseline,
        candidate=candidate,
        baseline_runtime_identity=baseline_runtime,
        candidate_runtime_identity=candidate_runtime,
        candidate_repository_sha=candidate_runtime.code_sha,
        replay_report=report,
        replay_repository_sha=candidate_runtime.code_sha,
    ) == result.fulfilment_digest


def test_unchanged_candidate_reuses_verified_baseline_without_new_report() -> None:
    plan, _ = copy.deepcopy(_cached_replay_material())
    runtime = _runtime("a" * 40)
    profiles = plan["environment_profile_digests"]
    assert isinstance(profiles, list)
    fingerprint = ReplayRevalidationFingerprintV1.build(
        runtime_identity=runtime,
        lrd01i_bundle_digest=str(plan["lrd01i_bundle_digest"]),
        ssc02_manifest_digest=str(plan["ssc02_manifest_digest"]),
        environment_profile_digests=tuple(str(item) for item in profiles),
        replay_policy_digest=str(plan["replay_policy_digest"]),
        migration_registry_digest=str(plan["migration_registry_digest"]),
        canonicalization_profile_digest=str(plan["canonicalization_profile_digest"]),
        crypto_profile_digest=str(plan["crypto_profile_digest"]),
        storage_profile_digests=(h("storage-profile"),),
    )
    decision = evaluate_revalidation_requirement_v1(
        baseline=fingerprint,
        candidate=fingerprint,
        baseline_runtime_identity=runtime,
        candidate_runtime_identity=runtime,
    )
    result = evaluate_revalidation_fulfilment_v1(
        decision=decision,
        baseline=fingerprint,
        candidate=fingerprint,
        baseline_runtime_identity=runtime,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
    )
    assert result.state is ReplayRevalidationFulfilmentState.BASELINE_REUSABLE
    assert result.baseline_replay_reusable is True
    assert result.revalidation_satisfied is False


def test_missing_baseline_decision_remains_unverifiable() -> None:
    plan, _ = copy.deepcopy(_cached_replay_material())
    runtime = _runtime("b" * 40)
    profiles = plan["environment_profile_digests"]
    assert isinstance(profiles, list)
    candidate = ReplayRevalidationFingerprintV1.build(
        runtime_identity=runtime,
        lrd01i_bundle_digest=str(plan["lrd01i_bundle_digest"]),
        ssc02_manifest_digest=str(plan["ssc02_manifest_digest"]),
        environment_profile_digests=tuple(str(item) for item in profiles),
        replay_policy_digest=str(plan["replay_policy_digest"]),
        migration_registry_digest=str(plan["migration_registry_digest"]),
        canonicalization_profile_digest=str(plan["canonicalization_profile_digest"]),
        crypto_profile_digest=str(plan["crypto_profile_digest"]),
        storage_profile_digests=(h("storage-profile"),),
    )
    decision = evaluate_revalidation_requirement_v1(
        baseline=None,
        candidate=candidate,
        baseline_runtime_identity=None,
        candidate_runtime_identity=runtime,
    )
    result = evaluate_revalidation_fulfilment_v1(
        decision=decision,
        baseline=None,
        candidate=candidate,
        baseline_runtime_identity=None,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
    )
    assert result.state is ReplayRevalidationFulfilmentState.UNVERIFIABLE
    assert result.revalidation_satisfied is False
    assert result.violations == ("baseline_revalidation_fingerprint_missing",)
