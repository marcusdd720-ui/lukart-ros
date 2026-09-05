"""Typed KPL-1.0 Action Plan downstream of a selected Strategy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from knowledge.models.strategy_model import StrategyModel, StrategyStatus


class TaskStatus(StrEnum):
    PENDING = "pending"
    BLOCKED = "blocked"
    READY = "ready"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PlanStatus(StrEnum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class DeadlineBinding:
    deadline: str
    rule_ref: str
    source_ref: str

    def __post_init__(self) -> None:
        if not self.deadline.strip() or not self.rule_ref.strip() or not self.source_ref.strip():
            raise ValueError("DeadlineBinding requires deadline, rule_ref and source_ref")


@dataclass(frozen=True, slots=True)
class PlanTask:
    task_id: str
    purpose: str
    owner: str
    required_inputs: tuple[str, ...] = ()
    preconditions: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    expected_output: str | None = None
    completion_criteria: tuple[str, ...] = ()
    failure_mode: str | None = None
    approval_rule: str | None = None
    approval_evidence: tuple[str, ...] = ()
    deadline: DeadlineBinding | None = None
    completion_evidence: tuple[str, ...] = ()
    fallback_trigger: str | None = None
    status: TaskStatus = TaskStatus.PENDING

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.purpose.strip() or not self.owner.strip():
            raise ValueError("PlanTask identity, purpose and owner cannot be empty")
        collections = (
            self.required_inputs,
            self.preconditions,
            self.dependencies,
            self.completion_criteria,
            self.approval_evidence,
            self.completion_evidence,
        )
        if any(not value.strip() for values in collections for value in values):
            raise ValueError("PlanTask collections cannot contain empty values")
        if self.task_id in self.dependencies:
            raise ValueError("PlanTask cannot depend on itself")
        if self.approval_rule is not None and not self.approval_rule.strip():
            raise ValueError("approval_rule cannot be blank")
        if self.approval_rule and self.status in {TaskStatus.READY, TaskStatus.COMPLETED}:
            if not self.approval_evidence:
                raise ValueError("approved task state requires approval evidence")
        if self.status is TaskStatus.COMPLETED:
            if not self.completion_criteria:
                raise ValueError("COMPLETED task requires completion criteria")
            if not self.completion_evidence:
                raise ValueError("COMPLETED task requires completion evidence")


@dataclass(frozen=True, slots=True)
class ActionPlan:
    plan_id: str
    strategy_id: str
    strategy_version: int
    tasks: tuple[PlanTask, ...]
    monitoring_hooks: tuple[str, ...] = ()
    status: PlanStatus = PlanStatus.PROPOSED
    version: int = 1
    lineage: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.plan_id.strip() or not self.strategy_id.strip():
            raise ValueError("ActionPlan identity fields cannot be empty")
        if self.strategy_version < 1 or self.version < 1:
            raise ValueError("ActionPlan versions must be >= 1")
        if any(not value.strip() for value in (*self.monitoring_hooks, *self.lineage)):
            raise ValueError("ActionPlan text collections cannot contain empty values")
        task_ids = [task.task_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("ActionPlan task IDs must be unique")
        known = set(task_ids)
        for task in self.tasks:
            unknown = set(task.dependencies) - known
            if unknown:
                raise ValueError("ActionPlan contains unresolved task dependencies")
        self._reject_cycles()
        if self.status is PlanStatus.COMPLETED:
            incomplete = any(
                task.status is not TaskStatus.COMPLETED for task in self.tasks
            )
            if not self.tasks or incomplete:
                raise ValueError("COMPLETED plan requires all tasks to be completed")

    def _reject_cycles(self) -> None:
        graph = {task.task_id: set(task.dependencies) for task in self.tasks}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise ValueError("ActionPlan task dependencies must be acyclic")
            if task_id in visited:
                return
            visiting.add(task_id)
            for dependency in graph[task_id]:
                visit(dependency)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in graph:
            visit(task_id)

    @classmethod
    def build(
        cls,
        plan_id: str,
        strategy: StrategyModel,
        *,
        tasks: tuple[PlanTask, ...] = (),
        monitoring_hooks: tuple[str, ...] = (),
        status: PlanStatus = PlanStatus.PROPOSED,
        version: int = 1,
        lineage: tuple[str, ...] = (),
    ) -> ActionPlan:
        if strategy.status is not StrategyStatus.SELECTED:
            raise ValueError("ActionPlan requires a SELECTED Strategy")
        return cls(
            plan_id=plan_id,
            strategy_id=strategy.strategy_id,
            strategy_version=strategy.version,
            tasks=tasks,
            monitoring_hooks=monitoring_hooks,
            status=status,
            version=version,
            lineage=lineage,
        )
