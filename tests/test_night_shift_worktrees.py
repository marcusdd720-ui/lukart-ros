from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.worktrees import WorktreeManager


def _run(*args: str, cwd: Path) -> str:
    completed = subprocess.run(
        list(args),
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run("git", "init", "-b", "main", cwd=repo)
    _run("git", "config", "user.email", "night-shift@example.test", cwd=repo)
    _run("git", "config", "user.name", "Night Shift Test", cwd=repo)
    _run("git", "config", "commit.gpgsign", "false", cwd=repo)
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    _run("git", "add", "README.md", cwd=repo)
    _run("git", "commit", "-m", "baseline", cwd=repo)
    return repo
def test_create_worktree_is_isolated_from_operator_tree(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    root = tmp_path / "night-worktrees"
    manager = WorktreeManager(repository=repo, root=root)

    operator_head = _run("git", "rev-parse", "HEAD", cwd=repo)
    handle = manager.create(
        task_id="task-001",
        branch="night-shift/task-001",
        base_ref=operator_head,
    )

    assert handle.path != repo
    assert handle.path.parent == root
    assert _run("git", "rev-parse", "HEAD", cwd=handle.path) == operator_head
    assert _run("git", "status", "--porcelain", cwd=repo) == ""
    assert manager.list_managed_paths() == (handle.path,)

    manager.remove(path=handle.path)
    assert not handle.path.exists()
def test_dirty_task_worktree_fails_clean_gate(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    manager = WorktreeManager(repository=repo, root=tmp_path / "night-worktrees")
    handle = manager.create(
        task_id="task-001",
        branch="night-shift/task-001",
        base_ref="HEAD",
    )
    (handle.path / "README.md").write_text("changed\n", encoding="utf-8")

    with pytest.raises(NightShiftContractError, match="worktree is dirty"):
        manager.require_clean(handle=handle)

    manager.remove(path=handle.path, force=True)


def test_operator_worktree_cannot_be_removed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    manager = WorktreeManager(repository=repo, root=tmp_path / "night-worktrees")

    with pytest.raises(NightShiftContractError, match="operator worktree"):
        manager.remove(path=repo, force=True)
def test_unsafe_task_identifier_is_rejected(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    manager = WorktreeManager(repository=repo, root=tmp_path / "night-worktrees")

    with pytest.raises(NightShiftContractError, match="unsafe path characters"):
        manager.create(
            task_id="../escape",
            branch="night-shift/escape",
            base_ref="HEAD",
        )


def test_branch_requires_night_shift_namespace(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    manager = WorktreeManager(repository=repo, root=tmp_path / "night-worktrees")

    with pytest.raises(NightShiftContractError, match="night-shift/ prefix"):
        manager.create(
            task_id="task-001",
            branch="feature/task-001",
            base_ref="HEAD",
        )
