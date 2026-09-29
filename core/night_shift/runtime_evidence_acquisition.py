"""Fail-closed runtime evidence acquisition gate for Night Shift V2-16."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from core.p3.contracts import content_digest

from .contracts import NightShiftContractError
from .runtime_profiles import RuntimeProfile
from .runtime_scale_benchmark import RuntimeBenchmarkSample


class RuntimeEvidenceAcquisitionStatus(StrEnum):
    BLOCKED = "BLOCKED"
    READY_FOR_HUMAN_VALIDATION = "READY_FOR_HUMAN_VALIDATION"


@dataclass(frozen=True, slots=True)
class RuntimeEvidenceAcquisitionPolicy:
    candidate_runtime_ids: tuple[str, ...] = ("dbos", "temporal")
    min_runs_per_runtime: int = 3
    forbidden_evidence_prefixes: tuple[str, ...] = (
        "test:",
        "synthetic:",
        "demo:",
    )
    automatic_profile_validation_enabled: bool = False

    def __post_init__(self) -> None:
        ids = tuple(sorted({item.strip() for item in self.candidate_runtime_ids}))
        if ids != ("dbos", "temporal"):
            raise NightShiftContractError(
                "V2-16 evidence acquisition requires exactly DBOS and Temporal"
            )
        if self.min_runs_per_runtime < 3:
            raise NightShiftContractError(
                "runtime evidence acquisition requires at least three runs per runtime"
            )
        prefixes = tuple(
            sorted({item.strip().casefold() for item in self.forbidden_evidence_prefixes})
        )
        required_prefixes = {"test:", "synthetic:", "demo:"}
        if (
            not prefixes
            or any(not item for item in prefixes)
            or not required_prefixes.issubset(prefixes)
        ):
            raise NightShiftContractError(
                "runtime evidence acquisition cannot weaken forbidden evidence prefixes"
            )
        if self.automatic_profile_validation_enabled:
            raise NightShiftContractError(
                "V2-16 cannot automatically validate runtime profiles"
            )
        object.__setattr__(self, "candidate_runtime_ids", ids)
        object.__setattr__(self, "forbidden_evidence_prefixes", prefixes)

    def digest(self) -> str:
        return content_digest(
            {
                "candidate_runtime_ids": list(self.candidate_runtime_ids),
                "min_runs_per_runtime": self.min_runs_per_runtime,
                "forbidden_evidence_prefixes": list(
                    self.forbidden_evidence_prefixes
                ),
                "automatic_profile_validation_enabled": (
                    self.automatic_profile_validation_enabled
                ),
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeEvidenceRun:
    runtime_id: str
    runtime_profile_digest: str
    benchmark_sample_digest: str
    run_id: str
    executor_id: str
    adapter: str
    adapter_version: str
    environment_digest: str
    artifact_digest: str
    evidence_refs: tuple[str, ...]
    synthetic: bool = False

    def __post_init__(self) -> None:
        required = (
            self.runtime_id,
            self.run_id,
            self.executor_id,
            self.adapter,
            self.adapter_version,
        )
        if any(not item.strip() for item in required):
            raise NightShiftContractError(
                "runtime evidence run requires complete identity"
            )
        digests = (
            self.runtime_profile_digest,
            self.benchmark_sample_digest,
            self.environment_digest,
            self.artifact_digest,
        )
        if any(re.fullmatch(r"[0-9a-f]{64}", item) is None for item in digests):
            raise NightShiftContractError(
                "runtime evidence run requires lowercase SHA-256 digests"
            )
        refs = tuple(sorted({item.strip() for item in self.evidence_refs}))
        if not refs or any(not item for item in refs):
            raise NightShiftContractError(
                "runtime evidence run requires evidence refs"
            )
        object.__setattr__(self, "evidence_refs", refs)

    def digest(self) -> str:
        return content_digest(
            {
                "runtime_id": self.runtime_id,
                "runtime_profile_digest": self.runtime_profile_digest,
                "benchmark_sample_digest": self.benchmark_sample_digest,
                "run_id": self.run_id,
                "executor_id": self.executor_id,
                "adapter": self.adapter,
                "adapter_version": self.adapter_version,
                "environment_digest": self.environment_digest,
                "artifact_digest": self.artifact_digest,
                "evidence_refs": list(self.evidence_refs),
                "synthetic": self.synthetic,
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeEvidenceCandidateResult:
    runtime_id: str
    profile_digest: str
    adapter: str
    accepted_run_digests: tuple[str, ...]
    accepted_sample_digests: tuple[str, ...]
    accepted_artifact_digests: tuple[str, ...]
    evidence_complete: bool
    blockers: tuple[str, ...]

    def digest(self) -> str:
        return content_digest(
            {
                "runtime_id": self.runtime_id,
                "profile_digest": self.profile_digest,
                "adapter": self.adapter,
                "accepted_run_digests": list(self.accepted_run_digests),
                "accepted_sample_digests": list(self.accepted_sample_digests),
                "accepted_artifact_digests": list(
                    self.accepted_artifact_digests
                ),
                "evidence_complete": self.evidence_complete,
                "blockers": list(self.blockers),
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeEvidenceAcquisitionResult:
    status: RuntimeEvidenceAcquisitionStatus
    policy_digest: str
    candidates: tuple[RuntimeEvidenceCandidateResult, ...]
    blockers: tuple[str, ...]
    automatic_profile_validation_executed: bool = False

    def __post_init__(self) -> None:
        if self.automatic_profile_validation_executed:
            raise NightShiftContractError(
                "evidence acquisition cannot validate profiles automatically"
            )

    @property
    def ready_runtime_ids(self) -> tuple[str, ...]:
        return tuple(
            item.runtime_id for item in self.candidates if item.evidence_complete
        )

    def digest(self) -> str:
        return content_digest(
            {
                "status": self.status.value,
                "policy_digest": self.policy_digest,
                "candidates": [item.digest() for item in self.candidates],
                "blockers": list(self.blockers),
                "automatic_profile_validation_executed": (
                    self.automatic_profile_validation_executed
                ),
            }
        )


def _is_concrete_adapter(profile: RuntimeProfile) -> bool:
    return not profile.adapter.casefold().startswith("future_")


def _has_forbidden_refs(
    refs: tuple[str, ...],
    prefixes: tuple[str, ...],
) -> bool:
    return any(
        ref.casefold().startswith(prefix)
        for ref in refs
        for prefix in prefixes
    )
def _candidate_result(
    *,
    profile: RuntimeProfile,
    samples_by_digest: dict[str, RuntimeBenchmarkSample],
    runs: tuple[RuntimeEvidenceRun, ...],
    policy: RuntimeEvidenceAcquisitionPolicy,
) -> RuntimeEvidenceCandidateResult:
    blockers: set[str] = set()
    accepted_runs: list[RuntimeEvidenceRun] = []

    if not _is_concrete_adapter(profile):
        blockers.add("ADAPTER_NOT_CONCRETE")

    for run in runs:
        if run.runtime_profile_digest != profile.digest():
            raise NightShiftContractError(
                "runtime evidence run is bound to stale profile"
            )
        sample = samples_by_digest.get(run.benchmark_sample_digest)
        if sample is None:
            raise NightShiftContractError(
                "runtime evidence run references unknown benchmark sample"
            )
        if sample.runtime_profile_digest != profile.digest():
            raise NightShiftContractError(
                "runtime evidence sample is bound to stale profile"
            )

        run_blocked = False
        if run.adapter != profile.adapter:
            blockers.add("ADAPTER_IDENTITY_MISMATCH")
            run_blocked = True
        if run.adapter_version.casefold() in {
            "unknown",
            "unversioned",
            "none",
        }:
            blockers.add("ADAPTER_VERSION_UNVERIFIED")
            run_blocked = True
        if run.synthetic:
            blockers.add("SYNTHETIC_EVIDENCE_FORBIDDEN")
            run_blocked = True
        if _has_forbidden_refs(
            run.evidence_refs,
            policy.forbidden_evidence_prefixes,
        ) or _has_forbidden_refs(
            sample.evidence_refs,
            policy.forbidden_evidence_prefixes,
        ):
            blockers.add("NON_OPERATIONAL_EVIDENCE_REF")
            run_blocked = True
        if not run_blocked:
            accepted_runs.append(run)

    run_digests = tuple(sorted(run.digest() for run in accepted_runs))
    sample_digests = tuple(
        sorted({run.benchmark_sample_digest for run in accepted_runs})
    )
    artifact_digests = tuple(
        sorted({run.artifact_digest for run in accepted_runs})
    )
    if len(accepted_runs) < policy.min_runs_per_runtime:
        blockers.add("INSUFFICIENT_ACCEPTED_RUNS")
    if len(sample_digests) < policy.min_runs_per_runtime:
        blockers.add("INSUFFICIENT_DISTINCT_SAMPLES")
    if len(artifact_digests) < policy.min_runs_per_runtime:
        blockers.add("INSUFFICIENT_DISTINCT_ARTIFACTS")

    ordered_blockers = tuple(sorted(blockers))
    return RuntimeEvidenceCandidateResult(
        runtime_id=profile.runtime_id,
        profile_digest=profile.digest(),
        adapter=profile.adapter,
        accepted_run_digests=run_digests,
        accepted_sample_digests=sample_digests,
        accepted_artifact_digests=artifact_digests,
        evidence_complete=not ordered_blockers,
        blockers=ordered_blockers,
    )


def evaluate_runtime_evidence_acquisition(
    *,
    profiles: tuple[RuntimeProfile, ...],
    samples: tuple[RuntimeBenchmarkSample, ...],
    runs: tuple[RuntimeEvidenceRun, ...],
    policy: RuntimeEvidenceAcquisitionPolicy,
) -> RuntimeEvidenceAcquisitionResult:
    by_id = {profile.runtime_id: profile for profile in profiles}
    if len(by_id) != len(profiles):
        raise NightShiftContractError(
            "runtime evidence acquisition profiles must be unique"
        )
    missing = [
        item for item in policy.candidate_runtime_ids if item not in by_id
    ]
    if missing:
        raise NightShiftContractError(
            "runtime evidence acquisition missing candidate profile: "
            + ",".join(missing)
        )

    sample_ids = [sample.sample_id for sample in samples]
    if len(set(sample_ids)) != len(sample_ids):
        raise NightShiftContractError(
            "runtime evidence acquisition sample ids must be unique"
        )
    run_ids = [run.run_id for run in runs]
    if len(set(run_ids)) != len(run_ids):
        raise NightShiftContractError(
            "runtime evidence acquisition run ids must be unique"
        )

    candidate_profiles = tuple(
        by_id[item] for item in policy.candidate_runtime_ids
    )
    candidate_digests = {
        profile.digest() for profile in candidate_profiles
    }
    unknown_samples = [
        sample.sample_id
        for sample in samples
        if sample.runtime_profile_digest not in candidate_digests
    ]
    if unknown_samples:
        raise NightShiftContractError(
            "runtime evidence acquisition contains stale benchmark sample"
        )
    unknown_runs = [
        run.run_id
        for run in runs
        if run.runtime_id not in policy.candidate_runtime_ids
    ]
    if unknown_runs:
        raise NightShiftContractError(
            "runtime evidence acquisition contains unknown runtime"
        )

    samples_by_digest = {sample.digest(): sample for sample in samples}
    results = []
    for profile in candidate_profiles:
        bound_runs = tuple(
            sorted(
                (
                    run for run in runs
                    if run.runtime_id == profile.runtime_id
                ),
                key=lambda item: item.run_id,
            )
        )
        results.append(
            _candidate_result(
                profile=profile,
                samples_by_digest=samples_by_digest,
                runs=bound_runs,
                policy=policy,
            )
        )

    candidates = tuple(results)
    blockers: tuple[str, ...] = ()
    if not all(item.evidence_complete for item in candidates):
        blockers = ("RUNTIME_EVIDENCE_INCOMPLETE",)
    status = (
        RuntimeEvidenceAcquisitionStatus.READY_FOR_HUMAN_VALIDATION
        if not blockers
        else RuntimeEvidenceAcquisitionStatus.BLOCKED
    )
    return RuntimeEvidenceAcquisitionResult(
        status=status,
        policy_digest=policy.digest(),
        candidates=candidates,
        blockers=blockers,
    )
