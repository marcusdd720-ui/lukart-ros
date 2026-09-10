from __future__ import annotations

from copy import deepcopy

import pytest

from core.cross_environment_replay_v1 import (
    ReplayExecutionStatus,
    build_environment_profile,
    build_observed_environment_receipt,
    build_replay_plan,
    build_replay_receipt,
    build_replay_report,
    digest_value,
)
from core.long_range_health_v1 import (
    HealthDimensionState,
    LongRangeHealthReportV1,
    LongRangeHealthState,
)
from core.periodic_replay_revalidation_v1 import (
    PeriodicReplayCadencePolicyV1,
    PeriodicReplayError,
    PeriodicReplayEvaluationV1,
    PeriodicReplayObservationV1,
    PeriodicReplayState,
    build_periodic_replay_observation_v1,
    evaluate_periodic_replay_v1,
    verify_observation_chain_v1,
    verify_observation_evidence_v1,
)

CASE_ID = "CASE-LRD-01L-0001"
REPOSITORY_SHA = "a" * 40
D = {
    "lock": "1" * 64,
    "canon": "2" * 64,
    "migration": "3" * 64,
    "crypto": "4" * 64,
    "bundle": "5" * 64,
    "verifier": "6" * 64,
    "environment_policy": "7" * 64,
    "ssc": "8" * 64,
    "replay_policy": "9" * 64,
    "semantic": "a" * 64,
    "invariants": "b" * 64,
    "freshness": "c" * 64,
    "drift": "d" * 64,
    "crypto_evidence": "e" * 64,
    "portability": "f" * 64,
    "recovery": "0" * 64,
}


def _snapshot() -> dict[str, object]:
    inventory: list[object] = []
    return {
        "os_family": "Linux",
        "os_release": "test-release",
        "os_build": "test-build",
        "cpu_architecture": "x86_64",
        "python_implementation": "CPython",
        "python_version": "3.11.9",
        "python_cache_tag": "cpython-311",
        "python_soabi": "cpython-311-x86_64-linux-gnu",
        "openssl_identity": "OpenSSL-test",
        "sqlite_identity": "3-test",
        "libc_runtime_identity": "glibc:test",
        "locale": "C.UTF-8",
        "timezone": "UTC",
        "filesystem_semantics": {
            "os_name": "posix",
            "path_separator": "/",
            "alt_separator": None,
            "case_sensitive_probe": True,
            "supports_symlinks": True,
        },
        "installed_artifacts": inventory,
        "installed_artifact_inventory_digest": digest_value(inventory),
    }


def _cross_environment_report(
    *,
    lrd01d_classification: str = "NO_DRIFT",
) -> dict[str, object]:
    snapshot = _snapshot()
    physical = str(snapshot["installed_artifact_inventory_digest"])
    profile_a = build_environment_profile(
        name="linux-a",
        observed=snapshot,
        dependency_lock_digest=D["lock"],
        physical_dependency_artifact_identities=(physical,),
        canonicalization_profile_digest=D["canon"],
        migration_registry_digest=D["migration"],
        crypto_profile_digest=D["crypto"],
        lrd01i_bundle_digest=D["bundle"],
        replay_verifier_digest=D["verifier"],
        environment_policy_digest=D["environment_policy"],
    )
    profile_b = build_environment_profile(
        name="linux-b",
        observed=snapshot,
        dependency_lock_digest=D["lock"],
        physical_dependency_artifact_identities=(physical,),
        canonicalization_profile_digest=D["canon"],
        migration_registry_digest=D["migration"],
        crypto_profile_digest=D["crypto"],
        lrd01i_bundle_digest=D["bundle"],
        replay_verifier_digest=D["verifier"],
        environment_policy_digest=D["environment_policy"],
    )
    profile_ids = [str(profile_a["profile_digest"]), str(profile_b["profile_digest"])]
    plan = build_replay_plan(
        lrd01i_bundle_digest=D["bundle"],
        ssc02_manifest_digest=D["ssc"],
        environment_profile_digests=profile_ids,
        reference_profile_digest=profile_ids[0],
        replay_policy_digest=D["replay_policy"],
        migration_registry_digest=D["migration"],
        canonicalization_profile_digest=D["canon"],
        crypto_profile_digest=D["crypto"],
        expected_matrix=profile_ids,
        hard_bounds={"max_profiles": 2},
    )
    observations = []
    receipts = []
    for profile in (profile_a, profile_b):
        observed = build_observed_environment_receipt(
            snapshot,
            declared_profile_digest=str(profile["profile_digest"]),
            verifier_digest=D["verifier"],
            environment_policy_digest=D["environment_policy"],
        )
        observations.append(observed)
        receipts.append(
            build_replay_receipt(
                plan=plan,
                profile=profile,
                observed=observed,
                verifier_digest=D["verifier"],
                semantic_result_identity=D["semantic"],
                invariant_report_identity=D["invariants"],
                lrd01d_classification=lrd01d_classification,
                execution_status=ReplayExecutionStatus.VERIFIED,
            )
        )
    return build_replay_report(
        plan=plan,
        profiles=(profile_a, profile_b),
        observed_environments=observations,
        receipts=receipts,
    )


