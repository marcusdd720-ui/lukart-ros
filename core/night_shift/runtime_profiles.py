"""Durable runtime profiles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

from core.p3.contracts import content_digest

from .config_validation import (
    require_bool,
    require_nonnegative_int,
    require_string,
    require_string_list,
)
from .contracts import NightShiftContractError


class RuntimeEvidence(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    DOCUMENTED = "DOCUMENTED"
    VALIDATED = "VALIDATED"


@dataclass(frozen=True, slots=True)
class RuntimeRequirements:
    crash_resume: bool = True
    idempotent_steps: bool = True
    deterministic_replay: bool = False
    durable_timers: bool = False
    distributed_workers: bool = False

    def digest(self) -> str:
        return content_digest(
            {
                "crash_resume": self.crash_resume,
                "idempotent_steps": self.idempotent_steps,
                "deterministic_replay": self.deterministic_replay,
                "durable_timers": self.durable_timers,
                "distributed_workers": self.distributed_workers,
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeProfile:
    runtime_id: str
    adapter: str
    evidence: RuntimeEvidence
    crash_resume: bool
    idempotent_steps: bool
    deterministic_replay: bool
    durable_timers: bool
    distributed_workers: bool
    requires_external_service: bool
    operational_rank: int
    source_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.runtime_id.strip() or not self.adapter.strip():
            raise NightShiftContractError("runtime identity is required")
        if self.operational_rank < 0:
            raise NightShiftContractError("operational_rank cannot be negative")
        refs = tuple(sorted({x.strip() for x in self.source_refs}))
        if not refs or any(not x for x in refs):
            raise NightShiftContractError("runtime profile requires evidence refs")
        object.__setattr__(self, "source_refs", refs)

    def satisfies(self, r: RuntimeRequirements) -> bool:
        pairs = (
            (r.crash_resume, self.crash_resume),
            (r.idempotent_steps, self.idempotent_steps),
            (r.deterministic_replay, self.deterministic_replay),
            (r.durable_timers, self.durable_timers),
            (r.distributed_workers, self.distributed_workers),
        )
        return all((not req) or got for req, got in pairs)

    def digest(self) -> str:
        return content_digest(
            {
                "runtime_id": self.runtime_id,
                "adapter": self.adapter,
                "evidence": self.evidence.value,
                "crash_resume": self.crash_resume,
                "idempotent_steps": self.idempotent_steps,
                "deterministic_replay": self.deterministic_replay,
                "durable_timers": self.durable_timers,
                "distributed_workers": self.distributed_workers,
                "requires_external_service": self.requires_external_service,
                "operational_rank": self.operational_rank,
                "source_refs": list(self.source_refs),
            }
        )


def load_runtime_profiles(path: str | Path) -> tuple[RuntimeProfile, ...]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("runtimes"), list):
        raise NightShiftContractError("runtime matrix must contain runtimes")
    out = []
    for item in raw["runtimes"]:
        out.append(
            RuntimeProfile(
                runtime_id=require_string(item["runtime_id"], field_name="runtime_id"),
                adapter=require_string(item["adapter"], field_name="adapter"),
                evidence=RuntimeEvidence(str(item["evidence"])),
                crash_resume=require_bool(
                    item["crash_resume"], field_name="crash_resume"
                ),
                idempotent_steps=require_bool(
                    item["idempotent_steps"], field_name="idempotent_steps"
                ),
                deterministic_replay=require_bool(
                    item["deterministic_replay"], field_name="deterministic_replay"
                ),
                durable_timers=require_bool(
                    item["durable_timers"], field_name="durable_timers"
                ),
                distributed_workers=require_bool(
                    item["distributed_workers"], field_name="distributed_workers"
                ),
                requires_external_service=require_bool(
                    item["requires_external_service"],
                    field_name="requires_external_service",
                ),
                operational_rank=require_nonnegative_int(
                    item["operational_rank"], field_name="operational_rank"
                ),
                source_refs=require_string_list(
                    item["source_refs"], field_name="source_refs"
                ),
            )
        )
    if len({x.runtime_id for x in out}) != len(out):
        raise NightShiftContractError("runtime ids must be unique")
    return tuple(sorted(out, key=lambda x: x.runtime_id))
