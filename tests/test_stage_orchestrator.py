import json
from pathlib import Path

from factory.stage_orchestrator import load_state, write_state


def test_missing_state_uses_current_stage_six(tmp_path: Path) -> None:
    state = load_state(tmp_path / "missing.json")
    assert state["current_stage"] == 6
    assert state["last_completed_stage"] == 5
    assert state["status"] == "READY"


def test_state_round_trip_is_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    expected = {"current_stage": 7, "last_completed_stage": 6, "status": "READY"}
    write_state(path, expected)
    assert json.loads(path.read_text(encoding="utf-8")) == expected
    assert load_state(path) == expected


def test_completed_terminal_state_is_valid(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    expected = {
        "current_stage": 16,
        "last_completed_stage": 16,
        "last_result": "PASS",
        "status": "COMPLETE",
    }
    write_state(path, expected)
    assert load_state(path) == expected


def test_state_rejects_inconsistent_stage_order(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        '{"current_stage": 6, "last_completed_stage": 6, "status": "READY"}\n',
        encoding="utf-8",
    )
    try:
        load_state(path)
    except RuntimeError as exc:
        assert "terminal status" in str(exc)
    else:
        raise AssertionError("invalid lifecycle state was accepted")


def test_pr_orchestrator_check_is_read_only_and_main_keeps_write_authority() -> None:
    workflow = Path(".github/workflows/stage-orchestrator.yml").read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "orchestrate:" in workflow
    assert "if: github.event_name == 'pull_request'" in workflow
    assert "contents: read" in workflow
    assert "actions: read" in workflow
    assert "Validate orchestrator contract without lifecycle mutation" in workflow
    assert "orchestrate-main:" in workflow
    assert "if: github.event_name != 'pull_request'" in workflow
    assert "contents: write" in workflow
    assert "actions: write" in workflow
    assert "Execute autonomous lifecycle controller" in workflow
