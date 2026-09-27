"""Isolated git worktree lifecycle for Night Shift workers."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .contracts import NightShiftContractError


@dataclass(frozen=True, slots=True)
class WorktreeHandle:
    task_id: str
    path: Path
    branch: str
    base_sha: str


class WorktreeManager:
    """Create and remove task-scoped worktrees without touching the operator worktree."""

    def __init__(self, *, repository: str | Path, root: str | Path) -> None:
        self.repository = Path(repository).resolve()
        self.root = Path(root).resolve()
        if self.repository == self.root:
            raise NightShiftContractError("worktree root cannot equal repository path")
        self.root.mkdir(parents=True, exist_ok=True)
        self._require_git_repository()
    def _git(self, *args: str, cwd: Path | None = None) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd or self.repository,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if completed.returncode != 0:
            message = completed.stdout.strip() or "git command failed"
            raise NightShiftContractError(message)
        return completed.stdout.strip()

    def _require_git_repository(self) -> None:
        root = self._git("rev-parse", "--show-toplevel")
        if Path(root).resolve() != self.repository:
            raise NightShiftContractError("repository must be an exact git worktree root")

    @staticmethod
    def _segment(value: str, *, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise NightShiftContractError(f"{field_name} is required")
        if any(part in normalized for part in ("..", "/", "\\", ":")):
            raise NightShiftContractError(f"{field_name} contains unsafe path characters")
        return normalized
    def create(
        self,
        *,
        task_id: str,
        branch: str,
        base_ref: str,
    ) -> WorktreeHandle:
        task_segment = self._segment(task_id, field_name="task_id")
        branch = branch.strip()
        base_ref = base_ref.strip()
        if not branch or not base_ref:
            raise NightShiftContractError("branch and base_ref are required")
        if not branch.startswith("night-shift/"):
            raise NightShiftContractError("night worktree branch must use night-shift/ prefix")

        target = (self.root / task_segment).resolve()
        if target.parent != self.root:
            raise NightShiftContractError("task worktree escaped configured root")
        if target.exists():
            raise NightShiftContractError("task worktree path already exists")

        base_sha = self._git("rev-parse", f"{base_ref}^{{commit}}")
        self._git("worktree", "add", "-b", branch, str(target), base_sha)
        head_sha = self._git("rev-parse", "HEAD", cwd=target)
        if head_sha != base_sha:
            self.remove(path=target, force=True)
            raise NightShiftContractError("worktree HEAD does not match requested base")
        return WorktreeHandle(
            task_id=task_segment,
            path=target,
            branch=branch,
            base_sha=base_sha,
        )

    def require_clean(self, *, handle: WorktreeHandle) -> None:
        self._require_managed_path(handle.path)
        status = self._git("status", "--porcelain", cwd=handle.path)
        if status:
            raise NightShiftContractError("task worktree is dirty")

    def remove(self, *, path: str | Path, force: bool = False) -> None:
        target = Path(path).resolve()
        self._require_managed_path(target)
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(target))
        self._git(*args)

    def _require_managed_path(self, target: Path) -> None:
        resolved = target.resolve()
        if resolved == self.repository:
            raise NightShiftContractError("operator worktree cannot be managed by Night Shift")
        if resolved.parent != self.root:
            raise NightShiftContractError("path is outside configured Night Shift root")

    def list_managed_paths(self) -> tuple[Path, ...]:
        output = self._git("worktree", "list", "--porcelain")
        paths: list[Path] = []
        for line in output.splitlines():
            if not line.startswith("worktree "):
                continue
            path = Path(line.removeprefix("worktree ")).resolve()
            if path.parent == self.root:
                paths.append(path)
        return tuple(sorted(paths, key=lambda item: str(item)))
