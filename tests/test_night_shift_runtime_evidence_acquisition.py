from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.runtime_evidence_acquisition import (
    RuntimeEvidenceAcquisitionPolicy,
    RuntimeEvidenceAcquisitionStatus,
    RuntimeEvidenceRun,
    evaluate_runtime_evidence_acquisition,
)
from core.night_shift.runtime_profiles import (
    RuntimeEvidence,
    RuntimeProfile,
    load_runtime_profiles,
)
from core.night_shift.runtime_scale_benchmark import RuntimeBenchmarkSample
from core.p3.contracts import content_digest

_MATRIX = Path("docs/execution_profiles/NIGHT_SHIFT_RUNTIME_MATRIX_V1.yaml")


def _candidate_profiles() -> tuple[RuntimeProfile, RuntimeProfile]:
    profiles = load_runtime_profiles(_MATRIX)
    dbos = next(item for item in profiles if item.runtime_id == "dbos")
    temporal = next(item for item in profiles if item.runtime_id == "temporal")
    return dbos, temporal


def _concrete_profiles() -> tuple[RuntimeProfile, RuntimeProfile]:
    dbos, temporal = _candidate_profiles()
    return (
        replace(dbos, adapter="DBOSWorkflowEngine"),
        replace(temporal, adapter="TemporalWorkflowEngine"),
    )


def _sample(
    profile: RuntimeProfile,
    index: int,
    *,
    evidence_ref: str | None = None,
) -> RuntimeBenchmarkSample:
    return RuntimeBenchmarkSample(
        runtime_profile_digest=profile.digest(),
        sample_id=f"{profile.runtime_id}-sample-{index:02d}",
        crash_resume_pass=True,
        idempotency_pass=True,
        deterministic_replay_pass=True,
        durable_timer_pass=True,
        distributed_workers_pass=True,
        setup_ms=100 + index,
        recovery_ms=50 + index,
        evidence_refs=(evidence_ref or f"artifact:{profile.runtime_id}:sample:{index}",),
    )


def _run(
    profile: RuntimeProfile,
    sample: RuntimeBenchmarkSample,
    index: int,
    *,
    synthetic: bool = False,
    adapter: str | None = None,
    evidence_ref: str | None = None,
    artifact_digest: str | None = None,
) -> RuntimeEvidenceRun:
    return RuntimeEvidenceRun(
        runtime_id=profile.runtime_id,
        runtime_profile_digest=profile.digest(),
        benchmark_sample_digest=sample.digest(),
        run_id=f"{profile.runtime_id}-run-{index:02d}",
        executor_id=f"executor-{index:02d}",
        adapter=adapter or profile.adapter,
        adapter_version="1.2.3",
        environment_digest=content_digest(
            {"environment": profile.runtime_id, "run": index}
        ),
        artifact_digest=artifact_digest
        or content_digest({"artifact": profile.runtime_id, "run": index}),
        evidence_refs=(evidence_ref or f"artifact:{profile.runtime_id}:run:{index}",),
        synthetic=synthetic,
    )


def _evidence_set(
    profiles: tuple[RuntimeProfile, RuntimeProfile],
    *,
    count: int = 3,
) -> tuple[tuple[RuntimeBenchmarkSample, ...], tuple[RuntimeEvidenceRun, ...]]:
    samples = tuple(
        _sample(profile, index)
        for profile in profiles
        for index in range(count)
    )
    by_key = {
        (sample.runtime_profile_digest, sample.sample_id): sample
        for sample in samples
    }
    runs = tuple(
        _run(
            profile,
            by_key[(profile.digest(), f"{profile.runtime_id}-sample-{index:02d}")],
            index,
        )
        for profile in profiles
        for index in range(count)
    )
    return samples, runs


def test_documented_placeholder_adapters_block_acquisition() -> None:
    profiles = _candidate_profiles()
    samples, runs = _evidence_set(profiles)
    result = evaluate_runtime_evidence_acquisition(
        profiles=profiles,
        samples=samples,
        runs=runs,
        policy=RuntimeEvidenceAcquisitionPolicy(),
    )
    assert result.status is RuntimeEvidenceAcquisitionStatus.BLOCKED
    assert result.blockers == ("RUNTIME_EVIDENCE_INCOMPLETE",)
    assert all("ADAPTER_NOT_CONCRETE" in item.blockers for item in result.candidates)


def test_concrete_operational_evidence_is_ready_for_human_validation() -> None:
    profiles = _concrete_profiles()
    samples, runs = _evidence_set(profiles)
    result = evaluate_runtime_evidence_acquisition(
        profiles=profiles,
        samples=samples,
        runs=runs,
        policy=RuntimeEvidenceAcquisitionPolicy(),
    )
    assert (
        result.status
        is RuntimeEvidenceAcquisitionStatus.READY_FOR_HUMAN_VALIDATION
    )
    assert result.blockers == ()
    assert result.ready_runtime_ids == ("dbos", "temporal")
    assert all(profile.evidence is RuntimeEvidence.DOCUMENTED for profile in profiles)
    assert result.automatic_profile_validation_executed is False


def test_non_sha256_content_address_is_rejected() -> None:
    profiles = _concrete_profiles()
    sample = _sample(profiles[0], 0)

    with pytest.raises(
        NightShiftContractError,
        match="lowercase SHA-256",
    ):
        replace(
            _run(profiles[0], sample, 0),
            environment_digest="z" * 64,
        )


