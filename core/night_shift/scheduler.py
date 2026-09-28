"""Deterministic portfolio scheduler and local resource governor."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import NightShiftContractError, RiskClass


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

    def __post_init__(self) -> None:
        task_id = self.task_id.strip()
        blockers = tuple(sorted({item.strip() for item in self.blocked_by}))
        if not task_id:
            raise NightShiftContractError("task_id is required")
        if self.priority < 0:
            raise NightShiftContractError("priority cannot be negative")
        if not 0 <= self.closure_percent <= 100:
            raise NightShiftContractError("closure_percent must be within 0..100")
        if any(not item for item in blockers):
            raise NightShiftContractError("blocked_by cannot contain blank values")
        object.__setattr__(self, "task_id", task_id)
        object.__setattr__(self, "blocked_by", blockers)


@dataclass(frozen=True, slots=True)
class ResourcePolicy:
    technical_active_max: int = 2
    local_code_writers_max: int = 1
    heavy_local_compute_max: int = 1

    def __post_init__(self) -> None:
        if self.technical_active_max < 1:
            raise NightShiftContractError("technical_active_max must be positive")
        if self.local_code_writers_max < 0:
            raise NightShiftContractError("local_code_writers_max cannot be negative")
        if self.heavy_local_compute_max < 0:
            raise NightShiftContractError("heavy_local_compute_max cannot be negative")


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
