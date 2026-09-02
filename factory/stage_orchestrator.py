"""Autonomous lifecycle controller for the LukArt ROS Factory."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from factory.stage_gate import COMMANDS
from factory.stage_registry import STAGES, get_stage, next_stage

DEFAULT_STATE = {
    "current_stage": 6,
    "last_completed_stage": 5,
    "status": "READY",
}
MAX_STAGE = max(stage.number for stage in STAGES)


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
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_gate(stage_number: int) -> int:
    command = ["python", "-m", "factory.stage_gate", "--stage", str(stage_number)]
    print(f"[orchestrator] {' '.join(command)}")
    return subprocess.run(command, check=False).returncode


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
        print(f"NEXT_STAGE={following.number}")
        print(f"NEXT_STAGE_NAME={following.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, default=Path("factory/stage_state.json"))
    parser.add_argument("--stage", default="", help="Override current stage")
    args = parser.parse_args()

    state = load_state(args.state_file)
    if args.stage:
        try:
            current_number = int(args.stage)
        except ValueError as exc:
            raise OrchestratorError("--stage must be an integer") from exc
    else:
        current_value = state["current_stage"]
        if not isinstance(current_value, int):
            raise OrchestratorError("Orchestrator state current_stage must be an integer")
        current_number = current_value

    while current_number <= MAX_STAGE:
        current = get_stage(current_number)
        print(f"CURRENT_STAGE={current.number}")
        print(f"CURRENT_STAGE_NAME={current.name}")

        # A stage is only valid after its real gate exists and passes.
        if not current.implemented or current.gate not in COMMANDS:
            state["status"] = "BLOCKED"
            state["block_reason"] = "gate_not_implemented"
            state["failed_stage"] = current.number
            write_state(args.state_file, state)
            print(f"STAGE {current.number}: BLOCKED")
            print("ORCHESTRATOR_RESULT=BLOCKED")
            return 1

        return_code = run_gate(current.number)
        if return_code != 0:
            state["status"] = "FAILED"
            state["failed_stage"] = current.number
            state["last_result"] = "FAIL"
            write_state(args.state_file, state)
            print(f"STAGE {current.number}: FAIL")
            print("ORCHESTRATOR_RESULT=FAIL")
            return return_code

        print(f"STAGE {current.number}: PASS")
        advance_state(state, current.number)
        write_state(args.state_file, state)
        if state["status"] == "COMPLETE":
            print("ORCHESTRATOR_RESULT=COMPLETE")
            return 0
        current_number = int(state["current_stage"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
