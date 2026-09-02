"""Stateful orchestrator for the LukArt ROS Factory lifecycle."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from factory.stage_registry import get_stage, next_stage

DEFAULT_STATE = {
    "current_stage": 6,
    "last_completed_stage": 5,
    "status": "READY",
}


class OrchestratorError(RuntimeError):
    """Raised when lifecycle state is invalid."""


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
    path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_gate(stage_number: int) -> int:
    command = ["python", "-m", "factory.stage_gate", "--stage", str(stage_number)]
    print(f"[orchestrator] {' '.join(command)}")
    completed = subprocess.run(command, check=False)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path("factory/stage_state.json"),
    )
    args = parser.parse_args()

    state = load_state(args.state_file)
    current_number = int(state["current_stage"])
    current = get_stage(current_number)

    print(f"CURRENT_STAGE={current.number}")
    print(f"CURRENT_STAGE_NAME={current.name}")

    if not current.implemented or current.gate not in __import__(
        "factory.stage_gate", fromlist=["COMMANDS"]
    ).COMMANDS:
        state["status"] = "BLOCKED"
        state["block_reason"] = "gate_not_implemented"
        write_state(args.state_file, state)
        print(f"STAGE {current.number}: BLOCKED")
        print("ORCHESTRATOR_RESULT=BLOCKED")
        return 0

    return_code = run_gate(current.number)
    if return_code != 0:
        state["status"] = "FAILED"
        state["failed_stage"] = current.number
        write_state(args.state_file, state)
        print(f"STAGE {current.number}: FAIL")
        print("ORCHESTRATOR_RESULT=FAIL")
        return 1

    following = next_stage(current.number)
    state["last_completed_stage"] = current.number
    state["last_result"] = "PASS"
    if following is None:
        state["current_stage"] = current.number
        state["status"] = "COMPLETE"
        state.pop("block_reason", None)
        print(f"STAGE {current.number}: PASS")
        print("ORCHESTRATOR_RESULT=COMPLETE")
        write_state(args.state_file, state)
        return 0

    state["current_stage"] = following.number
    state["status"] = "READY"
    state.pop("block_reason", None)
    state.pop("failed_stage", None)
    write_state(args.state_file, state)
    print(f"STAGE {current.number}: PASS")
    print(f"NEXT_STAGE={following.number}")
    print(f"NEXT_STAGE_NAME={following.name}")
    print("ORCHESTRATOR_RESULT=ADVANCED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