def _health(
    *,
    state: LongRangeHealthState = LongRangeHealthState.HEALTHY,
    evaluated_at: int = 990,
) -> LongRangeHealthReportV1:
    if state is LongRangeHealthState.HEALTHY:
        dimension = HealthDimensionState.FRESH
        violations: tuple[str, ...] = ()
    else:
        dimension = HealthDimensionState.STALE
        violations = ("crypto_renewal_stale",)
    return LongRangeHealthReportV1(
        case_id=CASE_ID,
        evaluated_at=evaluated_at,
        freshness_policy_digest=D["freshness"],
        drift_report_digest=D["drift"],
        crypto_state=dimension,
        portability_state=dimension,
        recovery_state=dimension,
        crypto_evidence_digest=D["crypto_evidence"],
        portability_evidence_digest=D["portability"],
        recovery_evidence_digest=D["recovery"],
        state=state,
        violations=violations,
    )


def _observation(
    *,
    observed_at: int = 1000,
    health: LongRangeHealthReportV1 | None = None,
    classification: str = "NO_DRIFT",
    previous: PeriodicReplayObservationV1 | None = None,
) -> PeriodicReplayObservationV1:
    return build_periodic_replay_observation_v1(
        case_id=CASE_ID,
        repository_sha=REPOSITORY_SHA,
        observed_at=observed_at,
        cross_environment_report=_cross_environment_report(
            lrd01d_classification=classification
        ),
        long_range_health_report=health or _health(evaluated_at=min(990, observed_at)),
        previous=previous,
    )


def test_policy_is_content_addressed_and_has_no_scheduler_authority() -> None:
    policy = PeriodicReplayCadencePolicyV1(
        effective_at=0,
        max_replay_age_seconds=1000,
        due_window_seconds=200,
    )
    body = policy.canonical_dict()
    assert len(policy.policy_digest) == 64
    assert body["scheduler_authority"] is False
    assert body["required_health_state"] == "HEALTHY"
    with pytest.raises(PeriodicReplayError, match="less than"):
        PeriodicReplayCadencePolicyV1(0, 100, 100)


def test_verified_upstream_evidence_builds_content_addressed_observation() -> None:
    cross = _cross_environment_report()
    health = _health()
    observation = build_periodic_replay_observation_v1(
        case_id=CASE_ID,
        repository_sha=REPOSITORY_SHA,
        observed_at=1000,
        cross_environment_report=cross,
        long_range_health_report=health,
    )
    assert observation.upstream_revalidation_pass is True
    assert observation.upstream_violations == ()
    assert observation.lrd01i_bundle_digest == D["bundle"]
    assert verify_observation_evidence_v1(
        observation,
        cross_environment_report=cross,
        long_range_health_report=health,
    ) == observation.observation_digest
    assert PeriodicReplayObservationV1.from_dict(observation.canonical_dict()) == observation


def test_current_due_and_overdue_boundaries_are_deterministic() -> None:
    policy = PeriodicReplayCadencePolicyV1(0, 1000, 200)
    observation = _observation()
    current = evaluate_periodic_replay_v1(
        policy=policy,
        evaluated_at=1799,
        observations=(observation,),
    )
    due = evaluate_periodic_replay_v1(
        policy=policy,
        evaluated_at=1800,
        observations=(observation,),
    )
    overdue = evaluate_periodic_replay_v1(
        policy=policy,
        evaluated_at=2001,
        observations=(observation,),
    )
    assert current.state is PeriodicReplayState.CURRENT
    assert due.state is PeriodicReplayState.DUE
    assert overdue.state is PeriodicReplayState.OVERDUE
    assert overdue.violations == ("periodic_replay_overdue",)
    assert PeriodicReplayEvaluationV1.from_dict(overdue.canonical_dict()) == overdue


def test_missing_observation_is_unverifiable_not_current() -> None:
    result = evaluate_periodic_replay_v1(
        policy=PeriodicReplayCadencePolicyV1(0, 1000, 200),
        evaluated_at=500,
        observations=(),
    )
    assert result.state is PeriodicReplayState.UNVERIFIABLE
    assert result.latest_observation_digest is None
    assert result.latest_observation_age_seconds is None


def test_missing_initial_drill_becomes_overdue_after_policy_deadline() -> None:
    result = evaluate_periodic_replay_v1(
        policy=PeriodicReplayCadencePolicyV1(100, 1000, 200),
        evaluated_at=1101,
        observations=(),
    )
    assert result.state is PeriodicReplayState.OVERDUE
    assert result.violations == ("initial_periodic_replay_missing",)


def test_historical_gap_is_detected_even_after_a_later_success() -> None:
    policy = PeriodicReplayCadencePolicyV1(0, 500, 100)
    first = _observation(observed_at=100)
    second = _observation(observed_at=700, previous=first)
    assert len(verify_observation_chain_v1((first, second))) == 64
    result = evaluate_periodic_replay_v1(
        policy=policy,
        evaluated_at=750,
        observations=(first, second),
    )
    assert result.state is PeriodicReplayState.OVERDUE
    assert result.violations == ("historical_periodic_replay_gap",)


