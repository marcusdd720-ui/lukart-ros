"""Mutation-scope enforcement for Proof-Carrying Task Capsules."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import PurePosixPath

from .contracts import NightShiftContractError, TaskCapsule


@dataclass(frozen=True, slots=True)
class ChangedFile:
    path: str
    additions: int
    deletions: int
    binary: bool = False

    def __post_init__(self) -> None:
        normalized = self.path.replace("\\", "/").strip()
        pure = PurePosixPath(normalized)
        if (
            not normalized
            or pure.is_absolute()
            or ".." in pure.parts
            or normalized.startswith("/")
        ):
            raise NightShiftContractError("changed path must be safe and repository-relative")
        if self.additions < 0 or self.deletions < 0:
            raise NightShiftContractError("line counts cannot be negative")
        object.__setattr__(self, "path", pure.as_posix())


@dataclass(frozen=True, slots=True)
class ScopeValidation:
    changed_files: int
    changed_lines: int


def validate_mutation_scope(
    *,
    task: TaskCapsule,
    changes: tuple[ChangedFile, ...],
) -> ScopeValidation:
    seen: set[str] = set()
    total_lines = 0

    for change in changes:
        if change.path in seen:
            raise NightShiftContractError("duplicate changed path in scope evidence")
        seen.add(change.path)

        if change.binary and not task.allow_binary_changes:
            raise NightShiftContractError("binary change is outside task authority")

        if any(fnmatchcase(change.path, pattern) for pattern in task.forbidden_paths):
            raise NightShiftContractError("changed path matches forbidden task scope")

        if not any(fnmatchcase(change.path, pattern) for pattern in task.allowed_paths):
            raise NightShiftContractError("changed path is outside allowed task scope")

        total_lines += change.additions + change.deletions

    if len(changes) > task.max_files_changed:
        raise NightShiftContractError("changed file count exceeds task mutation budget")
    if total_lines > task.max_lines_changed:
        raise NightShiftContractError("changed line count exceeds task mutation budget")

    return ScopeValidation(changed_files=len(changes), changed_lines=total_lines)
