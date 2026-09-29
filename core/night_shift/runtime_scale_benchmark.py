"""Fail-closed V2-15 DBOS versus Temporal scale benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.p3.contracts import content_digest

from .contracts import NightShiftContractError
from .runtime_profiles import RuntimeEvidence, RuntimeProfile, RuntimeRequirements


class RuntimeScaleBenchmarkStatus(StrEnum):
    BLOCKED = "BLOCKED"
    READY_FOR_HUMAN = "READY_FOR_HUMAN"


@dataclass(frozen=True, slots=True)
class RuntimeBenchmarkPolicy:
    candidate_runtime_ids: tuple[str, ...] = ("dbos", "temporal")
    min_samples_per_runtime: int = 3
    automatic_scale_promotion_enabled: bool = False

    def __post_init__(self) -> None:
        ids = tuple(sorted({item.strip() for item in self.candidate_runtime_ids}))
        if ids != ("dbos", "temporal"):
            raise NightShiftContractError(
                "V2-15 benchmark requires exactly DBOS and Temporal"
            )
        if self.min_samples_per_runtime < 1:
            raise NightShiftContractError(
                "runtime benchmark requires at least one sample per runtime"
            )
        if self.automatic_scale_promotion_enabled:
            raise NightShiftContractError(
                "V2-15 benchmark cannot enable automatic scale promotion"
            )
        object.__setattr__(self, "candidate_runtime_ids", ids)

    def digest(self) -> str:
        return content_digest(
            {
                "candidate_runtime_ids": list(self.candidate_runtime_ids),
                "min_samples_per_runtime": self.min_samples_per_runtime,
                "automatic_scale_promotion_enabled": self.automatic_scale_promotion_enabled,
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeBenchmarkSample:
    runtime_profile_digest: str
    sample_id: str
    crash_resume_pass: bool
    idempotency_pass: bool
    deterministic_replay_pass: bool
    durable_timer_pass: bool
    distributed_workers_pass: bool
    setup_ms: int
    recovery_ms: int
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.runtime_profile_digest) != 64 or not self.sample_id.strip():
            raise NightShiftContractError("invalid runtime benchmark sample identity")
        if self.setup_ms < 0 or self.recovery_ms < 0:
            raise NightShiftContractError("runtime benchmark timings cannot be negative")
        refs = tuple(sorted({item.strip() for item in self.evidence_refs}))
        if not refs or any(not item for item in refs):
            raise NightShiftContractError("runtime benchmark sample requires evidence")
        object.__setattr__(self, "evidence_refs", refs)

    def satisfies(self, requirements: RuntimeRequirements) -> bool:
        checks = (
            (requirements.crash_resume, self.crash_resume_pass),
            (requirements.idempotent_steps, self.idempotency_pass),
            (requirements.deterministic_replay, self.deterministic_replay_pass),
            (requirements.durable_timers, self.durable_timer_pass),
            (requirements.distributed_workers, self.distributed_workers_pass),
        )
        return all((not required) or observed for required, observed in checks)

    def digest(self) -> str:
        return content_digest(
            {
                "runtime_profile_digest": self.runtime_profile_digest,
                "sample_id": self.sample_id,
                "crash_resume_pass": self.crash_resume_pass,
                "idempotency_pass": self.idempotency_pass,
                "deterministic_replay_pass": self.deterministic_replay_pass,
                "durable_timer_pass": self.durable_timer_pass,
                "distributed_workers_pass": self.distributed_workers_pass,
                "setup_ms": self.setup_ms,
                "recovery_ms": self.recovery_ms,
                "evidence_refs": list(self.evidence_refs),
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeBenchmarkCandidateResult:
    runtime_id: str
    profile_digest: str
    adapter: str
    evidence: RuntimeEvidence
    sample_digests: tuple[str, ...]
    max_setup_ms: int | None
    max_recovery_ms: int | None
    eligible_for_scale_selection: bool
    rejection_reasons: tuple[str, ...]

    def digest(self) -> str:
        return content_digest(
            {
                "runtime_id": self.runtime_id,
                "profile_digest": self.profile_digest,
                "adapter": self.adapter,
                "evidence": self.evidence.value,
                "sample_digests": list(self.sample_digests),
                "max_setup_ms": self.max_setup_ms,
                "max_recovery_ms": self.max_recovery_ms,
                "eligible_for_scale_selection": self.eligible_for_scale_selection,
                "rejection_reasons": list(self.rejection_reasons),
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeScaleBenchmarkResult:
    status: RuntimeScaleBenchmarkStatus
    policy_digest: str
    requirements_digest: str
    candidates: tuple[RuntimeBenchmarkCandidateResult, ...]
    blockers: tuple[str, ...]
    automatic_scale_promotion_executed: bool = False

    def __post_init__(self) -> None:
        if self.automatic_scale_promotion_executed:
            raise NightShiftContractError(
                "benchmark result cannot execute automatic scale promotion"
            )

    @property
    def eligible_runtime_ids(self) -> tuple[str, ...]:
        return tuple(
            item.runtime_id
            for item in self.candidates
            if item.eligible_for_scale_selection
        )

    def digest(self) -> str:
        return content_digest(
            {
                "status": self.status.value,
                "policy_digest": self.policy_digest,
                "requirements_digest": self.requirements_digest,
                "candidates": [item.digest() for item in self.candidates],
                "blockers": list(self.blockers),
                "automatic_scale_promotion_executed": self.automatic_scale_promotion_executed,
            }
        )


def _is_concrete_adapter(profile: RuntimeProfile) -> bool:
    return not profile.adapter.casefold().startswith("future_")


def _candidate_result(
    *,
    profile: RuntimeProfile,
    samples: tuple[RuntimeBenchmarkSample, ...],
    policy: RuntimeBenchmarkPolicy,
    requirements: RuntimeRequirements,
) -> RuntimeBenchmarkCandidateResult:
    reasons: list[str] = []
    if profile.evidence is not RuntimeEvidence.VALIDATED:
        reasons.append("EVIDENCE_NOT_VALIDATED")
    if not _is_concrete_adapter(profile):
        reasons.append("ADAPTER_NOT_CONCRETE")
    if len(samples) < policy.min_samples_per_runtime:
        reasons.append("INSUFFICIENT_SAMPLES")
    if not profile.satisfies(requirements):
        reasons.append("PROFILE_REQUIREMENTS_UNMET")
    if (
        len(samples) >= policy.min_samples_per_runtime
        and not all(sample.satisfies(requirements) for sample in samples)
    ):
        reasons.append("OBSERVATION_REQUIREMENTS_UNMET")

    sample_digests = tuple(sorted(sample.digest() for sample in samples))
    eligible = not reasons
    return RuntimeBenchmarkCandidateResult(
        runtime_id=profile.runtime_id,
        profile_digest=profile.digest(),
        adapter=profile.adapter,
        evidence=profile.evidence,
        sample_digests=sample_digests,
        max_setup_ms=max((sample.setup_ms for sample in samples), default=None),
        max_recovery_ms=max((sample.recovery_ms for sample in samples), default=None),
        eligible_for_scale_selection=eligible,
        rejection_reasons=tuple(sorted(reasons)),
    )


def evaluate_runtime_scale_benchmark(
    *,
    profiles: tuple[RuntimeProfile, ...],
    samples: tuple[RuntimeBenchmarkSample, ...],
    policy: RuntimeBenchmarkPolicy,
    requirements: RuntimeRequirements,
) -> RuntimeScaleBenchmarkResult:
    by_id = {profile.runtime_id: profile for profile in profiles}
    if len(by_id) != len(profiles):
        raise NightShiftContractError("runtime benchmark profiles must be unique")

    sample_ids = [sample.sample_id for sample in samples]
    if len(set(sample_ids)) != len(sample_ids):
        raise NightShiftContractError(
            "runtime benchmark sample ids must be unique"
        )

    missing = [item for item in policy.candidate_runtime_ids if item not in by_id]
    if missing:
        raise NightShiftContractError(
            "runtime benchmark missing candidate profile: " + ",".join(missing)
        )

    candidate_profiles = tuple(by_id[item] for item in policy.candidate_runtime_ids)
    candidate_digests = {profile.digest() for profile in candidate_profiles}
    unknown = [
        sample.sample_id
        for sample in samples
        if sample.runtime_profile_digest not in candidate_digests
    ]
    if unknown:
        raise NightShiftContractError(
            "runtime benchmark sample is bound to stale or unknown profile"
        )

    results = []
    for profile in candidate_profiles:
        bound_samples = tuple(
            sorted(
                (
                    sample
                    for sample in samples
                    if sample.runtime_profile_digest == profile.digest()
                ),
                key=lambda item: item.sample_id,
            )
        )
        results.append(
            _candidate_result(
                profile=profile,
                samples=bound_samples,
                policy=policy,
                requirements=requirements,
            )
        )

    candidate_results = tuple(results)
    evidence_complete = all(
        item.evidence is RuntimeEvidence.VALIDATED
        and not item.adapter.casefold().startswith("future_")
        and len(item.sample_digests) >= policy.min_samples_per_runtime
        for item in candidate_results
    )
    eligible = tuple(
        item for item in candidate_results if item.eligible_for_scale_selection
    )
    blockers: list[str] = []
    if not evidence_complete:
        blockers.append("BENCHMARK_EVIDENCE_INCOMPLETE")
    elif not eligible:
        blockers.append("NO_RUNTIME_SATISFIES_SCALE_REQUIREMENTS")

    status = (
        RuntimeScaleBenchmarkStatus.READY_FOR_HUMAN
        if evidence_complete and eligible
        else RuntimeScaleBenchmarkStatus.BLOCKED
    )
    return RuntimeScaleBenchmarkResult(
        status=status,
        policy_digest=policy.digest(),
        requirements_digest=requirements.digest(),
        candidates=candidate_results,
        blockers=tuple(blockers),
    )
