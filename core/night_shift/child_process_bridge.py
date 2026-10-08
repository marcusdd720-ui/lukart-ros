"""Fenced POSIX child-process bridge for the existing Night Shift control plane.

Not a dispatcher, provider certification, or production adapter admission.
The trusted integration host owns authorization, cost/privacy admission and
independent-review sandbox evidence. Cached task metadata is never authority.
"""

from __future__ import annotations

import hashlib
import os
import re
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.p3.contracts import content_digest

from .contracts import NightShiftContractError, require_git_oid
from .journal import DurableEventJournal
from .leases import LeaseStore

_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_ROLES = frozenset({"BUILDER", "REVIEWER"})


@dataclass(frozen=True, slots=True)
class ChildLaunchPlan:
    """Trusted-host configuration; never construct from task/model content."""

    task_id: str
    worker_id: str
    lease_id: str
    fencing_token: int
    role: str
    executable: Path
    executable_sha256: str
    arguments: tuple[str, ...]
    worktree: Path
    base_sha: str
    progress_name: str = ".night-shift-progress"
    timeout_seconds: float = 120.0
    heartbeat_seconds: float = 1.0
    lease_ttl_seconds: int = 30
    no_progress_seconds: float = 60.0

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (self.task_id, self.worker_id, self.lease_id)
        ):
            raise NightShiftContractError("child launch requires exact task identity")
        if self.role not in _ROLES or type(self.fencing_token) is not int:
            raise NightShiftContractError("invalid child role or fencing token")
        if self.fencing_token < 1:
            raise NightShiftContractError("fencing token must be positive")
        if not _HEX64.fullmatch(self.executable_sha256):
            raise NightShiftContractError("executable SHA-256 required")
        require_git_oid(self.base_sha, field_name="base_sha")
        if not isinstance(self.arguments, tuple) or any(
            not isinstance(arg, str) or "\x00" in arg for arg in self.arguments
        ):
            raise NightShiftContractError("invalid child argument vector")
        if (
            not isinstance(self.progress_name, str)
            or self.progress_name in {"", ".", ".."}
            or "/" in self.progress_name
            or "\\" in self.progress_name
        ):
            raise NightShiftContractError("progress marker must be a local basename")
        if (
            not 0 < self.heartbeat_seconds <= 10
            or not self.heartbeat_seconds < self.lease_ttl_seconds
            or not 0 < self.no_progress_seconds <= self.timeout_seconds
            or not 0 < self.timeout_seconds <= 3600
        ):
            raise NightShiftContractError("invalid bounded execution limits")

    def digest(self) -> str:
        return content_digest(
            {
                "task_id": self.task_id,
                "worker_id": self.worker_id,
                "lease_id": self.lease_id,
                "fencing_token": self.fencing_token,
                "role": self.role,
                "executable_sha256": self.executable_sha256,
                "arguments_sha256": hashlib.sha256(
                    "\0".join(self.arguments).encode("utf-8")
                ).hexdigest(),
                "worktree": str(self.worktree),
                "base_sha": self.base_sha,
                "timeout_seconds": self.timeout_seconds,
                "no_progress_seconds": self.no_progress_seconds,
            }
        )


@dataclass(frozen=True, slots=True)
class ChildExitEvidence:
    task_id: str
    role: str
    pid: int
    exit_code: int
    plan_digest: str
    progress_digest: str | None
    status: str


