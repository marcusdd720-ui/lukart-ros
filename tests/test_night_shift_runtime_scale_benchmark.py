from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.runtime_profiles import (
    RuntimeEvidence,
    RuntimeProfile,
    RuntimeRequirements,
    load_runtime_profiles,
)
from core.night_shift.runtime_scale_benchmark import (
    RuntimeBenchmarkPolicy,
    RuntimeBenchmarkSample,
    RuntimeScaleBenchmarkStatus,
    evaluate_runtime_scale_benchmark,
)

_MATRIX = Path("docs/execution_profiles/NIGHT_SHIFT_RUNTIME_MATRIX_V1.yaml")


def _candidate_profiles() -> tuple[RuntimeProfile, RuntimeProfile]:
    profiles = load_runtime_profiles(_MATRIX)
    dbos = next(item for item in profiles if item.runtime_id == "dbos")
    temporal = next(item for item in profiles if item.runtime_id == "temporal")
    return dbos, temporal
def _validated_profiles() -> tuple[RuntimeProfile, RuntimeProfile]:
    dbos, temporal = _candidate_profiles()
    return (
        replace(
            dbos,
            adapter="DBOSWorkflowEngine",
            evidence=RuntimeEvidence.VALIDATED,
        ),
        replace(
            temporal,
            adapter="TemporalWorkflowEngine",
            evidence=RuntimeEvidence.VALIDATED,
        ),
    )


def _sample(
    profile: RuntimeProfile,
    index: int,
    *,
    crash: bool = True,
    idempotency: bool = True,
    replay: bool = True,
    timer: bool = True,
    distributed: bool = True,
) -> RuntimeBenchmarkSample:
    return RuntimeBenchmarkSample(
        runtime_profile_digest=profile.digest(),
        sample_id=f"{profile.runtime_id}-{index:02d}",
        crash_resume_pass=crash,
        idempotency_pass=idempotency,
        deterministic_replay_pass=replay,
        durable_timer_pass=timer,
        distributed_workers_pass=distributed,
        setup_ms=100 + index,
        recovery_ms=50 + index,
        evidence_refs=(f"test:{profile.runtime_id}:{index}",),
    )


def _samples(
    profiles: tuple[RuntimeProfile, RuntimeProfile],
    *,
    count: int = 2,
) -> tuple[RuntimeBenchmarkSample, ...]:
    return tuple(
        _sample(profile, index)
        for profile in profiles
        for index in range(count)
    )


def _scale_requirements() -> RuntimeRequirements:
    return RuntimeRequirements(
        crash_resume=True,
        idempotent_steps=True,
        deterministic_replay=False,
        durable_timers=True,
        distributed_workers=True,
    )


def test_documented_placeholder_adapters_block_scale_readiness() -> None:
    profiles = _candidate_profiles()
    result = evaluate_runtime_scale_benchmark(
        profiles=profiles,
        samples=_samples(profiles),
        policy=RuntimeBenchmarkPolicy(min_samples_per_runtime=2),
        requirements=_scale_requirements(),
    )

    assert result.status is RuntimeScaleBenchmarkStatus.BLOCKED
    assert result.blockers == ("BENCHMARK_EVIDENCE_INCOMPLETE",)
    assert result.eligible_runtime_ids == ()
    for candidate in result.candidates:
        assert "EVIDENCE_NOT_VALIDATED" in candidate.rejection_reasons
        assert "ADAPTER_NOT_CONCRETE" in candidate.rejection_reasons
    assert result.automatic_scale_promotion_executed is False


def test_validated_concrete_benchmark_becomes_ready_for_human() -> None:
    profiles = _validated_profiles()
    result = evaluate_runtime_scale_benchmark(
        profiles=profiles,
        samples=_samples(profiles),
        policy=RuntimeBenchmarkPolicy(min_samples_per_runtime=2),
        requirements=_scale_requirements(),
    )

    assert result.status is RuntimeScaleBenchmarkStatus.READY_FOR_HUMAN
    assert result.blockers == ()
    assert result.eligible_runtime_ids == ("dbos", "temporal")
    assert result.automatic_scale_promotion_executed is False
    assert all(candidate.max_recovery_ms == 51 for candidate in result.candidates)


