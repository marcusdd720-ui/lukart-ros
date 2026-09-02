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
    """Collect outer Smoke and nested Stage Gate diagnostics for repair classification."""
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
    outer_log = result.stdout + result.stderr
    nested_ids = re.findall(r"\bRUN_ID=(\d+)\b", outer_log)
    nested_logs: list[str] = []
    for nested_id in dict.fromkeys(nested_ids):
        nested = run(
            [
                "gh",
                "run",
                "view",
                nested_id,
                "--repo",
                repository,
                "--log-failed",
            ],
            capture=True,
        )
        nested_logs.append(nested.stdout + nested.stderr)
    combined = outer_log + "\n" + "\n".join(nested_logs)
    return combined[-30000:]


def auto_repair(failure_log: str) -> bool:
    """Diagnose the failure and publish only a safe repair on a fresh SHA."""
    return repair_repository(Path("."), failure_log)


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


def _remote_state(path: Path) -> dict[str, object] | None:
    result = run(["git", "show", f"origin/main:{path.as_posix()}"], capture=True)
    if result.returncode != 0:
        return None
    try:
        state = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return state if isinstance(state, dict) else None


def _remote_already_contains(state: dict[str, object]) -> bool:
    remote = _remote_state(Path("factory/stage_state.json"))
    if remote is None:
        return False
    desired_completed = state.get("last_completed_stage")
    remote_completed = remote.get("last_completed_stage")
    if not isinstance(desired_completed, int) or not isinstance(remote_completed, int):
        return False
    if remote_completed > desired_completed:
        return True
    if remote_completed == desired_completed:
        return (
            remote.get("last_result") == state.get("last_result")
            and remote.get("status") == state.get("status")
        )
    return False


def publish_state(path: Path, state: dict[str, object]) -> None:
    """Publish lifecycle state, tolerating a concurrent equivalent winner."""
    write_state(path, state)
    add = run(["git", "add", str(path)])
    if add.returncode != 0:
        raise OrchestratorError("Cannot stage lifecycle state")
    commit = run(
        ["git", "commit", "-m", "chore: advance stage lifecycle state"]
    )
    if commit.returncode != 0:
        raise OrchestratorError("Cannot commit lifecycle state")
    push = run(["git", "push", "origin", "HEAD:main"])
    if push.returncode == 0:
        return
    fetch = run(["git", "fetch", "origin", "main"])
    if fetch.returncode != 0:
        raise OrchestratorError("Cannot refresh remote lifecycle state")
    if _remote_already_contains(state):
        print("[orchestrator] concurrent lifecycle publication already won")
        return
    raise OrchestratorError("Cannot publish lifecycle state after remote refresh")


def dispatch_next_orchestrator(next_stage_number: int) -> None:
    """Explicitly start the next lifecycle controller after state publication.

    Pushes made with the workflow GITHUB_TOKEN do not recursively trigger a
    new workflow run, so stage progression must use workflow_dispatch.
    """
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not repository:
        raise OrchestratorError("GITHUB_REPOSITORY is required")
    result = run(
        [
            "gh",
            "workflow",
            "run",
            "stage-orchestrator.yml",
            "--repo",
            repository,
            "--ref",
            "main",
            "-f",
            f"stage={next_stage_number}",
        ],
        capture=True,
    )
    if result.returncode != 0:
        raise OrchestratorError(
            result.stderr.strip() or "Next Stage Orchestrator dispatch failed"
        )
    print(f"NEXT_ORCHESTRATOR_DISPATCHED={next_stage_number}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, default=Path("factory/stage_state.json"))
    parser.add_argument("--stage", default="", help="Override current stage")
    args = parser.parse_args()

    state = load_state(args.state_file)
    if state.get("status") == "COMPLETE" and not args.stage:
        print("ORCHESTRATOR_RESULT=COMPLETE")
        return 0
    if args.stage:
        current_number = int(args.stage)
    else:
        current_value = state["current_stage"]
        if not isinstance(current_value, int):
            raise OrchestratorError("Orchestrator state current_stage must be an integer")
        current_number = current_value
    current = get_stage(current_number)
    print(f"CURRENT_STAGE={current.number}")
    print(f"CURRENT_STAGE_NAME={current.name}")
    for attempt in range(1, MAX_ATTEMPTS + 1):
        state["current_stage"] = current.number
        state["status"] = "RUNNING"
        write_state(args.state_file, state)
        fresh_sha = git_sha()
        print(f"VALIDATION_SHA={fresh_sha}")
        run_id = dispatch_smoke(current.number, fresh_sha)
        passed, conclusion = wait_for_run(run_id)
        print(f"SMOKE_RUN_ID={run_id}")
        print(f"SMOKE_CONCLUSION={conclusion}")
        if passed:
            advance_state(state, current.number)
            publish_state(args.state_file, state)
            if state["status"] == "COMPLETE":
                print("ORCHESTRATOR_RESULT=COMPLETE")
            else:
                next_value = state["current_stage"]
                if not isinstance(next_value, int):
                    raise OrchestratorError(
                        "Orchestrator state next current_stage must be an integer"
                    )
                print(f"NEXT_STAGE={next_value}")
                dispatch_next_orchestrator(next_value)
                print("ORCHESTRATOR_RESULT=ADVANCED")
            return 0
        print("SMOKE_FAILURE_LOG_START")
        failure_log = capture_failure(run_id)
        print(failure_log)
        print("SMOKE_FAILURE_LOG_END")
        state["last_result"] = "FAIL"
        state["failed_stage"] = current.number
        write_state(args.state_file, state)
        if attempt == MAX_ATTEMPTS or not auto_repair(failure_log):
            raise OrchestratorError(
                f"Stage {current.number} failed and automatic repair could not produce a new SHA"
            )
        repaired_sha = git_sha()
        if repaired_sha == fresh_sha:
            raise OrchestratorError("Automatic repair did not produce a fresh SHA")
        time.sleep(3)
    raise OrchestratorError(f"Stage {current.number} exhausted repair attempts")


if __name__ == "__main__":
    raise SystemExit(main())