class ChildProcessBridge:
    """Start one subprocess per task ID under existing leases and journal.

    A trusted host MUST pass an admission checker that independently verifies
    current task authority, verified-zero-cost provider eligibility, egress
    policy, and role. A reviewer additionally requires a separate isolation
    checker; callbacks are not satisfied by model/user-supplied declarations.
    No implementation is registered as VALIDATED by this module.
    """

    def __init__(
        self,
        *,
        leases: LeaseStore,
        journal: DurableEventJournal,
        admission_checker: Callable[[ChildLaunchPlan], bool] | None = None,
        reviewer_isolation_checker: Callable[[ChildLaunchPlan], bool] | None = None,
    ) -> None:
        self.leases = leases
        self.journal = journal
        self.admission_checker = admission_checker
        self.reviewer_isolation_checker = reviewer_isolation_checker

    @staticmethod
    def _require_task_worktree(path: Path, expected_sha: str) -> None:
        """Never launch against main, detached HEAD, or a dirty shared worktree."""
        try:
            def git(*args: str) -> str:
                return subprocess.run(
                    ["git", "-C", str(path), *args],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5,
                ).stdout.strip()

            head = git("rev-parse", "HEAD")
            root = git("rev-parse", "--show-toplevel")
            branch = git("symbolic-ref", "--quiet", "--short", "HEAD")
            status = git("status", "--porcelain", "--untracked-files=all")
        except (OSError, subprocess.SubprocessError) as exc:
            raise NightShiftContractError("task worktree cannot be verified") from exc
        if Path(root).resolve() != path or not branch.startswith("night-shift/"):
            raise NightShiftContractError("dedicated night-shift worktree required")
        if head != expected_sha:
            raise NightShiftContractError("worktree SHA drift")
        if status:
            raise NightShiftContractError("task worktree is not clean")

    @staticmethod
    def _hash_executable(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(128 * 1024), b""):
                h.update(block)
        return h.hexdigest()

    @staticmethod
    def _progress(path: Path) -> str | None:
        if not path.exists():
            return None
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 131072:
            raise NightShiftContractError("invalid progress evidence file")
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _kill_group(child: subprocess.Popen[bytes]) -> None:
        # The leader may have exited while descendants remain in its session.
        # Do not interpret leader exit as proof that the entire group stopped.
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait(timeout=5)

    def execute(self, plan: ChildLaunchPlan) -> ChildExitEvidence:
        if os.name != "posix":
            raise NightShiftContractError("WSL/Linux POSIX runner required")
        if self.admission_checker is None or self.admission_checker(plan) is not True:
            raise NightShiftContractError("trusted execution admission required")
        if plan.role == "REVIEWER" and (
            self.reviewer_isolation_checker is None
            or self.reviewer_isolation_checker(plan) is not True
        ):
            raise NightShiftContractError(
                "independent review isolation is not attested"
            )

        executable = plan.executable.resolve(strict=True)
        worktree = plan.worktree.resolve(strict=True)
        if not executable.is_file() or not worktree.is_dir():
            raise NightShiftContractError("invalid child executable/worktree")
        if self._hash_executable(executable) != plan.executable_sha256:
            raise NightShiftContractError("executable identity mismatch")
        if any(
            item.event_type == "CHILD_LAUNCH_INTENT"
            for item in self.journal.events(workflow_id=f"child-bridge:{plan.task_id}")
        ):
            raise NightShiftContractError("launch already recorded; reconcile first")
        self._require_task_worktree(worktree, plan.base_sha)

        progress_path = worktree / plan.progress_name
        if progress_path.exists() or progress_path.is_symlink():
            raise NightShiftContractError("old progress marker must be reconciled")

        now = int(time.time())
        self.leases.require_current(
            task_id=plan.task_id,
            lease_id=plan.lease_id,
            fencing_token=plan.fencing_token,
            now_epoch=now,
        )
        # One immutable intent blocks blind restart after crash, timeout, or
        # ambiguous exit. Recovery requires an external reconciliation decision.
        event_id = f"child-bridge:{plan.task_id}:intent"
        inserted = self.journal.append_event(
            event_id=event_id,
            workflow_id=f"child-bridge:{plan.task_id}",
            event_type="CHILD_LAUNCH_INTENT",
            payload={"plan_digest": plan.digest(), "role": plan.role},
            created_at_epoch=now,
        )
        if not inserted:
            raise NightShiftContractError("launch already recorded; reconcile first")

        # Close the lease-loss race across intent persistence and POSIX spawn.
        # An intent with a lost lease stays blocked for explicit reconciliation.
        self.leases.require_current(
            task_id=plan.task_id,
            lease_id=plan.lease_id,
            fencing_token=plan.fencing_token,
            now_epoch=int(time.time()),
        )

        child: subprocess.Popen[bytes] | None = None
        last_progress: str | None = None
        last_progress_at = time.monotonic()
        started_at = last_progress_at
        last_beat_at = started_at
        sequence = 0

        def record(event_type: str, payload: dict[str, object]) -> None:
            nonlocal sequence
            sequence += 1
            self.journal.append_event(
                event_id=f"child-bridge:{plan.task_id}:{sequence}",
                workflow_id=f"child-bridge:{plan.task_id}",
                event_type=event_type,
                payload=payload,
                created_at_epoch=int(time.time()),
            )

        try:
            child = subprocess.Popen(
                [str(executable), *plan.arguments],
                cwd=worktree,
                env={"PATH": os.defpath, "LANG": "C.UTF-8"},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                start_new_session=True,
            )
            record("CHILD_STARTED", {
                "pid": child.pid,
                "plan_digest": plan.digest(),
                "binary_sha256": plan.executable_sha256,
            })
            while child.poll() is None:
                time.sleep(min(plan.heartbeat_seconds, 0.25))
                elapsed = time.monotonic() - started_at
                if elapsed >= plan.timeout_seconds:
                    raise NightShiftContractError("child execution timeout")
                progress = self._progress(progress_path)
                if progress is not None and progress != last_progress:
                    last_progress = progress
                    last_progress_at = time.monotonic()
                    record("CHILD_PROGRESS", {"sha256": progress})
                if time.monotonic() - last_progress_at >= plan.no_progress_seconds:
                    raise NightShiftContractError("child without meaningful progress")
                if time.monotonic() - last_beat_at >= plan.heartbeat_seconds:
                    self.leases.heartbeat(
                        task_id=plan.task_id,
                        lease_id=plan.lease_id,
                        fencing_token=plan.fencing_token,
                        now_epoch=int(time.time()),
                        ttl_seconds=plan.lease_ttl_seconds,
                    )
                    last_beat_at = time.monotonic()

            # Reap any remaining same-session descendants. An exit code alone
            # cannot attest independent, kernel-enforced process isolation.
            self._kill_group(child)
            # Completion is NOT test PASS, review approval, or promotion.
            self.leases.require_current(
                task_id=plan.task_id,
                lease_id=plan.lease_id,
                fencing_token=plan.fencing_token,
                now_epoch=int(time.time()),
            )
            evidence = ChildExitEvidence(
                task_id=plan.task_id,
                role=plan.role,
                pid=child.pid,
                exit_code=child.returncode,
                plan_digest=plan.digest(),
                progress_digest=last_progress,
                status="EXITED_ZERO" if child.returncode == 0 else "EXITED_NONZERO",
            )
            record("CHILD_EXIT", {
                "pid": child.pid,
                "exit_code": child.returncode,
                "status": evidence.status,
                "plan_digest": evidence.plan_digest,
                "progress_digest": last_progress,
            })
            return evidence
        except BaseException:
            if child is not None:
                self._kill_group(child)
            try:
                record("CHILD_ABORTED", {
                    "pid": child.pid if child is not None else None,
                    "plan_digest": plan.digest(),
                    "result": "RECONCILIATION_REQUIRED",
                })
            except Exception:
                pass
            raise
