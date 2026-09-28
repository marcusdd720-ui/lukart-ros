"""Shadow-mode planner: predicts actions without mutating external systems."""

from __future__ import annotations

from dataclasses import dataclass

from core.p3.contracts import content_digest

from .executor_registry import ExecutorProfile, executor_registry_digest
from .multi_project import Dispatch, compile_dispatches
from .portfolio import PortfolioSnapshot
from .project_registry import ProjectRegistry
from .scheduler import ResourcePolicy


@dataclass(frozen=True, slots=True)
class ShadowPlan:
    portfolio_digest: str
    project_registry_digest: str
    executor_registry_digest: str
    resource_policy_digest: str
    planned_at_epoch: int
    dispatches: tuple[Dispatch, ...]
    mutating_actions_executed: int = 0

    def digest(self) -> str:
        return content_digest(
            {
                "portfolio_digest": self.portfolio_digest,
                "project_registry_digest": self.project_registry_digest,
                "executor_registry_digest": self.executor_registry_digest,
                "resource_policy_digest": self.resource_policy_digest,
                "planned_at_epoch": self.planned_at_epoch,
                "dispatches": [
                    {
                        "project_id": x.project_id,
                        "task_id": x.task_id,
                        "executor_id": x.executor_id,
                        "repository": x.repository,
                    }
                    for x in self.dispatches
                ],
                "mutating_actions_executed": self.mutating_actions_executed,
            }
        )


def plan_shadow(
    *,
    snapshot: PortfolioSnapshot,
    registry: ProjectRegistry,
    executors: tuple[ExecutorProfile, ...],
    resource_policy: ResourcePolicy,
    now_epoch: int,
) -> ShadowPlan:
    dispatches = compile_dispatches(
        snapshot=snapshot,
        registry=registry,
        executors=executors,
        resource_policy=resource_policy,
        now_epoch=now_epoch,
    )
    resource_policy_digest = content_digest(
        {
            "technical_active_max": resource_policy.technical_active_max,
            "local_code_writers_max": resource_policy.local_code_writers_max,
            "heavy_local_compute_max": resource_policy.heavy_local_compute_max,
        }
    )
    return ShadowPlan(
        portfolio_digest=snapshot.digest(),
        project_registry_digest=registry.digest(),
        executor_registry_digest=executor_registry_digest(executors),
        resource_policy_digest=resource_policy_digest,
        planned_at_epoch=now_epoch,
        dispatches=dispatches,
        mutating_actions_executed=0,
    )
