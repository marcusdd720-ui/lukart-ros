"""Deterministic portfolio scheduler and local resource governor."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import RiskClass


@dataclass(frozen=True, slots=True)
class WorkItem:
    task_id: str
    priority: int
    closure_percent: int
    ready: bool
    blocked_by: tuple[str, ...]
    risk_class: RiskClass
    requires_local_writer: bool = True
    heavy_compute: bool = False


@dataclass(frozen=True, slots=True)
class ResourcePolicy:
    technical_active_max: int = 2
    local_code_writers_max: int = 1
    heavy_local_compute_max: int = 1


def compile_ready_queue(items: tuple[WorkItem, ...]) -> tuple[WorkItem, ...]:
    ready = [
        item
        for item in items
        if item.ready and not item.blocked_by and 0 <= item.closure_percent <= 100
    ]
    return tuple(
        sorted(
            ready,
            key=lambda item: (
                item.priority,
                -item.closure_percent,
                item.risk_class.value,
                item.task_id,
            ),
        )
    )


def select_batch(
    items: tuple[WorkItem, ...],
    *,
    policy: ResourcePolicy,
) -> tuple[WorkItem, ...]:
    selected: list[WorkItem] = []
    writers = 0
    heavy = 0
    for item in compile_ready_queue(items):
        if len(selected) >= policy.technical_active_max:
            break
        if item.requires_local_writer and writers >= policy.local_code_writers_max:
            continue
        if item.heavy_compute and heavy >= policy.heavy_local_compute_max:
            continue
        selected.append(item)
        writers += int(item.requires_local_writer)
        heavy += int(item.heavy_compute)
    return tuple(selected)