def test_duplicate_run_identity_cannot_inflate_evidence() -> None:
    profiles = _concrete_profiles()
    samples, runs = _evidence_set(profiles)
    with pytest.raises(NightShiftContractError, match="run ids must be unique"):
        evaluate_runtime_evidence_acquisition(
            profiles=profiles,
            samples=samples,
            runs=runs + (runs[0],),
            policy=RuntimeEvidenceAcquisitionPolicy(),
        )


def test_synthetic_run_blocks_candidate() -> None:
    profiles = _concrete_profiles()
    samples, runs = _evidence_set(profiles)
    result = evaluate_runtime_evidence_acquisition(
        profiles=profiles,
        samples=samples,
        runs=(replace(runs[0], synthetic=True),) + runs[1:],
        policy=RuntimeEvidenceAcquisitionPolicy(),
    )
    dbos = next(item for item in result.candidates if item.runtime_id == "dbos")
    assert result.status is RuntimeEvidenceAcquisitionStatus.BLOCKED
    assert "SYNTHETIC_EVIDENCE_FORBIDDEN" in dbos.blockers


def test_test_namespace_in_sample_evidence_is_rejected() -> None:
    profiles = _concrete_profiles()
    samples, runs = _evidence_set(profiles)
    bad_sample = _sample(profiles[0], 0, evidence_ref="test:fake-db")
    amended_samples = (bad_sample,) + samples[1:]
    amended_runs = (
        replace(runs[0], benchmark_sample_digest=bad_sample.digest()),
    ) + runs[1:]
    result = evaluate_runtime_evidence_acquisition(
        profiles=profiles,
        samples=amended_samples,
        runs=amended_runs,
        policy=RuntimeEvidenceAcquisitionPolicy(),
    )
    dbos = next(item for item in result.candidates if item.runtime_id == "dbos")
    assert "NON_OPERATIONAL_EVIDENCE_REF" in dbos.blockers


def test_duplicate_artifact_digests_do_not_count_as_independent_evidence() -> None:
    profiles = _concrete_profiles()
    samples, runs = _evidence_set(profiles)
    shared = content_digest({"same": "artifact"})
    changed = tuple(
        replace(run, artifact_digest=shared)
        if run.runtime_id == "dbos"
        else run
        for run in runs
    )
    result = evaluate_runtime_evidence_acquisition(
        profiles=profiles,
        samples=samples,
        runs=changed,
        policy=RuntimeEvidenceAcquisitionPolicy(),
    )
    dbos = next(item for item in result.candidates if item.runtime_id == "dbos")
    assert result.status is RuntimeEvidenceAcquisitionStatus.BLOCKED
    assert "INSUFFICIENT_DISTINCT_ARTIFACTS" in dbos.blockers


def test_unknown_sample_digest_is_rejected() -> None:
    profiles = _concrete_profiles()
    samples, runs = _evidence_set(profiles)
    bad = replace(runs[0], benchmark_sample_digest="a" * 64)
    with pytest.raises(
        NightShiftContractError,
        match="unknown benchmark sample",
    ):
        evaluate_runtime_evidence_acquisition(
            profiles=profiles,
            samples=samples,
            runs=(bad,) + runs[1:],
            policy=RuntimeEvidenceAcquisitionPolicy(),
        )


def test_adapter_identity_mismatch_blocks_candidate() -> None:
    profiles = _concrete_profiles()
    samples, runs = _evidence_set(profiles)
    result = evaluate_runtime_evidence_acquisition(
        profiles=profiles,
        samples=samples,
        runs=(replace(runs[0], adapter="UnexpectedAdapter"),) + runs[1:],
        policy=RuntimeEvidenceAcquisitionPolicy(),
    )
    dbos = next(item for item in result.candidates if item.runtime_id == "dbos")
    assert "ADAPTER_IDENTITY_MISMATCH" in dbos.blockers


def test_result_digest_is_independent_of_input_order() -> None:
    profiles = _concrete_profiles()
    samples, runs = _evidence_set(profiles)
    policy = RuntimeEvidenceAcquisitionPolicy()
    first = evaluate_runtime_evidence_acquisition(
        profiles=profiles,
        samples=samples,
        runs=runs,
        policy=policy,
    )
    second = evaluate_runtime_evidence_acquisition(
        profiles=profiles,
        samples=tuple(reversed(samples)),
        runs=tuple(reversed(runs)),
        policy=policy,
    )
    assert first.digest() == second.digest()


def test_v216_policy_cannot_weaken_evidence_thresholds() -> None:
    with pytest.raises(
        NightShiftContractError,
        match="at least three runs",
    ):
        RuntimeEvidenceAcquisitionPolicy(min_runs_per_runtime=1)

    with pytest.raises(
        NightShiftContractError,
        match="cannot weaken forbidden evidence prefixes",
    ):
        RuntimeEvidenceAcquisitionPolicy(
            forbidden_evidence_prefixes=("artifact:",),
        )


def test_v216_policy_cannot_change_candidates_or_auto_validate() -> None:
    with pytest.raises(
        NightShiftContractError,
        match="exactly DBOS and Temporal",
    ):
        RuntimeEvidenceAcquisitionPolicy(candidate_runtime_ids=("dbos",))

    with pytest.raises(
        NightShiftContractError,
        match="cannot automatically validate",
    ):
        RuntimeEvidenceAcquisitionPolicy(
            automatic_profile_validation_enabled=True
        )
