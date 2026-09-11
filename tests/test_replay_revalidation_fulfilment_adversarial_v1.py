from __future__ import annotations

import copy
import hashlib
from functools import lru_cache

import pytest

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
    ReplayRevalidationFulfilmentError,
    ReplayRevalidationFulfilmentState,
    ReplayRevalidationFulfilmentV1,
    evaluate_revalidation_fulfilment_v1,
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


def _evaluate(
    *,
    replay_report: dict[str, object] | None,
    replay_repository_sha: str | None,
    candidate_repository_sha: str | None = None,
):
    baseline_runtime, candidate_runtime, baseline, candidate, decision, _ = _material()
    return evaluate_revalidation_fulfilment_v1(
        decision=decision,
        baseline=baseline,
        candidate=candidate,
        baseline_runtime_identity=baseline_runtime,
        candidate_runtime_identity=candidate_runtime,
        candidate_repository_sha=candidate_repository_sha or candidate_runtime.code_sha,
        replay_report=replay_report,
        replay_repository_sha=replay_repository_sha,
    )


def test_candidate_repository_sha_substitution_fails_closed() -> None:
    _, candidate_runtime, _, _, _, report = _material()
    with pytest.raises(
        ReplayRevalidationFulfilmentError,
        match="repository SHA/RuntimeIdentity substitution",
    ):
        _evaluate(
            replay_report=report,
            replay_repository_sha=candidate_runtime.code_sha,
            candidate_repository_sha="c" * 40,
        )


def test_stale_replay_sha_cannot_be_relabelled_as_candidate_evidence() -> None:
    _, _, _, _, _, report = _material()
    with pytest.raises(
        ReplayRevalidationFulfilmentError,
        match="not produced for the exact candidate",
    ):
        _evaluate(replay_report=report, replay_repository_sha="a" * 40)


def test_tampered_replay_report_fails_before_fulfilment_claim() -> None:
    _, candidate_runtime, _, _, _, report = _material()
    tampered = copy.deepcopy(report)
    receipts = tampered["receipts"]
    assert isinstance(receipts, list)
    assert isinstance(receipts[0], dict)
    receipts[0]["semantic_result_identity"] = h("tampered-semantic")
    with pytest.raises(
        ReplayRevalidationFulfilmentError,
        match="invalid LRD-01K replay evidence",
    ):
        _evaluate(
            replay_report=tampered,
            replay_repository_sha=candidate_runtime.code_sha,
        )


def test_valid_semantic_drift_report_is_revalidation_failed_not_pass() -> None:
    _, candidate_runtime, _, _, _, report = _material()
    plan = report["plan"]
    profiles = report["profiles"]
    observed = report["observed_environments"]
    assert isinstance(plan, dict)
    assert isinstance(profiles, list)
    assert isinstance(observed, list)
    observed_by_profile = {
        str(item["declared_profile_digest"]): item
        for item in observed
        if isinstance(item, dict)
    }
    receipts: list[dict[str, object]] = []
    for profile in profiles:
        assert isinstance(profile, dict)
        profile_digest = str(profile["profile_digest"])
        observation = observed_by_profile[profile_digest]
        receipts.append(
            build_replay_receipt(
                plan=plan,
                profile=profile,
                observed=observation,
                verifier_digest=str(profile["replay_verifier_digest"]),
                semantic_result_identity=h("semantic-drift"),
                invariant_report_identity=h("invariants-drift"),
                lrd01d_classification="SEMANTIC_DRIFT",
                execution_status=ReplayExecutionStatus.VERIFIED,
            )
        )
    failed_report = build_replay_report(
        plan=plan,
        profiles=profiles,
        observed_environments=observed,
        receipts=receipts,
    )
    result = _evaluate(
        replay_report=failed_report,
        replay_repository_sha=candidate_runtime.code_sha,
    )
    assert result.state is ReplayRevalidationFulfilmentState.REVALIDATION_FAILED
    assert result.revalidation_satisfied is False
    assert all("SEMANTIC_DRIFT" in violation for violation in result.violations)


def test_partial_replay_binding_is_rejected() -> None:
    _, _, _, _, _, report = _material()
    with pytest.raises(ReplayRevalidationFulfilmentError, match="supplied together"):
        _evaluate(replay_report=report, replay_repository_sha=None)


def test_fulfilment_parser_rejects_authority_injection_and_digest_tamper() -> None:
    _, candidate_runtime, _, _, _, report = _material()
    result = _evaluate(
        replay_report=report,
        replay_repository_sha=candidate_runtime.code_sha,
    )
    authority = result.canonical_dict()
    authority["release_authority"] = True
    with pytest.raises(ReplayRevalidationFulfilmentError, match="release_authority"):
        ReplayRevalidationFulfilmentV1.from_dict(authority)

    tampered = result.canonical_dict()
    tampered["state"] = "REVALIDATION_FAILED"
    with pytest.raises(ReplayRevalidationFulfilmentError):
        ReplayRevalidationFulfilmentV1.from_dict(tampered)


def test_uppercase_repository_sha_is_never_canonical() -> None:
    _, candidate_runtime, _, _, _, report = _material()
    with pytest.raises(
        ReplayRevalidationFulfilmentError,
        match="lowercase 40-char git SHA",
    ):
        _evaluate(
            replay_report=report,
            replay_repository_sha=candidate_runtime.code_sha,
            candidate_repository_sha=candidate_runtime.code_sha.upper(),
        )
