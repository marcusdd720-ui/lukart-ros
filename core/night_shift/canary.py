"""Local-only controlled mutation canary for Night Shift."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.p3.contracts import content_digest

from .authority import AuthorityBudgetStore
from .contracts import (
    AutonomyEnvelope,
    LiveStateSnapshot,
    NightShiftContractError,
    PolicyRef,
    RiskClass,
    TaskCapsule,
    authorize_task,
)
from .failure_gate import FailureInjectionReport
from .leases import LeaseStore
from .promotion import PromotionState, VerificationQuorum, decide_promotion
from .receipts import ExecutionReceipt
from .scope import ChangedFile, validate_mutation_scope
from .worktrees import WorktreeManager


@dataclass(frozen=True, slots=True)
class ControlledCanaryResult:
    task_id: str
    input_sha: str
    output_sha: str
    promotion_state: PromotionState
    receipt_digest: str
    rollback_verified: bool
    published: bool = False


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise NightShiftContractError(completed.stderr.strip() or "git command failed")
    return completed.stdout.strip()


def _changed_files(worktree: Path) -> tuple[ChangedFile, ...]:
    output = _git(worktree, "diff", "--numstat", "--no-renames")
    changes: list[ChangedFile] = []
    for line in output.splitlines():
        additions, deletions, path = line.split("\t", 2)
        binary = additions == "-" or deletions == "-"
        changes.append(
            ChangedFile(
                path,
                0 if binary else int(additions),
                0 if binary else int(deletions),
                binary=binary,
            )
        )
    return tuple(changes)


def run_controlled_canary(
    *,
    repository: str | Path,
    worktree_root: str | Path,
    task: TaskCapsule,
    state: LiveStateSnapshot,
    policy: PolicyRef,
    envelope: AutonomyEnvelope,
    quorum: VerificationQuorum,
    failure_report: FailureInjectionReport,
    required_failure_scenarios: tuple[str, ...],
    target_path: str,
    replacement_text: str,
    now_epoch: int,
    lease_ttl_seconds: int = 300,
    mutation_writer: Callable[[Path, str], None] | None = None,
) -> ControlledCanaryResult:
    if task.risk_class not in {RiskClass.R0, RiskClass.R1}:
        raise NightShiftContractError("controlled canary is limited to R0/R1")
    if state.head_sha != state.base_sha:
        raise NightShiftContractError("controlled canary requires exact single-SHA baseline")
    failure_report.require_passed(required_scenarios=required_failure_scenarios)

    decision = decide_promotion(
        repository=task.repository,
        risk_class=task.risk_class,
        envelope=envelope,
        quorum=quorum,
        subject_sha=state.head_sha,
        task_capsule_digest=task.digest(),
        now_epoch=now_epoch,
    )
    if decision.state is not PromotionState.ELIGIBLE_AUTO:
        raise NightShiftContractError("controlled canary requires ELIGIBLE_AUTO")

    repo = Path(repository).resolve()
    root = Path(worktree_root).resolve()
    manager = WorktreeManager(repository=repo, root=root)
    operator_head = _git(repo, "rev-parse", "HEAD")

    authority = AuthorityBudgetStore(root / "authority.db")
    reservation = authority.reserve_task(
        envelope=envelope,
        task_id=task.task_id,
        now_epoch=now_epoch,
    )
    execution = authorize_task(
        policy=policy,
        state=state,
        task=task,
        envelope=envelope,
        reservation=reservation,
        reservation_verifier=authority,
        now_epoch=now_epoch,
        decision_id=f"{task.task_id}:canary",
    )

    leases = LeaseStore(root / "leases.db")
    lease = leases.acquire(
        task_id=task.task_id,
        lease_id=f"{task.task_id}:lease",
        worker_id="controlled-canary",
        now_epoch=now_epoch,
        ttl_seconds=lease_ttl_seconds,
    )

    branch = f"night-shift/{task.task_id}"
    handle = manager.create(
        task_id=task.task_id,
        branch=branch,
        base_sha=state.head_sha,
    )
    output_sha = state.head_sha
    receipt: ExecutionReceipt | None = None
    try:
        leases.initialize_state(
            task_id=task.task_id,
            state="READY",
            lease_id=lease.lease_id,
            fencing_token=lease.fencing_token,
            now_epoch=now_epoch,
        )
        target = (handle.path / target_path).resolve()
        if handle.path not in target.parents:
            raise NightShiftContractError("canary target escaped worktree")
        target.parent.mkdir(parents=True, exist_ok=True)
        if mutation_writer is None:
            target.write_text(replacement_text, encoding="utf-8")
        else:
            mutation_writer(target, replacement_text)

        changes = _changed_files(handle.path)
        scope = validate_mutation_scope(task=task, changes=changes)
        if not changes:
            raise NightShiftContractError("controlled canary produced no mutation")

        _git(handle.path, "add", "--all")
        _git(
            handle.path,
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=Night Shift Canary",
            "-c",
            "user.email=night-shift-canary" + chr(64) + "example.test",
            "commit",
            "-m",
            f"canary: {task.task_id}",
        )
        output_sha = _git(handle.path, "rev-parse", "HEAD")

        diff_digest = content_digest(
            {
                "changes": [
                    {
                        "path": item.path,
                        "additions": item.additions,
                        "deletions": item.deletions,
                        "binary": item.binary,
                    }
                    for item in changes
                ],
                "changed_files": scope.changed_files,
                "changed_lines": scope.changed_lines,
            }
        )
        environment_digest = content_digest(
            {
                "mode": "CONTROLLED_LOCAL_CANARY",
                "repository": task.repository,
                "worktree_isolated": True,
                "published": False,
            }
        )
        receipt = ExecutionReceipt(
            task_id=task.task_id,
            workflow_id=f"{task.task_id}:workflow",
            lease_id=lease.lease_id,
            fencing_token=lease.fencing_token,
            policy_digest=policy.policy_digest,
            decision_digest=execution.digest(),
            state_snapshot_digest=state.digest(),
            task_capsule_digest=task.digest(),
            authority_envelope_digest=envelope.digest(),
            authority_reservation_digest=reservation.digest(),
            environment_digest=environment_digest,
            verification_digest=quorum.digest(),
            input_sha=state.head_sha,
            output_sha=output_sha,
            diff_digest=diff_digest,
            final_state="CLOSED_PASS",
            evidence_refs=(
                "canary:local-only",
                "canary:rollback-required",
                "failure-injection:complete",
            ),
        )
    finally:
        manager.remove(path=handle.path, force=True)
        _git(repo, "branch", "-D", branch)

    rollback_verified = (
        _git(repo, "rev-parse", "HEAD") == operator_head
        and branch not in _git(repo, "branch", "--format=%(refname:short)").splitlines()
        and not handle.path.exists()
    )
    if not rollback_verified or receipt is None:
        raise NightShiftContractError("controlled canary rollback verification failed")

    return ControlledCanaryResult(
        task_id=task.task_id,
        input_sha=state.head_sha,
        output_sha=output_sha,
        promotion_state=decision.state,
        receipt_digest=receipt.digest(),
        rollback_verified=True,
        published=False,
    )
