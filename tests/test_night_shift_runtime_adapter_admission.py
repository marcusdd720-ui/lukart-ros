from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.runtime_adapter_admission import (
    RuntimeAdapterAdmissionPolicy,
    RuntimeAdapterAdmissionStatus,
    RuntimeAdapterArtifact,
    RuntimeAdapterConformanceRun,
    evaluate_runtime_adapter_admission,
)
from core.night_shift.runtime_profiles import RuntimeProfile, load_runtime_profiles
from core.p3.contracts import content_digest

_MATRIX = Path("docs/execution_profiles/NIGHT_SHIFT_RUNTIME_MATRIX_V1.yaml")
REPO_SHA = "a" * 40


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


def _artifact(profile: RuntimeProfile) -> RuntimeAdapterArtifact:
    return RuntimeAdapterArtifact(
        runtime_id=profile.runtime_id,
        adapter_name=profile.adapter,
        module=f"core.night_shift.adapters.{profile.runtime_id}",
        class_name=profile.adapter,
        source_digest=content_digest(
            {"runtime": profile.runtime_id, "source": "adapter"}
        ),
        dependency_lock_digest=content_digest(
            {"runtime": profile.runtime_id, "lock": "uv.lock"}
        ),
        subject_repo_sha=REPO_SHA,
        evidence_refs=(f"artifact:{profile.runtime_id}:adapter",),
    )


def _run(
    profile: RuntimeProfile,
    artifact: RuntimeAdapterArtifact,
    index: int,
) -> RuntimeAdapterConformanceRun:
    return RuntimeAdapterConformanceRun(
        runtime_id=profile.runtime_id,
        artifact_digest=artifact.digest(),
        run_id=f"{profile.runtime_id}-adapter-run-{index:02d}",
        subject_repo_sha=REPO_SHA,
        crash_resume_pass=True,
        idempotent_steps_pass=True,
        deterministic_replay_pass=True,
        durable_timers_pass=True,
        distributed_workers_pass=True,
        evidence_digest=content_digest(
            {
                "runtime": profile.runtime_id,
                "run": index,
                "kind": "adapter-conformance",
            }
        ),
        evidence_refs=(f"artifact:{profile.runtime_id}:conformance:{index}",),
    )


def _fixture(
    profiles: tuple[RuntimeProfile, RuntimeProfile],
) -> tuple[
    tuple[RuntimeAdapterArtifact, ...],
    tuple[RuntimeAdapterConformanceRun, ...],
]:
    artifacts = tuple(_artifact(profile) for profile in profiles)
    by_id = {artifact.runtime_id: artifact for artifact in artifacts}
    runs = tuple(
        _run(profile, by_id[profile.runtime_id], index)
        for profile in profiles
        for index in range(3)
    )
    return artifacts, runs


def test_concrete_adapter_evidence_prepares_signed_binding_change() -> None:
    profiles = _concrete_profiles()
    artifacts, runs = _fixture(profiles)

    result = evaluate_runtime_adapter_admission(
        profiles=profiles,
        artifacts=artifacts,
        runs=runs,
        subject_repo_sha=REPO_SHA,
        policy=RuntimeAdapterAdmissionPolicy(),
    )

    assert (
        result.status
        is RuntimeAdapterAdmissionStatus.READY_FOR_SIGNED_ADAPTER_BINDING_CHANGE
    )
    assert result.blockers == ()
    assert all(
        item.ready_for_signed_adapter_binding_change
        for item in result.candidates
    )
    assert result.automatic_registry_mutation_executed is False
    assert result.automatic_matrix_mutation_executed is False


