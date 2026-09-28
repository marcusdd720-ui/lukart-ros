"""Provider-neutral executor capability registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from core.p3.contracts import content_digest

from .config_validation import (
    require_bool,
    require_nonnegative_int,
    require_positive_int,
    require_string,
    require_string_list,
)
from .contracts import NightShiftContractError


@dataclass(frozen=True, slots=True)
class ExecutorProfile:
    executor_id: str
    capabilities: tuple[str, ...]
    mutating: bool
    independent_review: bool
    cost_rank: int
    enabled: bool
    requires_local_writer: bool = False
    heavy_compute: bool = False
    max_parallel: int = 1

    def __post_init__(self) -> None:
        caps = tuple(sorted({x.strip() for x in self.capabilities}))
        if not self.executor_id.strip() or not caps or self.cost_rank < 0:
            raise NightShiftContractError("invalid executor profile")
        if self.max_parallel < 1:
            raise NightShiftContractError("max_parallel must be positive")
        object.__setattr__(self, "capabilities", caps)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "executor_id": self.executor_id,
            "capabilities": list(self.capabilities),
            "mutating": self.mutating,
            "independent_review": self.independent_review,
            "cost_rank": self.cost_rank,
            "enabled": self.enabled,
            "requires_local_writer": self.requires_local_writer,
            "heavy_compute": self.heavy_compute,
            "max_parallel": self.max_parallel,
        }


def executor_registry_digest(executors: tuple[ExecutorProfile, ...]) -> str:
    ordered = sorted(executors, key=lambda item: item.executor_id)
    return content_digest({"executors": [item.canonical_dict() for item in ordered]})


def load_executor_profiles(path: str | Path) -> tuple[ExecutorProfile, ...]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("executors"), list):
        raise NightShiftContractError("executor registry must contain executors")
    items = tuple(
        ExecutorProfile(
            require_string(x["executor_id"], field_name="executor_id"),
            require_string_list(x["capabilities"], field_name="capabilities"),
            require_bool(x["mutating"], field_name="mutating"),
            require_bool(x["independent_review"], field_name="independent_review"),
            require_nonnegative_int(x["cost_rank"], field_name="cost_rank"),
            require_bool(x["enabled"], field_name="enabled"),
            require_bool(x["requires_local_writer"], field_name="requires_local_writer"),
            require_bool(x["heavy_compute"], field_name="heavy_compute"),
            require_positive_int(x["max_parallel"], field_name="max_parallel"),
        )
        for x in raw["executors"]
    )
    if len({x.executor_id for x in items}) != len(items):
        raise NightShiftContractError("executor ids must be unique")
    return items
