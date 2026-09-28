"""High-level shadow Night Shift cycle."""

from __future__ import annotations

from dataclasses import dataclass

from .executor_registry import ExecutorProfile
from .morning_report import MorningReport, build_shadow_report
from .portfolio import PortfolioSnapshot
from .project_registry import ProjectRegistry
from .scheduler import ResourcePolicy
from .shadow_runner import ShadowPlan, plan_shadow


@dataclass(frozen=True, slots=True)
class NightCycleResult:
    plan: ShadowPlan
    report: MorningReport


def run_shadow_cycle(
    *,
    snapshot: PortfolioSnapshot,
    registry: ProjectRegistry,
    executors: tuple[ExecutorProfile, ...],
    resource_policy: ResourcePolicy,
    now_epoch: int,
) -> NightCycleResult:
    plan = plan_shadow(
        snapshot=snapshot,
        registry=registry,
        executors=executors,
        resource_policy=resource_policy,
        now_epoch=now_epoch,
    )
    blocked = tuple(sorted(x.task_id for x in snapshot.projects if not x.ready))
    report = build_shadow_report(
        plan=plan,
        blocked=blocked,
        evidence_refs=(f"portfolio:{snapshot.digest()}", f"plan:{plan.digest()}"),
    )
    return NightCycleResult(plan, report)
