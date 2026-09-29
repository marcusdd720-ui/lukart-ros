"""Fail-closed shadow activation evidence gate for Night Shift V2-22."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.p3.contracts import content_digest, require_hex_digest

from .contracts import NightShiftContractError
from .runtime_shadow_activation_plan import (
    RuntimeShadowActivationPlanResult,
    RuntimeShadowActivationPlanStatus,
)


class RuntimeShadowEvidenceStatus(StrEnum):
    BLOCKED = "BLOCKED"
    READY_FOR_PROMOTION_REVIEW = "READY_FOR_PROMOTION_REVIEW"


def _digest(value: str, *, field_name: str) -> str:
    try:
        return require_hex_digest(value, field_name=field_name)
    except ValueError as exc:
        raise NightShiftContractError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class RuntimeShadowActivationRun:
    runtime_id: str
    plan_candidate_digest: str
    run_id: str
    side_effect_free: bool
    rollback_verified: bool
    deterministic_replay_pass: bool
    task_budget_respected: bool
    evidence_digest: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        runtime_id = self.runtime_id.strip()
        run_id = self.run_id.strip()
        if not runtime_id or not run_id:
            raise NightShiftContractError("shadow activation run identity is required")
        object.__setattr__(
            self,
            "plan_candidate_digest",
            _digest(self.plan_candidate_digest, field_name="plan_candidate_digest"),
        )
        object.__setattr__(
            self,
            "evidence_digest",
            _digest(self.evidence_digest, field_name="evidence_digest"),
        )
        flags = (
            self.side_effect_free,
            self.rollback_verified,
            self.deterministic_replay_pass,
            self.task_budget_respected,
        )
        if any(type(value) is not bool for value in flags):
            raise NightShiftContractError(
                "shadow activation evidence flags must be booleans"
            )
        refs = tuple(sorted({item.strip() for item in self.evidence_refs}))
        if not refs or any(not item for item in refs):
            raise NightShiftContractError("shadow activation run requires evidence refs")
        forbidden = ("test:", "synthetic:", "demo:")
        if any(ref.casefold().startswith(forbidden) for ref in refs):
            raise NightShiftContractError(
                "shadow activation rejects test/synthetic/demo evidence"
            )
        object.__setattr__(self, "runtime_id", runtime_id)
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "evidence_refs", refs)

    def passed(self) -> bool:
        return (
            self.side_effect_free
            and self.rollback_verified
            and self.deterministic_replay_pass
            and self.task_budget_respected
        )

    def digest(self) -> str:
        return content_digest(
            {
                "runtime_id": self.runtime_id,
                "plan_candidate_digest": self.plan_candidate_digest,
                "run_id": self.run_id,
                "side_effect_free": self.side_effect_free,
                "rollback_verified": self.rollback_verified,
                "deterministic_replay_pass": self.deterministic_replay_pass,
                "task_budget_respected": self.task_budget_respected,
                "evidence_digest": self.evidence_digest,
                "evidence_refs": list(self.evidence_refs),
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeShadowEvidencePolicy:
    candidate_runtime_ids: tuple[str, ...] = ("dbos", "temporal")
    min_runs_per_runtime: int = 3
    production_mutation_enabled: bool = False
    external_publication_enabled: bool = False
    automatic_promotion_enabled: bool = False

    def __post_init__(self) -> None:
        ids = tuple(sorted({item.strip() for item in self.candidate_runtime_ids}))
        if ids != ("dbos", "temporal"):
            raise NightShiftContractError(
                "V2-22 shadow evidence requires exactly DBOS and Temporal"
            )
        if self.min_runs_per_runtime < 3:
            raise NightShiftContractError(
                "V2-22 requires at least three shadow runs per runtime"
            )
        if (
            self.production_mutation_enabled
            or self.external_publication_enabled
            or self.automatic_promotion_enabled
        ):
            raise NightShiftContractError(
                "V2-22 cannot mutate production, publish, or auto-promote"
            )
        object.__setattr__(self, "candidate_runtime_ids", ids)

    def digest(self) -> str:
        return content_digest(
            {
                "candidate_runtime_ids": list(self.candidate_runtime_ids),
                "min_runs_per_runtime": self.min_runs_per_runtime,
                "production_mutation_enabled": self.production_mutation_enabled,
                "external_publication_enabled": self.external_publication_enabled,
                "automatic_promotion_enabled": self.automatic_promotion_enabled,
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeShadowEvidenceCandidate:
    runtime_id: str
    plan_candidate_digest: str
    run_digests: tuple[str, ...]
    ready_for_promotion_review: bool
    blockers: tuple[str, ...]

    def digest(self) -> str:
        return content_digest(
            {
                "runtime_id": self.runtime_id,
                "plan_candidate_digest": self.plan_candidate_digest,
                "run_digests": list(self.run_digests),
                "ready_for_promotion_review": self.ready_for_promotion_review,
                "blockers": list(self.blockers),
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeShadowEvidenceResult:
    status: RuntimeShadowEvidenceStatus
    policy_digest: str
    plan_digest: str
    candidates: tuple[RuntimeShadowEvidenceCandidate, ...]
    blockers: tuple[str, ...]
    production_promotion_executed: bool = False

    def __post_init__(self) -> None:
        if (
            self.status is RuntimeShadowEvidenceStatus.READY_FOR_PROMOTION_REVIEW
            and self.blockers
        ):
            raise NightShiftContractError(
                "ready shadow evidence cannot carry blockers"
            )
        if self.production_promotion_executed:
            raise NightShiftContractError(
                "shadow evidence gate cannot promote a runtime"
            )

    def digest(self) -> str:
        return content_digest(
            {
                "status": self.status.value,
                "policy_digest": self.policy_digest,
                "plan_digest": self.plan_digest,
                "candidates": [item.digest() for item in self.candidates],
                "blockers": list(self.blockers),
                "production_promotion_executed": self.production_promotion_executed,
            }
        )


def evaluate_runtime_shadow_evidence(
    *,
    plan: RuntimeShadowActivationPlanResult,
    runs: tuple[RuntimeShadowActivationRun, ...],
    policy: RuntimeShadowEvidencePolicy,
) -> RuntimeShadowEvidenceResult:
    if (
        plan.status
        is not RuntimeShadowActivationPlanStatus.READY_FOR_CONTROLLED_SHADOW_EXECUTION
    ):
        return RuntimeShadowEvidenceResult(
            status=RuntimeShadowEvidenceStatus.BLOCKED,
            policy_digest=policy.digest(),
            plan_digest=plan.digest(),
            candidates=(),
            blockers=("SHADOW_ACTIVATION_PLAN_NOT_READY",),
        )

    plan_by_runtime = {item.runtime_id: item for item in plan.candidates}
    if len(plan_by_runtime) != len(plan.candidates):
        raise NightShiftContractError("shadow plan candidates must be unique")
    if tuple(sorted(plan_by_runtime)) != policy.candidate_runtime_ids:
        raise NightShiftContractError(
            "shadow evidence requires exactly planned candidate runtimes"
        )

    run_ids = [item.run_id for item in runs]
    evidence_digests = [item.evidence_digest for item in runs]
    if len(set(run_ids)) != len(run_ids):
        raise NightShiftContractError("shadow run ids must be globally unique")
    if len(set(evidence_digests)) != len(evidence_digests):
        raise NightShiftContractError(
            "shadow evidence digests must be globally unique"
        )

    unknown = set(item.runtime_id for item in runs) - set(policy.candidate_runtime_ids)
    if unknown:
        raise NightShiftContractError("shadow evidence references unknown runtime")

    candidates: list[RuntimeShadowEvidenceCandidate] = []
    for runtime_id in policy.candidate_runtime_ids:
        planned = plan_by_runtime[runtime_id]
        bound = tuple(item for item in runs if item.runtime_id == runtime_id)
        blockers: set[str] = set()
        for item in bound:
            if item.plan_candidate_digest != planned.digest():
                raise NightShiftContractError(
                    "shadow run plan candidate digest mismatch"
                )
        if len(bound) < policy.min_runs_per_runtime:
            blockers.add("INSUFFICIENT_SHADOW_RUNS")
        if any(not item.passed() for item in bound):
            blockers.add("SHADOW_EXECUTION_REQUIREMENTS_FAILED")
        ordered_blockers = tuple(sorted(blockers))
        candidates.append(
            RuntimeShadowEvidenceCandidate(
                runtime_id=runtime_id,
                plan_candidate_digest=planned.digest(),
                run_digests=tuple(sorted(item.digest() for item in bound)),
                ready_for_promotion_review=not ordered_blockers,
                blockers=ordered_blockers,
            )
        )

    ordered = tuple(candidates)
    result_blockers: tuple[str, ...] = ()
    if not all(item.ready_for_promotion_review for item in ordered):
        result_blockers = ("SHADOW_EVIDENCE_INCOMPLETE",)
    return RuntimeShadowEvidenceResult(
        status=(
            RuntimeShadowEvidenceStatus.READY_FOR_PROMOTION_REVIEW
            if not result_blockers
            else RuntimeShadowEvidenceStatus.BLOCKED
        ),
        policy_digest=policy.digest(),
        plan_digest=plan.digest(),
        candidates=ordered,
        blockers=result_blockers,
    )
