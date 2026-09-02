"""Autonomous lifecycle controller for the LukArt ROS Factory."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

from factory.stage_registry import STAGES, get_stage, next_stage

DEFAULT_STATE = {
    "current_stage": 6,
    "last_completed_stage": 5,
    "status": "READY",
}
MAX_STAGE = max(stage.number for stage in STAGES)
MAX_ATTEMPTS = 5


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
    if not isinstance(current, int) or not isinstance(completed, int):
        raise OrchestratorError("Orchestrator state requires integer stage fields")
    get_stage(current)
    if completed < -1 or completed >= current:
        raise OrchestratorError("Orchestrator state has inconsistent stage ordering")
    return state


def write_state(path: Path, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print(f"[orchestrator] {' '.join(command)}")
    return subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=capture,
    )


def dispatch_smoke(stage_number: int) -> int:
    """Dispatch the GitHub App Smoke Test and return its workflow run id."""
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
    time.sleep(2)
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
            "20",
            "--json",
            "databaseId,headSha,status,conclusion,event",
        ],
        capture=True,
    )
    if runs.returncode != 0:
        raise OrchestratorError(runs.stderr.strip() or "Cannot locate Smoke Test run")
    try:
        entries = json.loads(runs.stdout)
    except json.JSONDecodeError as exc:
        raise OrchestratorError("Invalid Smoke Test run list") from exc
    current_sha = git_sha()
    for entry in entries:
        if entry.get("event") == "workflow_dispatch" and entry.get("headSha") == current_sha:
            return int(entry["databaseId"])
    raise OrchestratorError("Fresh-SHA Smoke Test run was not found")


def wait_for_run(run_id: int) -> tuple[bool, str]:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    for _ in range(180):
        result = run(
            [
                "gh",
                "run",
                "view",
                str(run_id),
                "--repo",
                repository,
                "--json",
                "status,conclusion,headSha",
            ],
            capture=True,
        )
        if result.returncode != 0:
            raise OrchestratorError(result.stderr.strip() or "Cannot inspect Smoke Test run")
        data = json.loads(result.stdout)
        if data["status"] == "completed":
            return data["conclusion"] == "success", str(data["conclusion"])
        time.sleep(5)
    raise OrchestratorError("Smoke Test timeout")


def capture_failure(run_id: int) -> str:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    result = run(
        [
            "gh",
            "run",
            "view",
            str(run_id),
            "--repo",
            repository,
            "--log-failed",
        ],
        capture=True,
    )
    return (result.stdout + result.stderr)[-20000:]


def auto_repair() -> bool:
    """Apply only deterministic, source-preserving repairs and require a changed tree."""
    changed = False
    for command in (
        ["python", "-m", "ruff", "check", ".", "--fix"],
        ["python", "-m", "ruff", "format", "."],
    ):
        result = run(command, capture=True)
        if result.returncode not in (0, 1):
            print(result.stdout)
            print(result.stderr)
    status = run(["git", "status", "--porcelain"], capture=True)
    if status.returncode != 0:
        raise OrchestratorError(status.stderr.strip() or "Cannot inspect repair diff")
    if status.stdout.strip():
        changed = True
        add = run(["git", "add", "-A"])
        if add.returncode != 0:
            raise OrchestratorError("Cannot stage automatic repair")
        commit = run(["git", "commit", "-m", "fix: automatic stage repair"])
        if commit.returncode != 0:
            raise OrchestratorError("Cannot commit automatic repair")
        push = run(["git", "push", "origin", "HEAD:main"])
        if push.returncode != 0:
            raise OrchestratorError("Cannot publish automatic repair")
    return changed


def advance_state(state: dict[str, object], current_number: int) -> None:
    following = next_stage(current_number)
    state["last_completed_stage"] = current_number
    state["last_result"] = "PASS"
    state.pop("failed_stage", None)
    state.pop("block_reason", None)
    if following is None:
        state["current_stage"] = current_number
        state["status"] = "COMPLETE"
    else:
        state["current_stage"] = following.number
        state["status"] = "READY"


def git_sha() -> str:
    result = run(["git", "rev-parse", "HEAD"], capture=True)
    if result.returncode != 0:
        raise OrchestratorError("Cannot resolve current SHA")
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, default=Path("factory/stage_state.json"))
    parser.add_argument("--stage", default="", help="Override current stage")
    args = parser.parse_args()

    state = load_state(args.state_file)
    current_value = int(args.stage) if args.stage else state["current_stage"]
    if not isinstance(current_value, int):
        raise OrchestratorError("Orchestrator stage must be an integer")
    current_number = current_value

    while current_number <= MAX_STAGE:
        current = get_stage(current_number)
        print(f"CURRENT_STAGE={current.number}")
        print(f"CURRENT_STAGE_NAME={current.name}")
        state["current_stage"] = current.number
        state["status"] = "RUNNING"
        write_state(args.state_file, state)

        for attempt in range(1, MAX_ATTEMPTS + 1):
            fresh_sha = git_sha()
            print(f"VALIDATION_SHA={fresh_sha}")
            run_id = dispatch_smoke(current.number)
            passed, conclusion = wait_for_run(run_id)
            print(f"SMOKE_RUN_ID={run_id}")
            print(f"SMOKE_CONCLUSION={conclusion}")
            if passed:
                break
            failure_log = capture_failure(run_id)
            print("SMOKE_FAILURE_LOG_START")
            print(failure_log)
            print("SMOKE_FAILURE_LOG_END")
            state["last_result"] = "FAIL"
            state["failed_stage"] = current.number
            write_state(args.state_file, state)
            if attempt == MAX_ATTEMPTS or not auto_repair():
                raise OrchestratorError(
                    f"Stage {current.number} failed and no deterministic repair produced a new SHA"
                )
            time.sleep(3)
        else:
            raise OrchestratorError(f"Stage {current.number} exhausted repair attempts")

        print(f"STAGE {current.number}: PASS")
        advance_state(state, current.number)
        write_state(args.state_file, state)
        current_number = int(state["current_stage"])
        if state["status"] == "COMPLETE":
            print("ORCHESTRATOR_RESULT=COMPLETE")
            return 0

        # Publish the state transition as a fresh commit so the next stage is
        # always validated against a new SHA and starts a new workflow run.
        run(["git", "add", "factory/stage_state.json"])
        run(["git", "commit", "-m", "chore: advance stage lifecycle state"])
        push = run(["git", "push", "origin", "HEAD:main"])
        if push.returncode != 0:
            raise OrchestratorError("Cannot publish lifecycle state")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
