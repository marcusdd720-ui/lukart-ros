"""Fail-closed runtime adapter admission boundary for Night Shift V2-18."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from core.p3.contracts import content_digest, require_hex_digest

from .contracts import NightShiftContractError
from .runtime_profiles import RuntimeProfile


class RuntimeAdapterAdmissionStatus(StrEnum):
    BLOCKED = "BLOCKED"
    READY_FOR_SIGNED_ADAPTER_BINDING_CHANGE = (
        "READY_FOR_SIGNED_ADAPTER_BINDING_CHANGE"
    )


def _digest(value: str, *, field_name: str) -> str:
    try:
        return require_hex_digest(value, field_name=field_name)
    except ValueError as exc:
        raise NightShiftContractError(str(exc)) from exc


def _git_sha(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if re.fullmatch(r"[0-9a-f]{40}", normalized) is None:
        raise NightShiftContractError(
            f"{field_name} must be a lowercase 40-character Git SHA"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class RuntimeAdapterAdmissionPolicy:
    candidate_runtime_ids: tuple[str, ...] = ("dbos", "temporal")
    min_conformance_runs_per_runtime: int = 3
    automatic_registry_mutation_enabled: bool = False
    automatic_matrix_mutation_enabled: bool = False

    def __post_init__(self) -> None:
        ids = tuple(sorted({item.strip() for item in self.candidate_runtime_ids}))
        if ids != ("dbos", "temporal"):
            raise NightShiftContractError(
                "V2-18 admission requires exactly DBOS and Temporal"
            )
        if self.min_conformance_runs_per_runtime < 3:
            raise NightShiftContractError(
                "runtime adapter admission requires at least three conformance runs"
            )
        if (
            self.automatic_registry_mutation_enabled
            or self.automatic_matrix_mutation_enabled
        ):
            raise NightShiftContractError(
                "V2-18 cannot automatically mutate adapter registry or runtime matrix"
            )
        object.__setattr__(self, "candidate_runtime_ids", ids)

    def digest(self) -> str:
        return content_digest(
            {
                "candidate_runtime_ids": list(self.candidate_runtime_ids),
                "min_conformance_runs_per_runtime": (
                    self.min_conformance_runs_per_runtime
                ),
                "automatic_registry_mutation_enabled": (
                    self.automatic_registry_mutation_enabled
                ),
                "automatic_matrix_mutation_enabled": (
                    self.automatic_matrix_mutation_enabled
                ),
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeAdapterArtifact:
    runtime_id: str
    adapter_name: str
    module: str
    class_name: str
    source_digest: str
    dependency_lock_digest: str
    subject_repo_sha: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        runtime_id = self.runtime_id.strip()
        adapter_name = self.adapter_name.strip()
        module = self.module.strip()
        class_name = self.class_name.strip()
        if not runtime_id or not adapter_name or not module or not class_name:
            raise NightShiftContractError(
                "runtime adapter artifact identity is required"
            )
        if adapter_name.casefold().startswith("future_"):
            raise NightShiftContractError(
                "runtime adapter artifact cannot use placeholder adapter identity"
            )
        source_digest = _digest(self.source_digest, field_name="source_digest")
        lock_digest = _digest(
            self.dependency_lock_digest,
            field_name="dependency_lock_digest",
        )
        repo_sha = _git_sha(self.subject_repo_sha, field_name="subject_repo_sha")
        refs = tuple(sorted({item.strip() for item in self.evidence_refs}))
        if not refs or any(not item for item in refs):
            raise NightShiftContractError(
                "runtime adapter artifact requires evidence refs"
            )
        forbidden = ("test:", "synthetic:", "demo:")
        if any(ref.casefold().startswith(forbidden) for ref in refs):
            raise NightShiftContractError(
                "runtime adapter admission rejects test/synthetic/demo evidence"
            )
        object.__setattr__(self, "runtime_id", runtime_id)
        object.__setattr__(self, "adapter_name", adapter_name)
        object.__setattr__(self, "module", module)
        object.__setattr__(self, "class_name", class_name)
        object.__setattr__(self, "source_digest", source_digest)
        object.__setattr__(self, "dependency_lock_digest", lock_digest)
        object.__setattr__(self, "subject_repo_sha", repo_sha)
        object.__setattr__(self, "evidence_refs", refs)

    def digest(self) -> str:
        return content_digest(
            {
                "runtime_id": self.runtime_id,
                "adapter_name": self.adapter_name,
                "module": self.module,
                "class_name": self.class_name,
                "source_digest": self.source_digest,
                "dependency_lock_digest": self.dependency_lock_digest,
                "subject_repo_sha": self.subject_repo_sha,
                "evidence_refs": list(self.evidence_refs),
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeAdapterConformanceRun:
    runtime_id: str
    artifact_digest: str
    run_id: str
    subject_repo_sha: str
    crash_resume_pass: bool
    idempotent_steps_pass: bool
    deterministic_replay_pass: bool
    durable_timers_pass: bool
    distributed_workers_pass: bool
    evidence_digest: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        runtime_id = self.runtime_id.strip()
        run_id = self.run_id.strip()
        if not runtime_id or not run_id:
            raise NightShiftContractError(
                "runtime adapter conformance identity is required"
            )
        object.__setattr__(
            self,
            "artifact_digest",
            _digest(self.artifact_digest, field_name="artifact_digest"),
        )
        object.__setattr__(
            self,
            "subject_repo_sha",
            _git_sha(self.subject_repo_sha, field_name="subject_repo_sha"),
        )
        object.__setattr__(
            self,
            "evidence_digest",
            _digest(self.evidence_digest, field_name="evidence_digest"),
        )
        bool_fields = (
            self.crash_resume_pass,
            self.idempotent_steps_pass,
            self.deterministic_replay_pass,
            self.durable_timers_pass,
            self.distributed_workers_pass,
        )
        if any(type(value) is not bool for value in bool_fields):
            raise NightShiftContractError(
                "runtime adapter conformance pass flags must be booleans"
            )
        refs = tuple(sorted({item.strip() for item in self.evidence_refs}))
        if not refs or any(not item for item in refs):
            raise NightShiftContractError(
                "runtime adapter conformance requires evidence refs"
            )
        forbidden = ("test:", "synthetic:", "demo:")
        if any(ref.casefold().startswith(forbidden) for ref in refs):
            raise NightShiftContractError(
                "runtime adapter conformance rejects test/synthetic/demo evidence"
            )
        object.__setattr__(self, "runtime_id", runtime_id)
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "evidence_refs", refs)

    def digest(self) -> str:
        return content_digest(
            {
                "runtime_id": self.runtime_id,
                "artifact_digest": self.artifact_digest,
                "run_id": self.run_id,
                "subject_repo_sha": self.subject_repo_sha,
                "crash_resume_pass": self.crash_resume_pass,
                "idempotent_steps_pass": self.idempotent_steps_pass,
                "deterministic_replay_pass": self.deterministic_replay_pass,
                "durable_timers_pass": self.durable_timers_pass,
                "distributed_workers_pass": self.distributed_workers_pass,
                "evidence_digest": self.evidence_digest,
                "evidence_refs": list(self.evidence_refs),
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeAdapterAdmissionCandidate:
    runtime_id: str
    source_profile_digest: str
    artifact_digest: str | None
    conformance_run_digests: tuple[str, ...]
    ready_for_signed_adapter_binding_change: bool
    blockers: tuple[str, ...]

    def digest(self) -> str:
        return content_digest(
            {
                "runtime_id": self.runtime_id,
                "source_profile_digest": self.source_profile_digest,
                "artifact_digest": self.artifact_digest,
                "conformance_run_digests": list(self.conformance_run_digests),
                "ready_for_signed_adapter_binding_change": (
                    self.ready_for_signed_adapter_binding_change
                ),
                "blockers": list(self.blockers),
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeAdapterAdmissionResult:
    status: RuntimeAdapterAdmissionStatus
    policy_digest: str
    subject_repo_sha: str
    candidates: tuple[RuntimeAdapterAdmissionCandidate, ...]
    blockers: tuple[str, ...]
    automatic_registry_mutation_executed: bool = False
    automatic_matrix_mutation_executed: bool = False

    def __post_init__(self) -> None:
        if (
            self.automatic_registry_mutation_executed
            or self.automatic_matrix_mutation_executed
        ):
            raise NightShiftContractError(
                "runtime adapter admission cannot mutate registry or matrix"
            )

    def digest(self) -> str:
        return content_digest(
            {
                "status": self.status.value,
                "policy_digest": self.policy_digest,
                "subject_repo_sha": self.subject_repo_sha,
                "candidates": [item.digest() for item in self.candidates],
                "blockers": list(self.blockers),
                "automatic_registry_mutation_executed": (
                    self.automatic_registry_mutation_executed
                ),
                "automatic_matrix_mutation_executed": (
                    self.automatic_matrix_mutation_executed
                ),
            }
        )


def _run_satisfies_profile(
    run: RuntimeAdapterConformanceRun,
    profile: RuntimeProfile,
) -> bool:
    checks = (
        (profile.crash_resume, run.crash_resume_pass),
        (profile.idempotent_steps, run.idempotent_steps_pass),
        (profile.deterministic_replay, run.deterministic_replay_pass),
        (profile.durable_timers, run.durable_timers_pass),
        (profile.distributed_workers, run.distributed_workers_pass),
    )
    return all((not required) or observed for required, observed in checks)


def evaluate_runtime_adapter_admission(
    *,
    profiles: tuple[RuntimeProfile, ...],
    artifacts: tuple[RuntimeAdapterArtifact, ...],
    runs: tuple[RuntimeAdapterConformanceRun, ...],
    subject_repo_sha: str,
    policy: RuntimeAdapterAdmissionPolicy,
) -> RuntimeAdapterAdmissionResult:
    repo_sha = _git_sha(subject_repo_sha, field_name="subject_repo_sha")
    by_profile = {profile.runtime_id: profile for profile in profiles}
    if len(by_profile) != len(profiles):
        raise NightShiftContractError(
            "runtime adapter admission profiles must be unique"
        )
    if tuple(sorted(by_profile)) != policy.candidate_runtime_ids:
        raise NightShiftContractError(
            "runtime adapter admission requires exactly candidate profiles"
        )

    by_artifact = {artifact.runtime_id: artifact for artifact in artifacts}
    if len(by_artifact) != len(artifacts):
        raise NightShiftContractError(
            "runtime adapter admission artifacts must be unique per runtime"
        )
    unknown_artifacts = set(by_artifact) - set(policy.candidate_runtime_ids)
    if unknown_artifacts:
        raise NightShiftContractError(
            "runtime adapter admission artifact references unknown runtime"
        )

    run_ids = [run.run_id for run in runs]
    if len(set(run_ids)) != len(run_ids):
        raise NightShiftContractError(
            "runtime adapter conformance run ids must be globally unique"
        )
    unknown_runs = [
        run.runtime_id
        for run in runs
        if run.runtime_id not in policy.candidate_runtime_ids
    ]
    if unknown_runs:
        raise NightShiftContractError(
            "runtime adapter conformance run references unknown runtime"
        )
    evidence_digests = [run.evidence_digest for run in runs]
    if len(set(evidence_digests)) != len(evidence_digests):
        raise NightShiftContractError(
            "runtime adapter conformance evidence digests must be globally unique"
        )

    candidates: list[RuntimeAdapterAdmissionCandidate] = []
    for runtime_id in policy.candidate_runtime_ids:
        profile = by_profile[runtime_id]
        artifact = by_artifact.get(runtime_id)
        blockers: set[str] = set()

        if profile.adapter.casefold().startswith("future_"):
            blockers.add("CANONICAL_PROFILE_STILL_USES_PLACEHOLDER_ADAPTER")

        if artifact is None:
            blockers.add("CONCRETE_ADAPTER_ARTIFACT_MISSING")
            candidates.append(
                RuntimeAdapterAdmissionCandidate(
                    runtime_id=runtime_id,
                    source_profile_digest=profile.digest(),
                    artifact_digest=None,
                    conformance_run_digests=(),
                    ready_for_signed_adapter_binding_change=False,
                    blockers=tuple(sorted(blockers)),
                )
            )
            continue

        if artifact.subject_repo_sha != repo_sha:
            raise NightShiftContractError(
                "runtime adapter artifact repository SHA mismatch"
            )
        if artifact.adapter_name != profile.adapter:
            raise NightShiftContractError(
                "runtime adapter artifact identity does not match runtime profile"
            )

        bound_runs = tuple(run for run in runs if run.runtime_id == runtime_id)
        for run in bound_runs:
            if run.artifact_digest != artifact.digest():
                raise NightShiftContractError(
                    "runtime adapter conformance artifact digest mismatch"
                )
            if run.subject_repo_sha != repo_sha:
                raise NightShiftContractError(
                    "runtime adapter conformance repository SHA mismatch"
                )

        if len(bound_runs) < policy.min_conformance_runs_per_runtime:
            blockers.add("INSUFFICIENT_CONFORMANCE_RUNS")
        if any(not _run_satisfies_profile(run, profile) for run in bound_runs):
            blockers.add("CONFORMANCE_REQUIREMENTS_FAILED")

        ordered_blockers = tuple(sorted(blockers))
        candidates.append(
            RuntimeAdapterAdmissionCandidate(
                runtime_id=runtime_id,
                source_profile_digest=profile.digest(),
                artifact_digest=artifact.digest(),
                conformance_run_digests=tuple(
                    sorted(run.digest() for run in bound_runs)
                ),
                ready_for_signed_adapter_binding_change=not ordered_blockers,
                blockers=ordered_blockers,
            )
        )

    ordered_candidates = tuple(candidates)
    result_blockers: tuple[str, ...] = ()
    if not all(
        item.ready_for_signed_adapter_binding_change
        for item in ordered_candidates
    ):
        result_blockers = ("RUNTIME_ADAPTER_ADMISSION_INCOMPLETE",)
    status = (
        RuntimeAdapterAdmissionStatus.READY_FOR_SIGNED_ADAPTER_BINDING_CHANGE
        if not result_blockers
        else RuntimeAdapterAdmissionStatus.BLOCKED
    )
    return RuntimeAdapterAdmissionResult(
        status=status,
        policy_digest=policy.digest(),
        subject_repo_sha=repo_sha,
        candidates=ordered_candidates,
        blockers=result_blockers,
    )
