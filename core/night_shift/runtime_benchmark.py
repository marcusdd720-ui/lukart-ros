"""Evidence-first durable runtime selection."""

from __future__ import annotations

from dataclasses import dataclass

from core.p3.contracts import content_digest

from .contracts import NightShiftContractError
from .runtime_profiles import RuntimeEvidence, RuntimeProfile, RuntimeRequirements


@dataclass(frozen=True, slots=True)
class RuntimeObservation:
    runtime_profile_digest: str
    crash_resume_pass: bool
    idempotency_pass: bool
    deterministic_replay_pass: bool
    durable_timer_pass: bool
    distributed_workers_pass: bool
    setup_ms: int
    recovery_ms: int
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.runtime_profile_digest) != 64 or self.setup_ms < 0 or self.recovery_ms < 0:
            raise NightShiftContractError("invalid runtime observation")
        refs = tuple(sorted({x.strip() for x in self.evidence_refs}))
        if not refs or any(not x for x in refs):
            raise NightShiftContractError("runtime observation requires evidence")
        object.__setattr__(self, "evidence_refs", refs)

    def digest(self) -> str:
        return content_digest(
            {
                "runtime_profile_digest": self.runtime_profile_digest,
                "crash_resume_pass": self.crash_resume_pass,
                "idempotency_pass": self.idempotency_pass,
                "deterministic_replay_pass": self.deterministic_replay_pass,
                "durable_timer_pass": self.durable_timer_pass,
                "distributed_workers_pass": self.distributed_workers_pass,
                "setup_ms": self.setup_ms,
                "recovery_ms": self.recovery_ms,
                "evidence_refs": list(self.evidence_refs),
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeDecision:
    runtime_id: str
    profile_digest: str
    observation_digest: str
    requirements_digest: str
    reason: str


def select_runtime(
    *,
    profiles: tuple[RuntimeProfile, ...],
    observations: tuple[RuntimeObservation, ...],
    requirements: RuntimeRequirements,
) -> RuntimeDecision:
    by_digest = {x.runtime_profile_digest: x for x in observations}
    candidates = []
    for p in profiles:
        o = by_digest.get(p.digest())
        if (
            p.evidence is not RuntimeEvidence.VALIDATED
            or o is None
            or not p.satisfies(requirements)
        ):
            continue
        checks = (
            (requirements.crash_resume, o.crash_resume_pass),
            (requirements.idempotent_steps, o.idempotency_pass),
            (requirements.deterministic_replay, o.deterministic_replay_pass),
            (requirements.durable_timers, o.durable_timer_pass),
            (requirements.distributed_workers, o.distributed_workers_pass),
        )
        if all((not req) or ok for req, ok in checks):
            candidates.append((p, o))
    if not candidates:
        raise NightShiftContractError("no validated runtime satisfies requirements")
    p, o = min(
        candidates,
        key=lambda x: (x[0].operational_rank, x[1].recovery_ms, x[1].setup_ms, x[0].runtime_id),
    )
    return RuntimeDecision(
        p.runtime_id,
        p.digest(),
        o.digest(),
        requirements.digest(),
        "minimum validated operational rank",
    )
