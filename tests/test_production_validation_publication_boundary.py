from __future__ import annotations

import inspect
from types import SimpleNamespace

from factory import production_validation_orchestrator as orchestrator


def test_publish_changes_never_performs_remote_git_write(monkeypatch) -> None:
    commands: list[list[str]] = []

    monkeypatch.setattr(orchestrator, "_git_changed", lambda: True)

    def capture_run(command: list[str], *, check: bool = False, **_: object) -> SimpleNamespace:
        commands.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(orchestrator.subprocess, "run", capture_run)

    orchestrator.publish_changes()

    assert commands
    assert [command[:2] for command in commands] == [["git", "add"], ["git", "commit"]]
    assert all(command[:2] != ["git", "push"] for command in commands)


def test_orchestrator_contains_no_direct_push_to_main_contract() -> None:
    source = inspect.getsource(orchestrator)

    assert "HEAD:main" not in source
    assert '["git", "push"' not in source