def test_canonical_placeholder_profiles_remain_blocked() -> None:
    profiles = _candidate_profiles()

    result = evaluate_runtime_adapter_admission(
        profiles=profiles,
        artifacts=(),
        runs=(),
        subject_repo_sha=REPO_SHA,
        policy=RuntimeAdapterAdmissionPolicy(),
    )

    assert result.status is RuntimeAdapterAdmissionStatus.BLOCKED
    assert result.blockers == ("RUNTIME_ADAPTER_ADMISSION_INCOMPLETE",)
    assert all(
        "CANONICAL_PROFILE_STILL_USES_PLACEHOLDER_ADAPTER" in item.blockers
        for item in result.candidates
    )
    assert all(
        "CONCRETE_ADAPTER_ARTIFACT_MISSING" in item.blockers
        for item in result.candidates
    )


def test_policy_threshold_and_auto_mutation_cannot_be_weakened() -> None:
    with pytest.raises(
        NightShiftContractError,
        match="at least three conformance runs",
    ):
        RuntimeAdapterAdmissionPolicy(min_conformance_runs_per_runtime=1)

    with pytest.raises(
        NightShiftContractError,
        match="cannot automatically mutate",
    ):
        RuntimeAdapterAdmissionPolicy(
            automatic_registry_mutation_enabled=True
        )

    with pytest.raises(
        NightShiftContractError,
        match="cannot automatically mutate",
    ):
        RuntimeAdapterAdmissionPolicy(
            automatic_matrix_mutation_enabled=True
        )


def test_placeholder_adapter_artifact_is_rejected() -> None:
    with pytest.raises(
        NightShiftContractError,
        match="placeholder adapter identity",
    ):
        RuntimeAdapterArtifact(
            runtime_id="dbos",
            adapter_name="future_dbos_adapter",
            module="core.night_shift.adapters.dbos",
            class_name="DBOSWorkflowEngine",
            source_digest="a" * 64,
            dependency_lock_digest="b" * 64,
            subject_repo_sha=REPO_SHA,
            evidence_refs=("artifact:dbos:adapter",),
        )


def test_test_synthetic_demo_evidence_is_rejected() -> None:
    profile = _concrete_profiles()[0]
    with pytest.raises(
        NightShiftContractError,
        match="rejects test/synthetic/demo evidence",
    ):
        replace(
            _artifact(profile),
            evidence_refs=("test:fake-adapter",),
        )


def test_duplicate_conformance_run_identity_cannot_inflate_quorum() -> None:
    profiles = _concrete_profiles()
    artifacts, runs = _fixture(profiles)
    duplicated = runs[0]

    with pytest.raises(
        NightShiftContractError,
        match="run ids must be globally unique",
    ):
        evaluate_runtime_adapter_admission(
            profiles=profiles,
            artifacts=artifacts,
            runs=(duplicated, duplicated) + runs[1:],
            subject_repo_sha=REPO_SHA,
            policy=RuntimeAdapterAdmissionPolicy(),
        )


def test_duplicate_evidence_digest_cannot_inflate_quorum() -> None:
    profiles = _concrete_profiles()
    artifacts, runs = _fixture(profiles)
    duplicated_evidence = replace(
        runs[1],
        evidence_digest=runs[0].evidence_digest,
    )

    with pytest.raises(
        NightShiftContractError,
        match="evidence digests must be globally unique",
    ):
        evaluate_runtime_adapter_admission(
            profiles=profiles,
            artifacts=artifacts,
            runs=(runs[0], duplicated_evidence) + runs[2:],
            subject_repo_sha=REPO_SHA,
            policy=RuntimeAdapterAdmissionPolicy(),
        )


def test_conformance_failure_blocks_candidate() -> None:
    profiles = _concrete_profiles()
    artifacts, runs = _fixture(profiles)
    failed = replace(runs[0], crash_resume_pass=False)

    result = evaluate_runtime_adapter_admission(
        profiles=profiles,
        artifacts=artifacts,
        runs=(failed,) + runs[1:],
        subject_repo_sha=REPO_SHA,
        policy=RuntimeAdapterAdmissionPolicy(),
    )

    dbos = next(item for item in result.candidates if item.runtime_id == "dbos")
    assert result.status is RuntimeAdapterAdmissionStatus.BLOCKED
    assert "CONFORMANCE_REQUIREMENTS_FAILED" in dbos.blockers


