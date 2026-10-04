"""Continuous work dispatch semantics for UAOS / Night Shift.

Pure deterministic policy layer. Process launchers and provider adapters consume these
decisions; this module does not claim that a process is executing without evidence.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import StrEnum

from .contracts import NightShiftContractError


class ExecutionState(StrEnum):
    EXECUTING = "EXECUTING"
    WAITING_EXTERNAL = "WAITING_EXTERNAL"
    WAITING_RETRY = "WAITING_RETRY"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"
    BLOCKED_TECHNICAL = "BLOCKED_TECHNICAL"
    QUARANTINED = "QUARANTINED"
    IDLE_NO_WORK = "IDLE_NO_WORK"
    STOPPED = "STOPPED"


class ProviderState(StrEnum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    FAILED = "FAILED"
    COOLDOWN = "COOLDOWN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class DispatchTask:
    task_id: str
    priority: int
    status: str = "READY"
    attempts: int = 0
    max_attempts: int = 3
    next_run_epoch: int = 0
    depends_on: tuple[str, ...] = ()
    human_gate: bool = False
    external_gate: bool = False
    privacy_class: str = "SYNTHETIC"
    worktree: str | None = None
    write_task: bool = False

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise NightShiftContractError("task_id is required")
        if self.priority < 0:
            raise NightShiftContractError("priority cannot be negative")
        if self.max_attempts < 1:
            raise NightShiftContractError("max_attempts must be positive")
        if self.attempts < 0:
            raise NightShiftContractError("attempts cannot be negative")


@dataclass(frozen=True, slots=True)
class WorkerEvidence:
    worker_id: str
    process_alive: bool
    child_agent_alive: bool
    task_id: str | None
    last_heartbeat_epoch: int
    last_progress_epoch: int
    waiting_for_input: bool = False


@dataclass(frozen=True, slots=True)
class ProviderCandidate:
    provider_id: str
    state: ProviderState
    capabilities: frozenset[str]
    privacy_eligible: bool
    zero_cost_verified: bool
    score: int = 0


@dataclass(frozen=True, slots=True)
class LivenessDecision:
    state: ExecutionState
    incident: str | None = None
    recover: bool = False


_TRANSIENT_PREFIXES = (
    ".aider.tags.cache.v4/",
    ".pytest_cache/",
    ".ruff_cache/",
    "__pycache__/",
)


def is_transient_tool_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return any(
        normalized == prefix.rstrip("/") or normalized.startswith(prefix)
        for prefix in _TRANSIENT_PREFIXES
    )


def validate_attempt_budget(task: DispatchTask) -> DispatchTask:
    if task.attempts > task.max_attempts:
        return replace(task, attempts=task.max_attempts, status="BLOCKED_TECHNICAL")
    if task.status == "DONE" and task.attempts > task.max_attempts:
        raise AssertionError("unreachable after normalization")
    return task


def normalize_legacy_result(task: DispatchTask, *, last_detail: str | None) -> DispatchTask:
    normalized = validate_attempt_budget(task)
    detail = (last_detail or "").strip().lower()
    if "agent success" in detail and normalized.status in {"BLOCKED", "BLOCKED_TECHNICAL"}:
        normalized = replace(normalized, status="DONE")
    return normalized


def dependencies_done(task: DispatchTask, tasks: Iterable[DispatchTask]) -> bool:
    states = {item.task_id: item.status for item in tasks}
    return all(states.get(dep) == "DONE" for dep in task.depends_on)


def executable_tasks(
    tasks: tuple[DispatchTask, ...], *, now_epoch: int
) -> tuple[DispatchTask, ...]:
    normalized = tuple(validate_attempt_budget(item) for item in tasks)
    ready = [
        item
        for item in normalized
        if item.status in {"READY", "RETRY"}
        and item.attempts < item.max_attempts
        and item.next_run_epoch <= now_epoch
        and not item.human_gate
        and not item.external_gate
        and dependencies_done(item, normalized)
    ]
    return tuple(sorted(ready, key=lambda item: (item.priority, item.task_id)))


def select_next_task(
    tasks: tuple[DispatchTask, ...],
    *,
    now_epoch: int,
    active_write_worktrees: frozenset[str] = frozenset(),
) -> DispatchTask | None:
    for task in executable_tasks(tasks, now_epoch=now_epoch):
        if task.write_task and task.worktree and task.worktree in active_write_worktrees:
            continue
        return task
    return None


def authoritative_execution_state(
    *,
    ready_work_exists: bool,
    worker: WorkerEvidence | None,
    now_epoch: int,
    heartbeat_stale_seconds: int = 180,
    progress_stale_seconds: int = 300,
) -> LivenessDecision:
    if worker is None:
        if ready_work_exists:
            return LivenessDecision(ExecutionState.BLOCKED_TECHNICAL, "NO_EXECUTOR", True)
        return LivenessDecision(ExecutionState.IDLE_NO_WORK)

    heartbeat_stale = now_epoch - worker.last_heartbeat_epoch > heartbeat_stale_seconds
    progress_stale = now_epoch - worker.last_progress_epoch > progress_stale_seconds

    if ready_work_exists and not worker.process_alive:
        return LivenessDecision(ExecutionState.BLOCKED_TECHNICAL, "DEAD_PROCESS", True)
    if ready_work_exists and heartbeat_stale:
        return LivenessDecision(ExecutionState.BLOCKED_TECHNICAL, "STALE_HEARTBEAT", True)
    if ready_work_exists and worker.waiting_for_input:
        return LivenessDecision(ExecutionState.BLOCKED_TECHNICAL, "SHELL_WAITING_INPUT", True)
    if ready_work_exists and worker.task_id and not worker.child_agent_alive:
        return LivenessDecision(ExecutionState.BLOCKED_TECHNICAL, "RUNNING_WITHOUT_CHILD", True)
    if ready_work_exists and worker.task_id and progress_stale:
        return LivenessDecision(ExecutionState.BLOCKED_TECHNICAL, "RUNNING_WITHOUT_PROGRESS", True)
    if ready_work_exists and worker.task_id and worker.child_agent_alive:
        return LivenessDecision(ExecutionState.EXECUTING)
    if ready_work_exists:
        return LivenessDecision(
            ExecutionState.BLOCKED_TECHNICAL, "QUEUED_WITH_ZERO_EXECUTION", True
        )
    return LivenessDecision(ExecutionState.IDLE_NO_WORK)


def select_zero_cost_provider(
    providers: tuple[ProviderCandidate, ...],
    *,
    required_capability: str,
    private_data: bool,
) -> ProviderCandidate | None:
    eligible = [
        p
        for p in providers
        if p.state in {ProviderState.AVAILABLE, ProviderState.DEGRADED}
        and p.zero_cost_verified
        and required_capability in p.capabilities
        and (not private_data or p.privacy_eligible)
    ]
    if not eligible:
        return None
    return sorted(
        eligible,
        key=lambda p: (
            p.state != ProviderState.AVAILABLE,
            -p.score,
            p.provider_id,
        ),
    )[0]
