"""Bounded V2-14 controlled Night Shift pilot."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.p3.contracts import content_digest

from .canary import ControlledCanaryResult, run_controlled_canary
from .contracts import (
    AutonomyEnvelope,
    LiveStateSnapshot,
    NightShiftContractError,
    PolicyRef,
    RiskClass,
    TaskCapsule,
)
from .crypto_identity import CanaryCryptographicContext
from .executor_registry import ExecutorProfile
from .failure_gate import FailureInjectionReport
from .morning_report import MorningReport
from .portfolio import PortfolioSnapshot, ProjectState
from .project_registry import ProjectRegistry
from .promotion import VerificationQuorum
from .scheduler import ResourcePolicy
from .shadow import ShadowPromotionClearance
from .shadow_runner import ShadowPlan, plan_shadow


@dataclass(frozen=True, slots=True)
class ControlledNightPilotPolicy:
    max_dispatches: int = 1
    allowed_risk_classes: tuple[RiskClass, ...] = (RiskClass.R0, RiskClass.R1)
    external_publication_enabled: bool = False

    def __post_init__(self) -> None:
        if self.max_dispatches != 1:
            raise NightShiftContractError(
                "controlled night pilot requires exactly one dispatch"
            )
        if not self.allowed_risk_classes:
            raise NightShiftContractError(
                "controlled night pilot requires allowed risk classes"
            )
        if any(item not in {RiskClass.R0, RiskClass.R1} for item in self.allowed_risk_classes):
            raise NightShiftContractError(
                "controlled night pilot is limited to R0/R1"
            )
        if self.external_publication_enabled:
            raise NightShiftContractError(
                "controlled night pilot cannot enable external publication"
            )

    def digest(self) -> str:
        return content_digest(
            {
                "max_dispatches": self.max_dispatches,
                "allowed_risk_classes": sorted(
                    item.value for item in self.allowed_risk_classes
                ),
                "external_publication_enabled": self.external_publication_enabled,
            }
        )


@dataclass(frozen=True, slots=True)
class ControlledNightPilotContext:
    repository: str | Path
    worktree_root: str | Path
    task: TaskCapsule
    state: LiveStateSnapshot
    policy: PolicyRef
    envelope: AutonomyEnvelope
    quorum: VerificationQuorum
    cryptographic_context: CanaryCryptographicContext
    shadow_clearance: ShadowPromotionClearance
    expected_shadow_ledger_digest: str
    failure_report: FailureInjectionReport
    expected_failure_report_digest: str
    expected_failure_suite_profile_digest: str
    required_failure_scenarios: tuple[str, ...]
    target_path: str
    replacement_text: str


@dataclass(frozen=True, slots=True)
class ControlledNightPilotResult:
    plan: ShadowPlan
    canary: ControlledCanaryResult
    report: MorningReport
    project_id: str
    task_id: str
    pilot_policy_digest: str

    def digest(self) -> str:
        return content_digest(
            {
                "plan_digest": self.plan.digest(),
                "project_id": self.project_id,
                "task_id": self.task_id,
                "pilot_policy_digest": self.pilot_policy_digest,
                "input_sha": self.canary.input_sha,
                "output_sha": self.canary.output_sha,
                "receipt_digest": self.canary.receipt_digest,
                "rollback_verified": self.canary.rollback_verified,
                "published": self.canary.published,
                "closed": list(self.report.closed),
                "blocked": list(self.report.blocked),
                "evidence_refs": list(self.report.evidence_refs),
            }
        )


def _selected_project(
    *,
    snapshot: PortfolioSnapshot,
    project_id: str,
    task_id: str,
) -> ProjectState:
    matches = [
        item
        for item in snapshot.projects
        if item.project_id == project_id and item.task_id == task_id
    ]
    if len(matches) != 1:
        raise NightShiftContractError(
            "controlled night pilot dispatch is not uniquely represented in live state"
        )
    return matches[0]


def run_controlled_night_pilot(
    *,
    snapshot: PortfolioSnapshot,
    registry: ProjectRegistry,
    executors: tuple[ExecutorProfile, ...],
    resource_policy: ResourcePolicy,
    pilot_policy: ControlledNightPilotPolicy,
    context: ControlledNightPilotContext,
    now_epoch: int,
) -> ControlledNightPilotResult:
    snapshot.require_fresh(now_epoch=now_epoch)
    plan = plan_shadow(
        snapshot=snapshot,
        registry=registry,
        executors=executors,
        resource_policy=resource_policy,
        now_epoch=now_epoch,
    )
    if len(plan.dispatches) != pilot_policy.max_dispatches:
        raise NightShiftContractError(
            "controlled night pilot requires exactly one planned dispatch"
        )

    dispatch = plan.dispatches[0]
    project = _selected_project(
        snapshot=snapshot,
        project_id=dispatch.project_id,
        task_id=dispatch.task_id,
    )
    config = registry.by_project_id(project.project_id)

    if not config.mutating:
        raise NightShiftContractError(
            "controlled night pilot requires a mutating project"
        )
    if project.risk_class not in pilot_policy.allowed_risk_classes:
        raise NightShiftContractError(
            "controlled night pilot risk class is outside the pilot envelope"
        )
    if project.repository != dispatch.repository:
        raise NightShiftContractError(
            "controlled night pilot repository mismatch"
        )
    if context.envelope.max_tasks != 1:
        raise NightShiftContractError(
            "controlled night pilot requires a single-task autonomy envelope"
        )
    if tuple(context.envelope.repositories) != (dispatch.repository,):
        raise NightShiftContractError(
            "controlled night pilot requires a single-repository autonomy envelope"
        )
    if tuple(context.envelope.allowed_risk_classes) != (project.risk_class,):
        raise NightShiftContractError(
            "controlled night pilot autonomy envelope risk must match the task"
        )
    if context.task.task_id != dispatch.task_id:
        raise NightShiftContractError(
            "controlled night pilot task capsule does not match dispatch"
        )
    if context.task.repository != dispatch.repository:
        raise NightShiftContractError(
            "controlled night pilot task repository does not match dispatch"
        )
    if context.state.repository != dispatch.repository:
        raise NightShiftContractError(
            "controlled night pilot live state repository does not match dispatch"
        )
    if context.state.head_sha != project.main_sha:
        raise NightShiftContractError(
            "controlled night pilot state is not bound to current project main"
        )
    if context.state.base_sha != context.state.head_sha:
        raise NightShiftContractError(
            "controlled night pilot requires a single-SHA execution baseline"
        )
    if context.task.state_snapshot_digest != context.state.digest():
        raise NightShiftContractError(
            "controlled night pilot task is not bound to current live state"
        )
    if context.task.risk_class != project.risk_class:
        raise NightShiftContractError(
            "controlled night pilot task risk differs from live portfolio"
        )

    canary = run_controlled_canary(
        repository=context.repository,
        worktree_root=context.worktree_root,
        task=context.task,
        state=context.state,
        policy=context.policy,
        envelope=context.envelope,
        quorum=context.quorum,
        cryptographic_context=context.cryptographic_context,
        shadow_clearance=context.shadow_clearance,
        expected_shadow_ledger_digest=context.expected_shadow_ledger_digest,
        failure_report=context.failure_report,
        expected_failure_report_digest=context.expected_failure_report_digest,
        expected_failure_suite_profile_digest=context.expected_failure_suite_profile_digest,
        required_failure_scenarios=context.required_failure_scenarios,
        target_path=context.target_path,
        replacement_text=context.replacement_text,
        now_epoch=now_epoch,
    )

    if canary.input_sha != project.main_sha:
        raise NightShiftContractError(
            "controlled night pilot canary executed against a different input SHA"
        )
    if not canary.rollback_verified:
        raise NightShiftContractError(
            "controlled night pilot requires verified rollback"
        )
    if canary.published:
        raise NightShiftContractError(
            "controlled night pilot must not publish externally"
        )

    evidence_refs = tuple(
        sorted(
            {
                f"portfolio:{snapshot.digest()}",
                f"plan:{plan.digest()}",
                f"pilot-policy:{pilot_policy.digest()}",
                f"receipt:{canary.receipt_digest}",
            }
        )
    )
    report = MorningReport(
        closed=(),
        ready_for_human=tuple(
            sorted(
                item.task_id
                for item in snapshot.projects
                if item.ready
            )
        ),
        blocked=tuple(
            sorted(item.task_id for item in snapshot.projects if not item.ready)
        ),
        planned=(),
        evidence_refs=evidence_refs,
    )
    return ControlledNightPilotResult(
        plan=plan,
        canary=canary,
        report=report,
        project_id=dispatch.project_id,
        task_id=dispatch.task_id,
        pilot_policy_digest=pilot_policy.digest(),
    )
