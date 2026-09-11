from __future__ import annotations

import copy
import hashlib

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
from core.replay_revalidation_baseline_transition_v1 import (
    ReplayRevalidationBaselineTransitionError,
    ReplayRevalidationBaselineTransitionState,
    ReplayRevalidationBaselineTransitionV1,
    evaluate_revalidation_baseline_transition_v1,
    verify_revalidation_baseline_transition_v1,
)
from core.replay_revalidation_baseline_v1 import ReplayRevalidationBaselineV1
from core.replay_revalidation_fulfilment_v1 import (
    ReplayRevalidationFulfilmentState,
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
    return plan, build_replay_report(
        plan=plan,
        profiles=[profile, other],
        observed_environments=[observed, observed_other],
        receipts=receipts,
    )


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


def _baseline() -> tuple[ReplayRevalidationBaselineV1, dict[str, object]]:
    plan, report = _replay_material()
    runtime = _runtime("a" * 40)
    fingerprint = _fingerprint(runtime, plan)
    return (
        ReplayRevalidationBaselineV1.build(
            repository_sha=runtime.code_sha,
            replay_repository_sha=runtime.code_sha,
            runtime_identity=runtime,
            fingerprint=fingerprint,
            replay_report=report,
        ),
        plan,
    )


def _changed_material() -> tuple[
    ReplayRevalidationBaselineV1,
    ReplayRevalidationFingerprintV1,
    RuntimeIdentity,
    dict[str, object],
]:
    baseline, plan = _baseline()
    _, report = _replay_material()
    candidate_runtime = _runtime("b" * 40)
    candidate = _fingerprint(candidate_runtime, plan)
    return baseline, candidate, candidate_runtime, report


def test_unchanged_candidate_reuses_exact_baseline_and_round_trips() -> None:
    baseline, _ = _baseline()
    candidate = baseline.fingerprint
    runtime = baseline.runtime_identity
    decision = evaluate_revalidation_requirement_v1(
        baseline=baseline.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline.runtime_identity,
        candidate_runtime_identity=runtime,
    )
    fulfilment = evaluate_revalidation_fulfilment_v1(
        decision=decision,
        baseline=baseline.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline.runtime_identity,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
    )
    evaluation = evaluate_revalidation_baseline_transition_v1(
        prior_baseline=baseline,
        decision=decision,
        fulfilment=fulfilment,
        candidate=candidate,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
    )
    assert evaluation.transition.state is ReplayRevalidationBaselineTransitionState.BASELINE_REUSED
    assert evaluation.resulting_baseline == baseline
    assert evaluation.transition.resulting_baseline_digest == baseline.baseline_digest
    restored = ReplayRevalidationBaselineTransitionV1.from_dict(
        evaluation.transition.canonical_dict()
    )
    assert restored == evaluation.transition
    assert verify_revalidation_baseline_transition_v1(
        restored,
        prior_baseline=baseline,
        decision=decision,
        fulfilment=fulfilment,
        candidate=candidate,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
    ) == restored.transition_digest


def test_changed_candidate_with_verified_replay_advances_exact_baseline() -> None:
    baseline, candidate, runtime, report = _changed_material()
    decision = evaluate_revalidation_requirement_v1(
        baseline=baseline.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline.runtime_identity,
        candidate_runtime_identity=runtime,
    )
    fulfilment = evaluate_revalidation_fulfilment_v1(
        decision=decision,
        baseline=baseline.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline.runtime_identity,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
        replay_report=report,
        replay_repository_sha=runtime.code_sha,
    )
    assert fulfilment.state is ReplayRevalidationFulfilmentState.REVALIDATED
    evaluation = evaluate_revalidation_baseline_transition_v1(
        prior_baseline=baseline,
        decision=decision,
        fulfilment=fulfilment,
        candidate=candidate,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
        replay_report=report,
        replay_repository_sha=runtime.code_sha,
    )
    assert evaluation.transition.state is ReplayRevalidationBaselineTransitionState.BASELINE_ADVANCED
    advanced = evaluation.resulting_baseline
    assert advanced is not None
    assert advanced.repository_sha == runtime.code_sha
    assert advanced.fingerprint == candidate
    assert advanced.baseline_digest == evaluation.transition.resulting_baseline_digest
    next_decision = evaluate_revalidation_requirement_v1(
        baseline=advanced.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=advanced.runtime_identity,
        candidate_runtime_identity=runtime,
    )
    assert next_decision.state is ReplayRevalidationState.UNCHANGED


def test_changed_candidate_without_replay_remains_blocked() -> None:
    baseline, candidate, runtime, _ = _changed_material()
    decision = evaluate_revalidation_requirement_v1(
        baseline=baseline.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline.runtime_identity,
        candidate_runtime_identity=runtime,
    )
    fulfilment = evaluate_revalidation_fulfilment_v1(
        decision=decision,
        baseline=baseline.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline.runtime_identity,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
    )
    evaluation = evaluate_revalidation_baseline_transition_v1(
        prior_baseline=baseline,
        decision=decision,
        fulfilment=fulfilment,
        candidate=candidate,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
    )
    assert evaluation.transition.state is (
        ReplayRevalidationBaselineTransitionState.REVALIDATION_REQUIRED
    )
    assert evaluation.resulting_baseline is None
    assert evaluation.transition.resulting_baseline_digest is None


def test_semantic_drift_replay_cannot_advance_baseline() -> None:
    baseline, candidate, runtime, report = _changed_material()
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
    drift_receipts: list[dict[str, object]] = []
    for profile in profiles:
        assert isinstance(profile, dict)
        profile_digest = str(profile["profile_digest"])
        drift_receipts.append(
            build_replay_receipt(
                plan=plan,
                profile=profile,
                observed=observed_by_profile[profile_digest],
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
    decision = evaluate_revalidation_requirement_v1(
        baseline=baseline.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline.runtime_identity,
        candidate_runtime_identity=runtime,
    )
    fulfilment = evaluate_revalidation_fulfilment_v1(
        decision=decision,
        baseline=baseline.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline.runtime_identity,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
        replay_report=drift_report,
        replay_repository_sha=runtime.code_sha,
    )
    assert fulfilment.state is ReplayRevalidationFulfilmentState.REVALIDATION_FAILED
    evaluation = evaluate_revalidation_baseline_transition_v1(
        prior_baseline=baseline,
        decision=decision,
        fulfilment=fulfilment,
        candidate=candidate,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
        replay_report=drift_report,
        replay_repository_sha=runtime.code_sha,
    )
    assert evaluation.transition.state is (
        ReplayRevalidationBaselineTransitionState.REVALIDATION_FAILED
    )
    assert evaluation.resulting_baseline is None


def test_candidate_or_replay_sha_substitution_fails_closed() -> None:
    baseline, candidate, runtime, report = _changed_material()
    decision = evaluate_revalidation_requirement_v1(
        baseline=baseline.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline.runtime_identity,
        candidate_runtime_identity=runtime,
    )
    fulfilment = evaluate_revalidation_fulfilment_v1(
        decision=decision,
        baseline=baseline.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline.runtime_identity,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
        replay_report=report,
        replay_repository_sha=runtime.code_sha,
    )
    with pytest.raises(
        ReplayRevalidationBaselineTransitionError,
        match="repository SHA/RuntimeIdentity substitution",
    ):
        evaluate_revalidation_baseline_transition_v1(
            prior_baseline=baseline,
            decision=decision,
            fulfilment=fulfilment,
            candidate=candidate,
            candidate_runtime_identity=runtime,
            candidate_repository_sha="c" * 40,
            replay_report=report,
            replay_repository_sha=runtime.code_sha,
        )
    with pytest.raises(
        ReplayRevalidationBaselineTransitionError,
        match="invalid upstream revalidation evidence",
    ):
        evaluate_revalidation_baseline_transition_v1(
            prior_baseline=baseline,
            decision=decision,
            fulfilment=fulfilment,
            candidate=candidate,
            candidate_runtime_identity=runtime,
            candidate_repository_sha=runtime.code_sha,
            replay_report=report,
            replay_repository_sha="c" * 40,
        )


def test_stale_decision_fulfilment_cannot_advance_other_candidate() -> None:
    baseline, candidate, runtime, report = _changed_material()
    decision = evaluate_revalidation_requirement_v1(
        baseline=baseline.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline.runtime_identity,
        candidate_runtime_identity=runtime,
    )
    fulfilment = evaluate_revalidation_fulfilment_v1(
        decision=decision,
        baseline=baseline.fingerprint,
        candidate=candidate,
        baseline_runtime_identity=baseline.runtime_identity,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
        replay_report=report,
        replay_repository_sha=runtime.code_sha,
    )
    foreign_runtime = _runtime("c" * 40)
    plan = report["plan"]
    assert isinstance(plan, dict)
    foreign_candidate = _fingerprint(foreign_runtime, plan)
    with pytest.raises(
        ReplayRevalidationBaselineTransitionError,
        match="invalid upstream revalidation evidence",
    ):
        evaluate_revalidation_baseline_transition_v1(
            prior_baseline=baseline,
            decision=decision,
            fulfilment=fulfilment,
            candidate=foreign_candidate,
            candidate_runtime_identity=foreign_runtime,
            candidate_repository_sha=foreign_runtime.code_sha,
            replay_report=report,
            replay_repository_sha=foreign_runtime.code_sha,
        )


def test_transition_authority_and_digest_tamper_are_rejected() -> None:
    baseline, _ = _baseline()
    runtime = baseline.runtime_identity
    candidate = baseline.fingerprint
    decision = evaluate_revalidation_requirement_v1(
        baseline=candidate,
        candidate=candidate,
        baseline_runtime_identity=runtime,
        candidate_runtime_identity=runtime,
    )
    fulfilment = evaluate_revalidation_fulfilment_v1(
        decision=decision,
        baseline=candidate,
        candidate=candidate,
        baseline_runtime_identity=runtime,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
    )
    transition = evaluate_revalidation_baseline_transition_v1(
        prior_baseline=baseline,
        decision=decision,
        fulfilment=fulfilment,
        candidate=candidate,
        candidate_runtime_identity=runtime,
        candidate_repository_sha=runtime.code_sha,
    ).transition
    authority = transition.canonical_dict()
    authority["persistence_authority"] = True
    with pytest.raises(
        ReplayRevalidationBaselineTransitionError,
        match="persistence_authority",
    ):
        ReplayRevalidationBaselineTransitionV1.from_dict(authority)
    tampered = transition.canonical_dict()
    tampered["transition_digest"] = h("wrong-transition")
    with pytest.raises(
        ReplayRevalidationBaselineTransitionError,
        match="transition_digest mismatch",
    ):
        ReplayRevalidationBaselineTransitionV1.from_dict(tampered)
