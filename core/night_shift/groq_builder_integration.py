"""Opt-in builder composition using the existing Night Shift process bridge.

The host supplies a separately approved launch plan and trusted admission
checker. This module does not register an executor or promote any adapter.
"""

from __future__ import annotations

import hashlib
import os
import stat
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .child_process_bridge import ChildLaunchPlan, ChildProcessBridge
from .contracts import NightShiftContractError
from .groq_builder_scope import ApprovedBuilderScope, verify_builder_changes
from .groq_local_broker import GroqBrokerPolicy, GroqLocalBroker, read_groq_key
from .journal import DurableEventJournal
from .leases import LeaseStore


@dataclass(frozen=True, slots=True)
class BrokeredBuilderReceipt:
    task_id: str
    process_pid: int
    plan_digest: str
    modified_file_digests: dict[str, str]
    broker_attempts: int
    broker_response_bytes: int


# Only the following known, pinned Bubblewrap topology may run an agent.
# The worktree itself is writable, but the linked Git metadata locator is
# overmounted with a read-only device and its external gitdir is never mounted.
# No consumer-defined mount, bind, symlink creation or later option may undo it.
_BWRAP_WORKSPACE = "/workspace"
_BWRAP_PREFIX = (
    "--unshare-all", "--unshare-net", "--unshare-pid", "--die-with-parent",
    "--new-session", "--clearenv", "--cap-drop", "ALL",
    "--ro-bind", "/usr", "/usr", "--ro-bind", "/bin", "/bin",
    "--ro-bind", "/lib", "/lib", "--ro-bind", "/lib64", "/lib64",
    "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
)


def _required_isolated_bwrap_prefix(scope: ApprovedBuilderScope) -> tuple[str, ...]:
    """Produce the only accepted worker mount layout, not a free-form CLI."""
    root = scope.worktree.resolve(strict=True)
    marker = root / ".git"
    # Linked Git worktree marker must be a regular file; bare/directory-based
    # repos need a different operator-approved proof, never an implicit bypass.
    if os.name != "posix" or os.uname().sysname != "Linux":
        raise NightShiftContractError("Linux mount namespace required for builder")
    try:
        fd = os.open(marker, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_size > 512):
                raise NightShiftContractError("linked Git worktree metadata marker required")
            raw = os.read(fd, 513)
        finally:
            os.close(fd)
        locator = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise NightShiftContractError("unreadable linked Git metadata marker") from exc
    if len(raw) > 512 or not locator.startswith("gitdir: "):
        raise NightShiftContractError("invalid linked Git metadata marker")
    locator_path = Path(locator.removeprefix("gitdir: ").strip())
    gitdir = (locator_path if locator_path.is_absolute()
              else root / locator_path).resolve(strict=True)
    if not gitdir.is_dir() or gitdir == root or gitdir.is_relative_to(root):
        raise NightShiftContractError("Git metadata must reside outside worker mount")
    # The bounded, read-only system mounts may never expose an operator
    # repository or its common-dir metadata by another absolute path.
    for exposed in (Path("/usr"), Path("/bin"), Path("/lib"), Path("/lib64")):
        mounted = exposed.resolve()
        if root.is_relative_to(mounted) or gitdir.is_relative_to(mounted):
            raise NightShiftContractError("Git metadata aliases a read-only host mount")
    return (
        *_BWRAP_PREFIX,
        "--bind", str(root), _BWRAP_WORKSPACE,
        # The worktree's .git file is mounted as /dev/null, not its host file.
        # Parent repository common-dir remains outside this namespace.
        "--ro-bind", "/dev/null", _BWRAP_WORKSPACE + "/.git",
        "--chdir", _BWRAP_WORKSPACE,
        "--",
    )


def _require_kernel_git_boundary(plan: ChildLaunchPlan, scope: ApprovedBuilderScope) -> None:
    """Reject all alternate mount grammars before reading the provider key."""
    expected = _required_isolated_bwrap_prefix(scope)
    args = plan.arguments
    # A command must follow '--'. Any extra bwrap flag, even an innocuous
    # looking bind later in the argv, is not accepted by the immutable profile.
    if (len(args) <= len(expected) or args[:len(expected)] != expected
            or not args[len(expected)].startswith("/")
            or any("\x00" in str(arg) for arg in args)):
        raise NightShiftContractError("unapproved Bubblewrap Git metadata mount layout")



