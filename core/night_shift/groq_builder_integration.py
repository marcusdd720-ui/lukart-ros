"""Opt-in builder composition using the existing Night Shift process bridge.

The host supplies a separately approved launch plan and trusted admission
checker. This module does not register an executor or promote any adapter.
"""

from __future__ import annotations

import hashlib
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
