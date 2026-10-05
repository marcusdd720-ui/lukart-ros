from __future__ import annotations

import pytest

from core.night_shift.continuous_dispatcher import ExecutionState
from core.night_shift.contracts import NightShiftContractError
from core.night_shift.soak_evidence import (
    SoakPolicy,
    SoakSample,
    SoakStatus,
    evaluate_soak,
)


def _sample(
    at: int,
    *,
    heartbeat: int | None = None,
    pid: int | None = 10,
    state: ExecutionState = ExecutionState.IDLE_NO_WORK,
    task_id: str | None = None,
    ready: bool = False,
    watchdog: bool = True,
    alive: bool = True,
    execution_evidence: bool = False,
    worker_id: str = "worker-a",
) -> SoakSample:
    return SoakSample(
        observed_at_epoch=at,
        heartbeat_epoch=at if heartbeat is None else heartbeat,
        worker_id=worker_id,
        pid=pid,
        state=state,
        task_id=task_id,
        ready_work_exists=ready,
        watchdog_watching=watchdog,
        process_alive=alive,
        execution_evidence=execution_evidence,
    )


def test_clean_short_run_is_incomplete_not_pass() -> None:
    result = evaluate_soak(
        (_sample(0), _sample(60)),
        policy=SoakPolicy(required_duration_seconds=3600),
    )
    assert result.status is SoakStatus.INCOMPLETE
    assert result.findings == ("DURATION_NOT_MET",)


def test_clean_required_duration_passes() -> None:
    result = evaluate_soak(
        (_sample(0), _sample(60), _sample(120)),
        policy=SoakPolicy(required_duration_seconds=120),
    )
    assert result.status is SoakStatus.PASS
    assert result.findings == ()


def test_empty_evidence_is_incomplete() -> None:
    result = evaluate_soak(())
    assert result.status is SoakStatus.INCOMPLETE
    assert result.findings == ("NO_SAMPLES",)


def test_non_monotonic_samples_fail_closed() -> None:
    with pytest.raises(NightShiftContractError, match="strictly increasing"):
        evaluate_soak((_sample(10), _sample(10)))


def test_ready_work_cannot_be_reported_idle() -> None:
    result = evaluate_soak(
        (_sample(0), _sample(60, ready=True)),
        policy=SoakPolicy(required_duration_seconds=60),
    )
    assert result.status is SoakStatus.FAIL
    assert "READY_WORK_REPORTED_IDLE" in result.findings


def test_executing_requires_task_and_execution_evidence() -> None:
    result = evaluate_soak(
        (
            _sample(0),
            _sample(60, state=ExecutionState.EXECUTING, ready=True),
        ),
        policy=SoakPolicy(required_duration_seconds=60),
    )
    assert result.status is SoakStatus.FAIL
    assert "EXECUTING_WITHOUT_TASK" in result.findings
    assert "EXECUTING_WITHOUT_EVIDENCE" in result.findings


def test_proven_execution_is_valid() -> None:
    result = evaluate_soak(
        (
            _sample(0),
            _sample(
                60,
                state=ExecutionState.EXECUTING,
                task_id="task-1",
                ready=True,
                execution_evidence=True,
            ),
        ),
        policy=SoakPolicy(required_duration_seconds=60),
    )
    assert result.status is SoakStatus.PASS


def test_stale_heartbeat_fails() -> None:
    result = evaluate_soak(
        (_sample(0), _sample(60, heartbeat=0)),
        policy=SoakPolicy(
            required_duration_seconds=60,
            max_heartbeat_age_seconds=30,
        ),
    )
    assert result.status is SoakStatus.FAIL
    assert "STALE_HEARTBEAT" in result.findings


def test_missing_watchdog_fails() -> None:
    result = evaluate_soak(
        (_sample(0), _sample(60, watchdog=False)),
        policy=SoakPolicy(required_duration_seconds=60),
    )
    assert result.status is SoakStatus.FAIL
    assert "WATCHDOG_NOT_WATCHING" in result.findings


def test_sample_gap_fails() -> None:
    result = evaluate_soak(
        (_sample(0), _sample(121)),
        policy=SoakPolicy(
            required_duration_seconds=120,
            max_sample_gap_seconds=120,
        ),
    )
    assert result.status is SoakStatus.FAIL
    assert "SAMPLE_GAP_EXCEEDED" in result.findings


def test_bounded_worker_outage_can_recover() -> None:
    result = evaluate_soak(
        (
            _sample(0, pid=10),
            _sample(30, pid=None, alive=False),
            _sample(60, pid=11),
            _sample(120, pid=11),
        ),
        policy=SoakPolicy(
            required_duration_seconds=120,
            max_restart_recovery_seconds=60,
        ),
    )
    assert result.status is SoakStatus.PASS
    assert result.bounded_recovery_count == 1
    assert result.worker_restart_count == 1


def test_long_worker_outage_fails() -> None:
    result = evaluate_soak(
        (
            _sample(0, pid=10),
            _sample(30, pid=None, alive=False),
            _sample(240, pid=11),
        ),
        policy=SoakPolicy(
            required_duration_seconds=240,
            max_sample_gap_seconds=300,
            max_restart_recovery_seconds=60,
        ),
    )
    assert result.status is SoakStatus.FAIL
    assert "RESTART_RECOVERY_EXCEEDED" in result.findings


def test_unrecovered_worker_outage_fails() -> None:
    result = evaluate_soak(
        (
            _sample(0, pid=10),
            _sample(60, pid=None, alive=False),
        ),
        policy=SoakPolicy(required_duration_seconds=60),
    )
    assert result.status is SoakStatus.FAIL
    assert "UNRECOVERED_WORKER_OUTAGE" in result.findings


def test_worker_identity_drift_fails() -> None:
    result = evaluate_soak(
        (_sample(0), _sample(60, worker_id="worker-b")),
        policy=SoakPolicy(required_duration_seconds=60),
    )
    assert result.status is SoakStatus.FAIL
    assert "WORKER_ID_DRIFT" in result.findings


def test_live_technical_block_fails() -> None:
    result = evaluate_soak(
        (
            _sample(0),
            _sample(60, state=ExecutionState.BLOCKED_TECHNICAL),
        ),
        policy=SoakPolicy(required_duration_seconds=60),
    )
    assert result.status is SoakStatus.FAIL
    assert "TECHNICAL_BLOCK_WHILE_PROCESS_ALIVE" in result.findings


def test_digest_is_deterministic() -> None:
    policy = SoakPolicy(required_duration_seconds=60)
    samples = (_sample(0), _sample(60))
    first = evaluate_soak(samples, policy=policy)
    second = evaluate_soak(samples, policy=policy)
    assert first.digest() == second.digest()