def test_deterministic_replay_can_exclude_dbos_without_invalidating_benchmark() -> None:
    dbos, temporal = _validated_profiles()
    samples = (
        _sample(dbos, 0, replay=False),
        _sample(dbos, 1, replay=False),
        _sample(temporal, 0, replay=True),
        _sample(temporal, 1, replay=True),
    )
    result = evaluate_runtime_scale_benchmark(
        profiles=(dbos, temporal),
        samples=samples,
        policy=RuntimeBenchmarkPolicy(min_samples_per_runtime=2),
        requirements=replace(_scale_requirements(), deterministic_replay=True),
    )

    assert result.status is RuntimeScaleBenchmarkStatus.READY_FOR_HUMAN
    assert result.eligible_runtime_ids == ("temporal",)
    dbos_result = next(item for item in result.candidates if item.runtime_id == "dbos")
    assert "PROFILE_REQUIREMENTS_UNMET" in dbos_result.rejection_reasons
    assert "OBSERVATION_REQUIREMENTS_UNMET" in dbos_result.rejection_reasons


def test_insufficient_samples_fail_closed() -> None:
    profiles = _validated_profiles()
    result = evaluate_runtime_scale_benchmark(
        profiles=profiles,
        samples=_samples(profiles, count=1),
        policy=RuntimeBenchmarkPolicy(min_samples_per_runtime=2),
        requirements=_scale_requirements(),
    )

    assert result.status is RuntimeScaleBenchmarkStatus.BLOCKED
    assert result.blockers == ("BENCHMARK_EVIDENCE_INCOMPLETE",)
    assert all(
        "INSUFFICIENT_SAMPLES" in candidate.rejection_reasons
        for candidate in result.candidates
    )


def test_no_runtime_satisfying_observed_requirements_blocks_selection() -> None:
    profiles = _validated_profiles()
    samples = tuple(
        _sample(profile, index, timer=False)
        for profile in profiles
        for index in range(2)
    )
    result = evaluate_runtime_scale_benchmark(
        profiles=profiles,
        samples=samples,
        policy=RuntimeBenchmarkPolicy(min_samples_per_runtime=2),
        requirements=_scale_requirements(),
    )

    assert result.status is RuntimeScaleBenchmarkStatus.BLOCKED
    assert result.blockers == ("NO_RUNTIME_SATISFIES_SCALE_REQUIREMENTS",)
    assert result.eligible_runtime_ids == ()


def test_duplicate_sample_identity_cannot_inflate_evidence_count() -> None:
    profiles = _validated_profiles()
    duplicated = _sample(profiles[0], 0)
    samples = (
        duplicated,
        duplicated,
        duplicated,
        _sample(profiles[1], 0),
        _sample(profiles[1], 1),
        _sample(profiles[1], 2),
    )

    with pytest.raises(
        NightShiftContractError,
        match="sample ids must be unique",
    ):
        evaluate_runtime_scale_benchmark(
            profiles=profiles,
            samples=samples,
            policy=RuntimeBenchmarkPolicy(min_samples_per_runtime=3),
            requirements=_scale_requirements(),
        )


def test_stale_or_unknown_profile_sample_is_rejected() -> None:
    profiles = _validated_profiles()
    stale = replace(
        _sample(profiles[0], 0),
        runtime_profile_digest="a" * 64,
    )
    with pytest.raises(
        NightShiftContractError,
        match="stale or unknown profile",
    ):
        evaluate_runtime_scale_benchmark(
            profiles=profiles,
            samples=(stale,),
            policy=RuntimeBenchmarkPolicy(min_samples_per_runtime=1),
            requirements=_scale_requirements(),
        )


def test_benchmark_digest_is_independent_of_sample_input_order() -> None:
    profiles = _validated_profiles()
    samples = _samples(profiles)
    policy = RuntimeBenchmarkPolicy(min_samples_per_runtime=2)
    requirements = _scale_requirements()

    first = evaluate_runtime_scale_benchmark(
        profiles=profiles,
        samples=samples,
        policy=policy,
        requirements=requirements,
    )
    second = evaluate_runtime_scale_benchmark(
        profiles=profiles,
        samples=tuple(reversed(samples)),
        policy=policy,
        requirements=requirements,
    )

    assert first.digest() == second.digest()


def test_v215_policy_cannot_change_candidates_or_auto_promote() -> None:
    with pytest.raises(NightShiftContractError, match="exactly DBOS and Temporal"):
        RuntimeBenchmarkPolicy(candidate_runtime_ids=("dbos",))

    with pytest.raises(NightShiftContractError, match="cannot enable automatic"):
        RuntimeBenchmarkPolicy(automatic_scale_promotion_enabled=True)