def run_scoped_builder(
    *,
    leases: LeaseStore,
    journal: DurableEventJournal,
    plan: ChildLaunchPlan,
    scope: ApprovedBuilderScope,
    broker_policy: GroqBrokerPolicy,
    auth_file: Path,
    broker_socket: Path,
    pinned_launch_arguments_sha256: str,
    trusted_admission_checker: Callable[[ChildLaunchPlan], bool],
) -> BrokeredBuilderReceipt:
    """Run exactly one host-approved builder; never commit/push/merge its output.

    The caller is an authenticated local host authority, not an agent/model.
    Its separately approved plan, executable pin, repository identity and
    egress policy must be established *before* invoking this entrypoint.
    """
    if trusted_admission_checker is None:
        raise NightShiftContractError("trusted host admission is required")
    if (plan.role != "BUILDER" or plan.task_id != scope.task_id
            or plan.task_id != broker_policy.task_id
            or plan.worktree != scope.worktree or plan.base_sha != scope.base_sha):
        raise NightShiftContractError("builder plan is not bound to approved scope")
    if plan.executable.name != "bwrap":
        raise NightShiftContractError("builder must launch pinned bubblewrap")
    digest = hashlib.sha256("\0".join(plan.arguments).encode()).hexdigest()
    if digest != pinned_launch_arguments_sha256:
        raise NightShiftContractError("worker argv differs from host-approved immutable plan")
    # The capability must be dropped by a single, adjacent flag/value pair.
    # Later --cap-add/--share-net would override the intended confinement.
    argv = plan.arguments
    cap_drop_all = sum(
        flag == "--cap-drop" and value == "ALL"
        for flag, value in zip(argv, argv[1:])
    ) == 1
    if ("--unshare-net" not in argv or "--unshare-pid" not in argv
            or "--clearenv" not in argv or not cap_drop_all
            or argv.count("--cap-drop") != 1 or "--cap-add" in argv
            or "--share-net" in argv):
        raise NightShiftContractError("mandatory namespace controls missing")
    if not broker_socket.is_absolute():
        raise NightShiftContractError("broker socket must have exact absolute path")
    _require_kernel_git_boundary(plan, scope)
    # Credential loaded after all no-secret admission checks. Never add to
    # subprocess argv/env or include it in a receipt, journal or exception.
    credential = read_groq_key(auth_file)
    with GroqLocalBroker(socket_path=broker_socket, policy=broker_policy,
                         api_key=credential) as broker:
        bridge = ChildProcessBridge(
            leases=leases, journal=journal,
            admission_checker=trusted_admission_checker,
        )
        result = bridge.execute(plan)
        # A zero child exit is required but is never proof of task acceptance.
        if result.status != "EXITED_ZERO" or result.exit_code != 0:
            raise NightShiftContractError("builder child did not exit successfully")
        evidence = broker.evidence
        if (evidence.denied or evidence.client_disconnected or evidence.response_overflow
                or not 1 <= evidence.attempts <= broker_policy.max_requests
                or len(evidence.upstream_statuses) != evidence.attempts
                or any(status != 200 for status in evidence.upstream_statuses)
                or evidence.response_bytes == 0):
            raise NightShiftContractError("builder provider budget/evidence incomplete")
        changed = verify_builder_changes(scope)
    # A scoped file result is not code correctness, review, or authority.
    # Close the lease-loss window between child exit and artifact inspection.
    claimed = leases.require_current(
        task_id=plan.task_id, lease_id=plan.lease_id,
        fencing_token=plan.fencing_token, now_epoch=int(time.time()),
    )
    if claimed.worker_id != plan.worker_id:
        raise NightShiftContractError("builder lease owner changed before receipt")

    receipt = BrokeredBuilderReceipt(
        task_id=plan.task_id, process_pid=result.pid, plan_digest=result.plan_digest,
        modified_file_digests=changed, broker_attempts=evidence.attempts,
        broker_response_bytes=evidence.response_bytes,
    )
    # Reuse the bridge's existing append-only hash-chained journal. A crash
    # after this insert can be reconciled from the receipt without rerunning
    # the builder; failed/duplicate persistence never returns success.
    if not journal.append_event(
        event_id=f"child-bridge:{plan.task_id}:scope-receipt",
        workflow_id=f"child-bridge:{plan.task_id}",
        event_type="BUILDER_SCOPE_RECEIPT",
        payload={
            "schema_version": "night-shift-builder-scope-receipt/v1",
            "task_id": receipt.task_id,
            "role": "BUILDER",
            "lease_id": claimed.lease_id,
            "fencing_token": claimed.fencing_token,
            "pid": receipt.process_pid,
            "plan_digest": receipt.plan_digest,
            "modified_file_digests": dict(sorted(receipt.modified_file_digests.items())),
            "broker_attempts": receipt.broker_attempts,
            "broker_response_bytes": receipt.broker_response_bytes,
            "acceptance": "SCOPE_ONLY_NOT_CODE_REVIEW",
        },
        created_at_epoch=int(time.time()),
    ):
        raise NightShiftContractError("builder receipt already recorded; reconcile first")
    # Lease ownership can change during the journal transaction. A persisted
    # receipt then needs reconciliation; never return success to a stale owner.
    claimed = leases.require_current(
        task_id=plan.task_id, lease_id=plan.lease_id,
        fencing_token=plan.fencing_token, now_epoch=int(time.time()),
    )
    if claimed.worker_id != plan.worker_id:
        raise NightShiftContractError("builder lease owner changed after receipt")
    return receipt
