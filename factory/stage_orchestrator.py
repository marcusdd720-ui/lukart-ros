"""Autonomous lifecycle controller for the LukArt ROS Factory."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

from factory.self_healing import repair_repository
from factory.stage_registry import get_stage, next_stage

DEFAULT_STATE = {
    "current_stage": 6,
    "last_completed_stage": 5,
    "status": "READY",
}
MAX_ATTEMPTS = 5
SMOKE_DISCOVERY_ATTEMPTS = 15
SMOKE_DISCOVERY_DELAY_SECONDS = 2


class OrchestratorError(RuntimeError):
    """Raised when lifecycle state is invalid or automation cannot proceed."""


def load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return DEFAULT_STATE.copy()
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OrchestratorError(f"Invalid orchestrator state JSON: {path}") from exc
    if not isinstance(state, dict):
        raise OrchestratorError("Orchestrator state must be a JSON object")
    current = state.get("current_stage")
    completed = state.get("last_completed_stage")
    status = state.get("status")
    if not isinstance(current, int) or not isinstance(completed, int):
        raise OrchestratorError("Orchestrator state requires integer stage fields")
    get_stage(current)
    if completed < -1 or completed > current:
        raise OrchestratorError("Orchestrator state has inconsistent stage ordering")
    if completed == current and status != "COMPLETE":
        raise OrchestratorError("Orchestrator state has inconsistent terminal status")
    return state


def write_state(path: Path, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print(f"[orchestrator] {' '.join(command)}")
    return subprocess.run(command, check=False, text=True, capture_output=capture)


def git_sha() -> str:
    result = run(["git", "rev-parse", "HEAD"], capture=True)
    if result.returncode != 0:
        raise OrchestratorError("Cannot resolve current SHA")
    return result.stdout.strip()


def dispatch_smoke(stage_number: int, expected_sha: str) -> int:
    """Dispatch Smoke Test and locate exactly the run for the expected SHA."""
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not repository:
        raise OrchestratorError("GITHUB_REPOSITORY is required")
    result = run(
        [
            "gh",
            "workflow",
            "run",
            "github-app-smoke.yml",
            "--repo",
            repository,
            "--ref",
            "main",
            "-f",
            f"stage={stage_number}",
        ],
        capture=True,
    )
    if result.returncode != 0:
        raise OrchestratorError(result.stderr.strip() or "Smoke Test dispatch failed")
    for _ in range(SMOKE_DISCOVERY_ATTEMPTS):
        runs = run(
            [
                "gh",
                "run",
                "list",
                "--repo",
                repository,
                "--workflow",
                "github-app-smoke.yml",
                "--limit",
                "50",
                "--json",
                "databaseId,headSha,status,conclusion,event,createdAt",
            ],
            capture=True,
        )
        if runs.returncode != 0:
            raise OrchestratorError(runs.stderr.strip() or "Cannot locate Smoke Test run")
        try:
            entries = json.loads(runs.stdout)
        except json.JSONDecodeError as exc:
            raise OrchestratorError("Invalid Smoke Test run list") from exc
        for entry in entries:
            if entry.get("event") == "workflow_dispatch" and entry.get("headSha") == expected_sha:
                return int(entry["databaseId"])
        time.sleep(SMOKE_DISCOVERY_DELAY_SECONDS)
    raise OrchestratorError(f"Fresh-SHA Smoke Test run was not found for {expected_sha}")


def wait_for_run(run_id: int) -> tuple[bool, str]:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    for _ in range(180):
        result = run(
            ["gh", "run", "view", str(run_id), "--repo", repository, "--json", "status,conclusion"],
            capture=True,
        )
        if result.returncode != 0:
            raise OrchestratorError(result.stderr.strip() or f"Cannot inspect run {run_id}")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise OrchestratorError(f"Invalid workflow result for run {run_id}") from exc
        status = payload.get("status")
        conclusion = payload.get("conclusion")
        if status == "completed":
            return conclusion == "success", str(conclusion)
        time.sleep(2)
    raise OrchestratorError(f"Workflow run {run_id} did not complete")
