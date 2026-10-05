"""Fail-closed soak evidence contracts for UAOS continuous execution.

The evaluator deliberately distinguishes implementation correctness from long-duration
operational evidence. A clean run shorter than the policy duration is INCOMPLETE,
never PASS.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.p3.contracts import content_digest

from .continuous_dispatcher import ExecutionState
from .contracts import NightShiftContractError


class SoakStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True, slots=True)
class SoakPolicy:
    required_duration_seconds: int = 72 * 60 * 60
    min_samples: int = 2
    max_sample_gap_seconds: int = 120
    max_heartbeat_age_seconds: int = 90
    max_restart_recovery_seconds: int = 180
    require_watchdog: bool = True

    def __post_init__(self) -> None:
        if self.required_duration_seconds < 1:
            raise NightShiftContractError("required_duration_seconds must be positive")
        if self.min_samples < 2:
            raise NightShiftContractError("min_samples must be at least two")
        if self.max_sample_gap_seconds < 1:
            raise NightShiftContractError("max_sample_gap_seconds must be positive")
        if self.max_heartbeat_age_seconds < 1:
            raise NightShiftContractError("max_heartbeat_age_seconds must be positive")
        if self.max_restart_recovery_seconds < 1:
            raise NightShiftContractError("max_restart_recovery_seconds must be positive")


@dataclass(frozen=True, slots=True)
class SoakSample:
    observed_at_epoch: int
    heartbeat_epoch: int
    worker_id: str
    pid: int | None
    state: ExecutionState
    task_id: str | None
    ready_work_exists: bool
    watchdog_watching: bool
    process_alive: bool
    execution_evidence: bool = False

    def __post_init__(self) -> None:
        worker_id = self.worker_id.strip()
        task_id = self.task_id.strip() if self.task_id is not None else None
        if self.observed_at_epoch < 0:
            raise NightShiftContractError("observed_at_epoch cannot be negative")
        if self.heartbeat_epoch < 0:
            raise NightShiftContractError("heartbeat_epoch cannot be negative")
        if self.heartbeat_epoch > self.observed_at_epoch:
            raise NightShiftContractError("heartbeat_epoch cannot be in the future")
        if not worker_id:
            raise NightShiftContractError("worker_id is required")
        if self.pid is not None and self.pid < 1:
            raise NightShiftContractError("pid must be positive when present")
        if task_id == "":
            raise NightShiftContractError("task_id cannot be blank")
        object.__setattr__(self, "worker_id", worker_id)
        object.__setattr__(self, "task_id", task_id)


@dataclass(frozen=True, slots=True)
class SoakEvaluation:
    status: SoakStatus
    first_observed_at_epoch: int | None
    last_observed_at_epoch: int | None
    duration_seconds: int
    sample_count: int
    worker_restart_count: int
    bounded_recovery_count: int
    max_sample_gap_seconds: int
    max_heartbeat_age_seconds: int
    findings: tuple[str, ...]

    def digest(self) -> str:
        return content_digest(
            {
                "status": self.status.value,
                "first_observed_at_epoch": self.first_observed_at_epoch,
                "last_observed_at_epoch": self.last_observed_at_epoch,
                "duration_seconds": self.duration_seconds,
                "sample_count": self.sample_count,
                "worker_restart_count": self.worker_restart_count,
                "bounded_recovery_count": self.bounded_recovery_count,
                "max_sample_gap_seconds": self.max_sample_gap_seconds,
                "max_heartbeat_age_seconds": self.max_heartbeat_age_seconds,
                "findings": list(self.findings),
            }
        )


def _validate_sample_order(samples: tuple[SoakSample, ...]) -> None:
    previous: int | None = None
    for sample in samples:
        if previous is not None and sample.observed_at_epoch <= previous:
            raise NightShiftContractError(
                "soak samples must have strictly increasing observed_at_epoch"
            )
        previous = sample.observed_at_epoch


def evaluate_soak(
    samples: tuple[SoakSample, ...],
    *,
    policy: SoakPolicy = SoakPolicy(),
) -> SoakEvaluation:
    """Evaluate long-duration continuity without overstating operational evidence."""

    if not samples:
        return SoakEvaluation(
            status=SoakStatus.INCOMPLETE,
            first_observed_at_epoch=None,
            last_observed_at_epoch=None,
            duration_seconds=0,
            sample_count=0,
            worker_restart_count=0,
            bounded_recovery_count=0,
            max_sample_gap_seconds=0,
            max_heartbeat_age_seconds=0,
            findings=("NO_SAMPLES",),
        )

    _validate_sample_order(samples)

    hard_findings: set[str] = set()
    worker_ids = {sample.worker_id for sample in samples}
    if len(worker_ids) != 1:
        hard_findings.add("WORKER_ID_DRIFT")

    max_gap = 0
    max_heartbeat_age = 0
    restart_count = 0
    bounded_recovery_count = 0
    last_alive_pid: int | None = None
    outage_started_at: int | None = None

    for index, sample in enumerate(samples):
        heartbeat_age = sample.observed_at_epoch - sample.heartbeat_epoch
        max_heartbeat_age = max(max_heartbeat_age, heartbeat_age)

        if index:
            gap = sample.observed_at_epoch - samples[index - 1].observed_at_epoch
            max_gap = max(max_gap, gap)
            if gap > policy.max_sample_gap_seconds:
                hard_findings.add("SAMPLE_GAP_EXCEEDED")

        if policy.require_watchdog and not sample.watchdog_watching:
            hard_findings.add("WATCHDOG_NOT_WATCHING")

        if not sample.process_alive:
            if outage_started_at is None:
                outage_started_at = sample.observed_at_epoch
            continue

        if outage_started_at is not None:
            recovery_seconds = sample.observed_at_epoch - outage_started_at
            if recovery_seconds > policy.max_restart_recovery_seconds:
                hard_findings.add("RESTART_RECOVERY_EXCEEDED")
            else:
                bounded_recovery_count += 1
            outage_started_at = None

        if heartbeat_age > policy.max_heartbeat_age_seconds:
            hard_findings.add("STALE_HEARTBEAT")

        if last_alive_pid is not None and sample.pid is not None and sample.pid != last_alive_pid:
            restart_count += 1
        if sample.pid is not None:
            last_alive_pid = sample.pid

        if sample.ready_work_exists and sample.state is ExecutionState.IDLE_NO_WORK:
            hard_findings.add("READY_WORK_REPORTED_IDLE")

        if sample.state is ExecutionState.EXECUTING:
            if sample.task_id is None:
                hard_findings.add("EXECUTING_WITHOUT_TASK")
            if not sample.execution_evidence:
                hard_findings.add("EXECUTING_WITHOUT_EVIDENCE")

        if sample.state is ExecutionState.BLOCKED_TECHNICAL:
            hard_findings.add("TECHNICAL_BLOCK_WHILE_PROCESS_ALIVE")
        if sample.state is ExecutionState.QUARANTINED:
            hard_findings.add("QUARANTINED_DURING_SOAK")
        if sample.state is ExecutionState.STOPPED:
            hard_findings.add("STOPPED_DURING_SOAK")

    if outage_started_at is not None:
        hard_findings.add("UNRECOVERED_WORKER_OUTAGE")

    first = samples[0].observed_at_epoch
    last = samples[-1].observed_at_epoch
    duration = last - first

    if hard_findings:
        status = SoakStatus.FAIL
        findings = tuple(sorted(hard_findings))
    else:
        incomplete: list[str] = []
        if len(samples) < policy.min_samples:
            incomplete.append("MIN_SAMPLES_NOT_MET")
        if duration < policy.required_duration_seconds:
            incomplete.append("DURATION_NOT_MET")
        if incomplete:
            status = SoakStatus.INCOMPLETE
            findings = tuple(incomplete)
        else:
            status = SoakStatus.PASS
            findings = ()

    return SoakEvaluation(
        status=status,
        first_observed_at_epoch=first,
        last_observed_at_epoch=last,
        duration_seconds=duration,
        sample_count=len(samples),
        worker_restart_count=restart_count,
        bounded_recovery_count=bounded_recovery_count,
        max_sample_gap_seconds=max_gap,
        max_heartbeat_age_seconds=max_heartbeat_age,
        findings=findings,
    )
