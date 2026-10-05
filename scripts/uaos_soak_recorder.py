"""Record real UAOS worker continuity evidence and evaluate it fail-closed."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from core.night_shift.continuous_dispatcher import ExecutionState
from core.night_shift.soak_evidence import (
    SoakPolicy,
    SoakSample,
    evaluate_soak,
)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _read_tasks(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{path} must contain a JSON array of task objects")
    return value


def _epoch(value: object) -> int:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("heartbeat timestamp is required")
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def _pid_alive(pid: int | None) -> bool:
    if pid is None or pid < 1:
        return False
    if os.name == "nt":
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
            capture_output=True,
            check=False,
            text=True,
        )
        for row in csv.reader(completed.stdout.splitlines()):
            if len(row) >= 2 and row[1].strip() == str(pid):
                return True
        return False
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _child_process_alive(pid: int | None) -> bool:
    if pid is None or pid < 1:
        return False
    if os.name == "nt":
        command = (
            "Get-CimInstance Win32_Process | "
            f"Where-Object {{$_.ParentProcessId -eq {pid}}} | "
            "Select-Object -First 1 -ExpandProperty ProcessId"
        )
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", command],
            capture_output=True,
            check=False,
            text=True,
        )
        return bool(completed.stdout.strip())
    completed = subprocess.run(
        ["ps", "-o", "pid=", "--ppid", str(pid)],
        capture_output=True,
        check=False,
        text=True,
    )
    return bool(completed.stdout.strip())


def _ready_work_exists(tasks: list[dict[str, Any]], now_epoch: int) -> bool:
    for task in tasks:
        status = str(task.get("status", "")).upper()
        attempts = int(task.get("attempts", 0))
        max_attempts = int(task.get("max_attempts", 3))
        next_run = int(task.get("next_run_epoch", 0))
        if (
            status in {"READY", "RETRY"}
            and attempts < max_attempts
            and next_run <= now_epoch
        ):
            return True
    return False


def capture_sample(state_dir: Path) -> SoakSample:
    heartbeat = _read_json(state_dir / "heartbeat.json")
    runtime = _read_json(state_dir / "runtime.json")
    watchdog = _read_json(state_dir / "watchdog.json")
    tasks = _read_tasks(state_dir / "tasks.json")

    observed = int(time.time())
    heartbeat_epoch = _epoch(heartbeat.get("ts"))
    pid_value = heartbeat.get("pid")
    pid = int(pid_value) if pid_value is not None else None
    state = ExecutionState(str(heartbeat.get("state", "")))
    task_value = heartbeat.get("task_id")
    task_id = str(task_value).strip() if task_value is not None else None

    process_alive = _pid_alive(pid)
    child_alive = _child_process_alive(pid) if state is ExecutionState.EXECUTING else False
    runtime_agrees = (
        runtime.get("pid") == heartbeat.get("pid")
        and runtime.get("state") == heartbeat.get("state")
        and runtime.get("task_id") == heartbeat.get("task_id")
    )
    execution_evidence = (
        state is ExecutionState.EXECUTING
        and task_id is not None
        and process_alive
        and child_alive
        and runtime_agrees
    )

    return SoakSample(
        observed_at_epoch=observed,
        heartbeat_epoch=heartbeat_epoch,
        worker_id=str(heartbeat.get("worker", "")),
        pid=pid,
        state=state,
        task_id=task_id,
        ready_work_exists=_ready_work_exists(tasks, observed),
        watchdog_watching=str(watchdog.get("state", "")).upper() == "WATCHING",
        process_alive=process_alive,
        execution_evidence=execution_evidence,
    )


def _sample_payload(sample: SoakSample) -> dict[str, Any]:
    payload = asdict(sample)
    payload["state"] = sample.state.value
    return payload


def _load_samples(path: Path) -> tuple[SoakSample, ...]:
    samples: list[SoakSample] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw = json.loads(line)
            samples.append(
                SoakSample(
                    observed_at_epoch=int(raw["observed_at_epoch"]),
                    heartbeat_epoch=int(raw["heartbeat_epoch"]),
                    worker_id=str(raw["worker_id"]),
                    pid=int(raw["pid"]) if raw.get("pid") is not None else None,
                    state=ExecutionState(str(raw["state"])),
                    task_id=raw.get("task_id"),
                    ready_work_exists=bool(raw["ready_work_exists"]),
                    watchdog_watching=bool(raw["watchdog_watching"]),
                    process_alive=bool(raw["process_alive"]),
                    execution_evidence=bool(raw.get("execution_evidence", False)),
                )
            )
    return tuple(samples)


def record(
    *,
    state_dir: Path,
    output: Path,
    summary: Path,
    duration_seconds: int,
    interval_seconds: int,
    heartbeat_age_seconds: int,
    restart_recovery_seconds: int,
) -> int:
    if duration_seconds < 1:
        raise ValueError("duration_seconds must be positive")
    if interval_seconds < 1:
        raise ValueError("interval_seconds must be positive")

    output.parent.mkdir(parents=True, exist_ok=True)
    summary.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.stat().st_size:
        raise ValueError("output evidence file must be new or empty")
    start: int | None = None

    with output.open("w", encoding="utf-8") as handle:
        while True:
            sample = capture_sample(state_dir)
            if start is None:
                start = sample.observed_at_epoch
            handle.write(json.dumps(_sample_payload(sample), sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

            if sample.observed_at_epoch - start >= duration_seconds:
                break
            time.sleep(interval_seconds)

    samples = _load_samples(output)
    evaluation = evaluate_soak(
        samples,
        policy=SoakPolicy(
            required_duration_seconds=duration_seconds,
            max_sample_gap_seconds=max(interval_seconds * 4, interval_seconds + 1),
            max_heartbeat_age_seconds=heartbeat_age_seconds,
            max_restart_recovery_seconds=restart_recovery_seconds,
        ),
    )
    payload = asdict(evaluation)
    payload["status"] = evaluation.status.value
    payload["digest"] = evaluation.digest()
    summary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if evaluation.status.value == "PASS" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--duration-seconds", type=int, default=72 * 60 * 60)
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--heartbeat-age-seconds", type=int, default=90)
    parser.add_argument("--restart-recovery-seconds", type=int, default=180)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return record(
        state_dir=args.state_dir,
        output=args.output,
        summary=args.summary,
        duration_seconds=args.duration_seconds,
        interval_seconds=args.interval_seconds,
        heartbeat_age_seconds=args.heartbeat_age_seconds,
        restart_recovery_seconds=args.restart_recovery_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
