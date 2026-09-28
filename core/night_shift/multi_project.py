"""Multi-project queue compilation and dispatch plan."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import NightShiftContractError
from .executor_registry import ExecutorProfile
from .portfolio import PortfolioSnapshot
from .project_registry import ProjectRegistry
from .routing import route_executor
from .scheduler import ResourcePolicy, WorkItem, select_batch


@dataclass(frozen=True, slots=True)
class Dispatch:
    project_id: str
    task_id: str
    executor_id: str
    repository: str


def compile_dispatches(
    *,
    snapshot: PortfolioSnapshot,
    registry: ProjectRegistry,
    executors: tuple[ExecutorProfile, ...],
    resource_policy: ResourcePolicy,
    now_epoch: int,
) -> tuple[Dispatch, ...]:
    snapshot.require_fresh(now_epoch=now_epoch)
    configs = {x.project_id: x for x in registry.projects}
    items = []
    by_task = {}
    for state in snapshot.projects:
        config = configs.get(state.project_id)
        if config is None or config.repository != state.repository:
            raise NightShiftContractError("live project missing/mismatched registry config")
        blockers = state.blockers + (("STALE_CANDIDATE",) if state.candidate_stale else ())
        if state.ready and not blockers:
            route = route_executor(
                required_capabilities=config.required_capabilities,
                executors=executors,
                mutating=config.mutating,
            )
            item = WorkItem(
                state.task_id,
                config.priority,
                state.closure_percent,
                True,
                blockers,
                state.risk_class,
                route.requires_local_writer,
                route.heavy_compute,
                route.executor_id,
                route.max_parallel,
            )
            by_task[state.task_id] = (state, route)
        else:
            item = WorkItem(
                state.task_id,
                config.priority,
                state.closure_percent,
                False,
                blockers,
                state.risk_class,
                False,
                False,
                None,
                1,
            )
        items.append(item)
    selected = select_batch(tuple(items), policy=resource_policy)
    out = []
    for item in selected:
        state, route = by_task[item.task_id]
        out.append(Dispatch(state.project_id, state.task_id, route.executor_id, state.repository))
    return tuple(out)