def test_swapped_or_duplicate_observation_chain_fails_closed() -> None:
    first = _observation(observed_at=1000)
    second = _observation(observed_at=1100, previous=first)
    with pytest.raises(PeriodicReplayError, match="must not have a predecessor"):
        verify_observation_chain_v1((second, first))
    with pytest.raises(PeriodicReplayError, match="duplicate observation"):
        verify_observation_chain_v1((first, first))


def test_unhealthy_lrd01e_evidence_is_unverifiable() -> None:
    observation = _observation(health=_health(state=LongRangeHealthState.STALE))
    assert observation.upstream_revalidation_pass is False
    result = evaluate_periodic_replay_v1(
        policy=PeriodicReplayCadencePolicyV1(0, 1000, 200),
        evaluated_at=1100,
        observations=(observation,),
    )
    assert result.state is PeriodicReplayState.UNVERIFIABLE
    assert "long_range_health_not_healthy" in result.violations


def test_semantic_drift_from_lrd01k_is_not_promoted_to_periodic_pass() -> None:
    observation = _observation(classification="SEMANTIC_DRIFT")
    assert observation.upstream_revalidation_pass is False
    assert observation.upstream_violations == (
        "cross_environment_semantic_revalidation_failed",
    )


def test_observation_chain_is_monotonic_and_bundle_scoped() -> None:
    first = _observation(observed_at=1000)
    second = _observation(observed_at=1100, previous=first)
    assert second.previous_observation_digest == first.observation_digest
    with pytest.raises(PeriodicReplayError, match="timestamp must increase"):
        _observation(observed_at=1000, previous=first)
    wrong_bundle = deepcopy(_cross_environment_report())
    plan = wrong_bundle["plan"]
    assert isinstance(plan, dict)
    plan["lrd01i_bundle_digest"] = "f" * 64
    with pytest.raises(PeriodicReplayError, match="invalid LRD-01K report"):
        build_periodic_replay_observation_v1(
            case_id=CASE_ID,
            repository_sha=REPOSITORY_SHA,
            observed_at=1100,
            cross_environment_report=wrong_bundle,
            long_range_health_report=_health(),
            previous=first,
        )


def test_evidence_substitution_and_content_tamper_fail_closed() -> None:
    cross = _cross_environment_report()
    health = _health()
    observation = build_periodic_replay_observation_v1(
        case_id=CASE_ID,
        repository_sha=REPOSITORY_SHA,
        observed_at=1000,
        cross_environment_report=cross,
        long_range_health_report=health,
    )
    changed_health = LongRangeHealthReportV1(
        case_id=CASE_ID,
        evaluated_at=991,
        freshness_policy_digest=D["freshness"],
        drift_report_digest=D["drift"],
        crypto_state=HealthDimensionState.FRESH,
        portability_state=HealthDimensionState.FRESH,
        recovery_state=HealthDimensionState.FRESH,
        crypto_evidence_digest=D["crypto_evidence"],
        portability_evidence_digest=D["portability"],
        recovery_evidence_digest=D["recovery"],
        state=LongRangeHealthState.HEALTHY,
        violations=(),
    )
    with pytest.raises(PeriodicReplayError, match="health report substitution"):
        verify_observation_evidence_v1(
            observation,
            cross_environment_report=cross,
            long_range_health_report=changed_health,
        )
    tampered = observation.canonical_dict()
    tampered["repository_sha"] = "b" * 40
    with pytest.raises(PeriodicReplayError, match="observation_digest mismatch"):
        PeriodicReplayObservationV1.from_dict(tampered)


def test_unknown_fields_invalid_sha_and_future_time_fail_closed() -> None:
    observation = _observation()
    unknown = observation.canonical_dict()
    unknown["scheduler_override"] = True
    with pytest.raises(PeriodicReplayError, match="unknown=scheduler_override"):
        PeriodicReplayObservationV1.from_dict(unknown)
    with pytest.raises(PeriodicReplayError, match="full Git SHA"):
        build_periodic_replay_observation_v1(
            case_id=CASE_ID,
            repository_sha="abc",
            observed_at=1000,
            cross_environment_report=_cross_environment_report(),
            long_range_health_report=_health(),
        )
    with pytest.raises(PeriodicReplayError, match="future"):
        evaluate_periodic_replay_v1(
            policy=PeriodicReplayCadencePolicyV1(0, 1000, 200),
            evaluated_at=999,
            observations=(observation,),
        )


def test_scheduler_authority_cannot_be_smuggled_into_evaluation() -> None:
    evaluation = evaluate_periodic_replay_v1(
        policy=PeriodicReplayCadencePolicyV1(0, 1000, 200),
        evaluated_at=1100,
        observations=(_observation(),),
    )
    payload = evaluation.canonical_dict()
    payload["scheduler_authority"] = True
    with pytest.raises(PeriodicReplayError, match="scheduler authority"):
        PeriodicReplayEvaluationV1.from_dict(payload)
