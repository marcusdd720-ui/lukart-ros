"""Bounded shadow activation planning for Night Shift V2-21."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.p3.contracts import content_digest

from .contracts import NightShiftContractError
from .runtime_binding_proposal import RuntimeBindingProposalResult
from .runtime_binding_verification import (
    RuntimeBindingVerificationResult,
    RuntimeBindingVerificationStatus,
)


class RuntimeShadowActivationPlanStatus(StrEnum):
    BLOCKED = "BLOCKED"
    READY_FOR_CONTROLLED_SHADOW_EXECUTION = "READY_FOR_CONTROLLED_SHADOW_EXECUTION"


@dataclass(frozen=True, slots=True)
class RuntimeShadowActivationPolicy:
    candidate_runtime_ids: tuple[str, ...] = ("dbos", "temporal")
    max_tasks_per_runtime: int = 1
    shadow_only: bool = True
    rollback_required: bool = True
    external_publication_enabled: bool = False
    production_mutation_enabled: bool = False
    automatic_promotion_enabled: bool = False

    def __post_init__(self) -> None:
        ids = tuple(sorted({item.strip() for item in self.candidate_runtime_ids}))
        if ids != ("dbos", "temporal"):
            raise NightShiftContractError(
                "V2-21 shadow activation requires exactly DBOS and Temporal"
            )
        if self.max_tasks_per_runtime != 1:
            raise NightShiftContractError(
                "V2-21 shadow activation is limited to one task per runtime"
            )
        if not self.shadow_only or not self.rollback_required:
            raise NightShiftContractError(
                "V2-21 requires shadow-only execution with rollback"
            )
        if (
            self.external_publication_enabled
            or self.production_mutation_enabled
            or self.automatic_promotion_enabled
        ):
            raise NightShiftContractError(
                "V2-21 cannot publish, mutate production, or auto-promote"
            )
        object.__setattr__(self, "candidate_runtime_ids", ids)

    def digest(self) -> str:
        return content_digest(
            {
                "candidate_runtime_ids": list(self.candidate_runtime_ids),
                "max_tasks_per_runtime": self.max_tasks_per_runtime,
                "shadow_only": self.shadow_only,
                "rollback_required": self.rollback_required,
                "external_publication_enabled": self.external_publication_enabled,
                "production_mutation_enabled": self.production_mutation_enabled,
                "automatic_promotion_enabled": self.automatic_promotion_enabled,
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeShadowActivationCandidate:
    runtime_id: str
    binding_candidate_digest: str
    task_budget: int
    shadow_only: bool
    rollback_required: bool

    def digest(self) -> str:
        return content_digest(
            {
                "runtime_id": self.runtime_id,
                "binding_candidate_digest": self.binding_candidate_digest,
                "task_budget": self.task_budget,
                "shadow_only": self.shadow_only,
                "rollback_required": self.rollback_required,
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeShadowActivationPlanResult:
    status: RuntimeShadowActivationPlanStatus
    policy_digest: str
    verification_digest: str
    proposal_digest: str
    candidates: tuple[RuntimeShadowActivationCandidate, ...]
    blockers: tuple[str, ...]
    execution_started: bool = False
    production_mutation_executed: bool = False
    external_publication_executed: bool = False

    def __post_init__(self) -> None:
        if (
            self.status
            is RuntimeShadowActivationPlanStatus.READY_FOR_CONTROLLED_SHADOW_EXECUTION
            and self.blockers
        ):
            raise NightShiftContractError(
                "ready shadow activation plan cannot carry blockers"
            )
        if (
            self.execution_started
            or self.production_mutation_executed
            or self.external_publication_executed
        ):
            raise NightShiftContractError(
                "shadow activation plan cannot execute runtime work"
            )

    def digest(self) -> str:
        return content_digest(
            {
                "status": self.status.value,
                "policy_digest": self.policy_digest,
                "verification_digest": self.verification_digest,
                "proposal_digest": self.proposal_digest,
                "candidates": [item.digest() for item in self.candidates],
                "blockers": list(self.blockers),
                "execution_started": self.execution_started,
                "production_mutation_executed": self.production_mutation_executed,
                "external_publication_executed": self.external_publication_executed,
            }
        )


def build_runtime_shadow_activation_plan(
    *,
    proposal: RuntimeBindingProposalResult,
    verification: RuntimeBindingVerificationResult,
    policy: RuntimeShadowActivationPolicy,
) -> RuntimeShadowActivationPlanResult:
    blockers: set[str] = set()
    if (
        verification.status
        is not RuntimeBindingVerificationStatus.READY_FOR_SHADOW_ACTIVATION_PLAN
    ):
        blockers.add("BINDING_VERIFICATION_NOT_READY")
    if verification.blockers:
        blockers.add("BINDING_VERIFICATION_BLOCKED")
    if verification.proposal_digest != proposal.digest():
        raise NightShiftContractError(
            "shadow activation verification does not bind exact proposal"
        )

    by_candidate = {item.runtime_id: item for item in proposal.candidates}
    if len(by_candidate) != len(proposal.candidates):
        raise NightShiftContractError(
            "shadow activation proposal candidates must be unique"
        )
    if tuple(sorted(by_candidate)) != policy.candidate_runtime_ids:
        blockers.add("BINDING_PROPOSAL_CANDIDATES_INCOMPLETE")

    candidates = tuple(
        RuntimeShadowActivationCandidate(
            runtime_id=runtime_id,
            binding_candidate_digest=by_candidate[runtime_id].digest(),
            task_budget=policy.max_tasks_per_runtime,
            shadow_only=True,
            rollback_required=True,
        )
        for runtime_id in policy.candidate_runtime_ids
        if runtime_id in by_candidate
    )
    if len(candidates) != len(policy.candidate_runtime_ids):
        blockers.add("SHADOW_ACTIVATION_PLAN_INCOMPLETE")

    ordered_blockers = tuple(sorted(blockers))
    return RuntimeShadowActivationPlanResult(
        status=(
            RuntimeShadowActivationPlanStatus.READY_FOR_CONTROLLED_SHADOW_EXECUTION
            if not ordered_blockers
            else RuntimeShadowActivationPlanStatus.BLOCKED
        ),
        policy_digest=policy.digest(),
        verification_digest=verification.digest(),
        proposal_digest=proposal.digest(),
        candidates=candidates,
        blockers=ordered_blockers,
    )
