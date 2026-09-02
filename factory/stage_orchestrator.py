"""Autonomous lifecycle controller for the LukArt ROS Factory."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

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
    """Apply deterministic repairs and require a real source-tree change."""
    state_file = Path("factory/stage_state.json")
    state_backup = state_file.read_text(encoding="utf-8") if state_file.exists() else None
    for command in (
        ["python", "-m", "ruff", "check", ".", "--fix"],
        ["python", "-m", "ruff", "format", "."],
    ):
        result = run(command, capture=True)
        if result.returncode not in (0, 1):
            print(result.stdout)
            print(result.stderr)

    if state_backup is not None:
        state_file.write_text(state_backup, encoding="utf-8")
    reset = run(["git", "checkout", "--", "factory/stage_state.json"])
    if reset.returncode != 0:
        raise OrchestratorError("Cannot restore lifecycle state after repair attempt")

    status = run(["git", "status", "--porcelain"], capture=True)
    if status.returncode != 0:
        raise OrchestratorError(status.stderr.strip() or "Cannot inspect repair diff")
    source_changes = [
        line for line in status.stdout.splitlines() if not line.endswith("factory/stage_state.json")
    ]
    if not source_changes:
        return False
    add = run(["git", "add", "-A"])
    if add.returncode != 0:
        raise OrchestratorError("Cannot stage automatic repair")
    commit = run(["git", "commit", "-m", "fix: automatic stage repair"])
    if commit.returncode != 0:
        raise OrchestratorError("Cannot commit automatic repair")
    push = run(["git", "push", "origin", "HEAD:main"])
    if push.returncode != 0:
        raise OrchestratorError("Cannot publish automatic repair")
    return True


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


def publish_state(path: Path, state: dict[str, object]) -> None:
    write_state(path, state)
    add = run(["git", "add", str(path)])
    if add.returncode != 0:
        raise OrchestratorError("Cannot stage lifecycle state")
    commit = run(["git", "commit", "-m", "chore: advance stage lifecycle state"])
    if commit.returncode != 0:
        raise OrchestratorError("Cannot commit lifecycle state")
    push = run(["git", "push", "origin", "HEAD:main"])
    if push.returncode != 0:
        raise OrchestratorError("Cannot publish lifecycle state")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, default=Path("factory/stage_state.json"))
    parser.add_argument("--stage", default="", help="Override current stage")
    args = parser.parse_args()

    state = load_state(args.state_file)
    current_number = int(args.stage) if args.stage else state["current_stage"]
    if not isinstance(current_number, int):
        raise OrchestratorError("Orchestrator stage must be an integer")

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
                print(f"NEXT_STAGE={state['current_stage']}")
                print("ORCHESTRATOR_RESULT=ADVANCED")
            return 0

        print("SMOKE_FAILURE_LOG_START")
        print(capture_failure(run_id))
        print("SMOKE_FAILURE_LOG_END")
        state["last_result"] = "FAIL"
        state["failed_stage"] = current.number
        write_state(args.state_file, state)
        if attempt == MAX_ATTEMPTS or not auto_repair():
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
