import sys
from types import SimpleNamespace

import factory.stage_gate as stage_gate


def test_nonzero_command_result_cannot_be_reported_as_pass(monkeypatch, capsys) -> None:
    synthetic_stage = SimpleNamespace(
        number=999,
        name="CASE-TESTY synthetic gate",
        gate="case-test",
    )
    monkeypatch.setattr(stage_gate, "get_stage", lambda number: synthetic_stage)
    monkeypatch.setattr(stage_gate, "next_stage", lambda number: None)
    monkeypatch.setitem(
        stage_gate.COMMANDS,
        "case-test",
        ("synthetic-pass", "synthetic-fail", "never-run"),
    )

    seen: list[str] = []

    def fake_run(command: str) -> int:
        seen.append(command)
        return 9 if command == "synthetic-fail" else 0

    monkeypatch.setattr(stage_gate, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["stage_gate", "--stage", "999"])

    result = stage_gate.main()
    output = capsys.readouterr().out

    assert result == 1
    assert "STAGE 999: FAIL" in output
    assert "STAGE 999: PASS" not in output
    assert seen == ["synthetic-pass", "synthetic-fail"]


def test_unimplemented_gate_fails_closed(monkeypatch, capsys) -> None:
    synthetic_stage = SimpleNamespace(
        number=998,
        name="CASE-TESTY unknown gate",
        gate="missing-gate",
    )
    monkeypatch.setattr(stage_gate, "get_stage", lambda number: synthetic_stage)
    monkeypatch.delitem(stage_gate.COMMANDS, "missing-gate", raising=False)
    monkeypatch.setattr(sys, "argv", ["stage_gate", "--stage", "998"])

    result = stage_gate.main()
    output = capsys.readouterr().out

    assert result == 2
    assert "Gate: NOT IMPLEMENTED" in output
    assert "PASS" not in output