def test_artifact_is_bound_to_exact_repository_sha() -> None:
    profiles = _concrete_profiles()
    artifacts, runs = _fixture(profiles)

    with pytest.raises(
        NightShiftContractError,
        match="artifact repository SHA mismatch",
    ):
        evaluate_runtime_adapter_admission(
            profiles=profiles,
            artifacts=artifacts,
            runs=runs,
            subject_repo_sha="b" * 40,
            policy=RuntimeAdapterAdmissionPolicy(),
        )


def test_run_is_bound_to_exact_artifact_digest() -> None:
    profiles = _concrete_profiles()
    artifacts, runs = _fixture(profiles)
    stale = replace(runs[0], artifact_digest="f" * 64)

    with pytest.raises(
        NightShiftContractError,
        match="artifact digest mismatch",
    ):
        evaluate_runtime_adapter_admission(
            profiles=profiles,
            artifacts=artifacts,
            runs=(stale,) + runs[1:],
            subject_repo_sha=REPO_SHA,
            policy=RuntimeAdapterAdmissionPolicy(),
        )


def test_result_digest_is_input_order_independent() -> None:
    profiles = _concrete_profiles()
    artifacts, runs = _fixture(profiles)
    policy = RuntimeAdapterAdmissionPolicy()

    first = evaluate_runtime_adapter_admission(
        profiles=profiles,
        artifacts=artifacts,
        runs=runs,
        subject_repo_sha=REPO_SHA,
        policy=policy,
    )
    second = evaluate_runtime_adapter_admission(
        profiles=tuple(reversed(profiles)),
        artifacts=tuple(reversed(artifacts)),
        runs=tuple(reversed(runs)),
        subject_repo_sha=REPO_SHA,
        policy=policy,
    )

    assert first.digest() == second.digest()

def test_artifact_adapter_identity_must_match_profile() -> None:
    profiles = _concrete_profiles()
    artifacts, runs = _fixture(profiles)
    mismatched = replace(artifacts[0], adapter_name="DifferentAdapter")

    with pytest.raises(
        NightShiftContractError,
        match="does not match runtime profile",
    ):
        evaluate_runtime_adapter_admission(
            profiles=profiles,
            artifacts=(mismatched, artifacts[1]),
            runs=runs,
            subject_repo_sha=REPO_SHA,
            policy=RuntimeAdapterAdmissionPolicy(),
        )


def test_conformance_evidence_digest_cannot_be_reused_across_runtimes() -> None:
    profiles = _concrete_profiles()
    artifacts, runs = _fixture(profiles)
    temporal_index = next(
        index for index, run in enumerate(runs) if run.runtime_id == "temporal"
    )
    reused = replace(
        runs[temporal_index],
        evidence_digest=runs[0].evidence_digest,
    )
    mutated = tuple(
        reused if index == temporal_index else run
        for index, run in enumerate(runs)
    )

    with pytest.raises(
        NightShiftContractError,
        match="globally unique",
    ):
        evaluate_runtime_adapter_admission(
            profiles=profiles,
            artifacts=artifacts,
            runs=mutated,
            subject_repo_sha=REPO_SHA,
            policy=RuntimeAdapterAdmissionPolicy(),
        )

def test_conformance_test_evidence_namespace_is_rejected() -> None:
    profiles = _concrete_profiles()
    _, runs = _fixture(profiles)

    with pytest.raises(
        NightShiftContractError,
        match="conformance rejects test/synthetic/demo evidence",
    ):
        replace(
            runs[0],
            evidence_refs=("test:fake-conformance",),
        )


def test_non_boolean_conformance_pass_flag_is_rejected() -> None:
    profiles = _concrete_profiles()
    artifacts, runs = _fixture(profiles)

    with pytest.raises(
        NightShiftContractError,
        match="pass flags must be booleans",
    ):
        replace(runs[0], crash_resume_pass="false")  # type: ignore[arg-type]
