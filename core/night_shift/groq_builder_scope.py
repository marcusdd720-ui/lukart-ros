"""Post-execution file-scope gate for a Groq Night Shift BUILDER candidate.

This does not authorize the agent's launch, git commit, GitHub push, or review.
Trusted host must authorize an exact task before calling ChildProcessBridge.
"""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .contracts import NightShiftContractError, require_git_oid


@dataclass(frozen=True, slots=True)
class ApprovedBuilderScope:
    task_id: str
    worktree: Path
    branch: str
    base_sha: str
    allowed_files: tuple[str, ...]
    max_files: int = 6
    max_file_bytes: int = 65536

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.branch.startswith("night-shift/"):
            raise NightShiftContractError("explicit task ID and night-shift branch required")
        require_git_oid(self.base_sha, field_name="base_sha")
        if not 1 <= self.max_files <= 6 or not 1 <= self.max_file_bytes <= 65536:
            raise NightShiftContractError("builder file budgets exceed approved bounds")
        if not self.allowed_files or len(set(self.allowed_files)) != len(self.allowed_files):
            raise NightShiftContractError("exact allowed file list required")
        if len(self.allowed_files) > self.max_files:
            raise NightShiftContractError("file allowlist exceeds budget")
        for filename in self.allowed_files:
            p = PurePosixPath(filename)
            if (not filename or p.is_absolute() or p.as_posix() != filename
                    or any(part in {".", "..", ".git"} for part in p.parts)
                    or "\\" in filename or p.parts[0].startswith(".")):
                raise NightShiftContractError("unsafe allowed file path")


def _git(worktree: Path, *args: str) -> str:
    command = ["git", "-c", "core.fsmonitor=false", "-c", f"core.hooksPath={os.devnull}",
               "-C", str(worktree), *args]
    try:
        output = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=8,
            env={"PATH": os.defpath, "LANG": "C.UTF-8",
                 "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
        ).stdout
        # NUL-delimited pathnames may themselves start/end with whitespace.
        # Stripping them would alias an unexpected filename to an allowed one.
        return output if "-z" in args else output.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise NightShiftContractError("git builder scope inspection failed") from exc


def verify_builder_changes(scope: ApprovedBuilderScope) -> dict[str, str]:
    """Return content hashes only for an exactly scoped, nonempty modification.

    Caller must never treat this as proof of code correctness or approval to
    publish. No generated code is executed here.
    """
    root = scope.worktree.resolve(strict=True)
    if _git(root, "rev-parse", "--show-toplevel") != str(root):
        raise NightShiftContractError("builder worktree root mismatch")
    if _git(root, "symbolic-ref", "--quiet", "--short", "HEAD") != scope.branch:
        raise NightShiftContractError("builder branch changed")
    if _git(root, "rev-parse", "HEAD") != scope.base_sha:
        raise NightShiftContractError("builder base SHA changed")
    # Path NUL-separated output rejects ambiguous whitespace, renames, and
    # untracked file names without executing repository-configured hooks.
    # Explicitly disable rename detection: a staged rename must expose both
    # the deleted source and new destination to the exact file allowlist.
    diff = _git(root, "diff", "--name-only", "--no-renames", "--no-ext-diff",
                "-z", "HEAD", "--")
    other = _git(root, "ls-files", "--others", "-z", "--")
    changed = set(filter(None, (diff + "\0" + other).split("\0")))
    if not changed or len(changed) > scope.max_files:
        raise NightShiftContractError("builder change count outside approved budget")
    if not changed <= set(scope.allowed_files):
        raise NightShiftContractError("builder modified an unapproved file")
    results = {}
    for filename in sorted(changed):
        target = root / filename
        try:
            info = target.lstat()
        except FileNotFoundError as exc:
            raise NightShiftContractError("builder deletion is not approved") from exc
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_size > scope.max_file_bytes):
            raise NightShiftContractError("unsafe modified file type or size")
        # Validate every directory component is a real directory, not a symlink.
        parent = target.parent
        while parent != root:
            if not stat.S_ISDIR(parent.lstat().st_mode):
                raise NightShiftContractError("builder path crosses a link")
            parent = parent.parent
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            check = os.fstat(fd)
            if (not stat.S_ISREG(check.st_mode) or check.st_ino != info.st_ino
                    or check.st_size > scope.max_file_bytes):
                raise NightShiftContractError("builder file raced inspection")
            chunks = []
            remaining = scope.max_file_bytes + 1
            while remaining > 0:
                part = os.read(fd, min(remaining, 16384))
                if not part:
                    break
                chunks.append(part)
                remaining -= len(part)
            data = b"".join(chunks)
            if len(data) > scope.max_file_bytes:
                raise NightShiftContractError("builder file exceeds size cap")
        finally:
            os.close(fd)
        results[filename] = hashlib.sha256(data).hexdigest()
    return results
