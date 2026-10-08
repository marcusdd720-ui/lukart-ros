from __future__ import annotations

import sys
from pathlib import Path

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.leases import LeaseStore
from core.night_shift.process_agent_executor import (
    BoundedProcessAgentExecutor,
    ProcessAgentRequest,
)


FIXTURE = Path(__file__).resolve().parents[1] / "core" / "night_shift" / "_real_agent_fixture.py"


def test_real_mutating_builder_then_distinct_reviewer_handoff(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    leases = LeaseStore(tmp_path / "leases.db")

    builder_lease = leases.acquire(
        task_id="build",
        lease_id="build-lease",
        worker_id="builder-worker",
        now_epoch=1,
        ttl_seconds=60,
    )
    leases.initialize_state(
        task_id="build",
        state="RUNNING",
        lease_id=builder_lease.lease_id,
        fencing_token=builder_lease.fencing_token,
        now_epoch=2,
    )
    builder = BoundedProcessAgentExecutor(
        executor_id="zero_cost_local_builder",
        workspace_root=tmp_path,
        allowed_executables=(sys.executable,),
        mutating=True,
        independent_review=False,
    )
    build_result = builder.execute(
        ProcessAgentRequest(
            task_id="build",
            command=(sys.executable, str(FIXTURE), "build"),
            workspace=str(workspace),
            mutating=True,
            timeout_seconds=10,
        )
    )
    assert build_result.passed
    assert build_result.child_pid > 0
    assert build_result.progress_events == ("workspace-mutated",)
    assert (workspace / "product.txt").is_file()
    leases.compare_and_swap_state(
        task_id="build",
        expected_version=1,
        new_state="DONE",
        lease_id=builder_lease.lease_id,
        fencing_token=builder_lease.fencing_token,
        now_epoch=3,
    )

    reviewer_lease = leases.acquire(
        task_id="review",
        lease_id="review-lease",
        worker_id="reviewer-worker",
        now_epoch=4,
        ttl_seconds=60,
    )
    leases.initialize_state(
        task_id="review",
        state="RUNNING",
        lease_id=reviewer_lease.lease_id,
        fencing_token=reviewer_lease.fencing_token,
        now_epoch=5,
    )
    reviewer = BoundedProcessAgentExecutor(
        executor_id="zero_cost_local_reviewer",
        workspace_root=tmp_path,
        allowed_executables=(sys.executable,),
        mutating=False,
        independent_review=True,
    )
    review_result = reviewer.execute(
        ProcessAgentRequest(
            task_id="review",
            command=(sys.executable, str(FIXTURE), "review"),
            workspace=str(workspace),
            mutating=False,
            timeout_seconds=10,
        )
    )
    assert review_result.passed
    assert review_result.progress_events == ("independent-review-complete",)
    assert review_result.run_id != build_result.run_id
    leases.compare_and_swap_state(
        task_id="review",
        expected_version=1,
        new_state="DONE",
        lease_id=reviewer_lease.lease_id,
        fencing_token=reviewer_lease.fencing_token,
        now_epoch=6,
    )
    assert leases.get_state(task_id="build").state == "DONE"
    assert leases.get_state(task_id="review").state == "DONE"


def test_reviewer_fails_closed_on_mutation_request(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    reviewer = BoundedProcessAgentExecutor(
        executor_id="zero_cost_local_reviewer",
        workspace_root=tmp_path,
        allowed_executables=(sys.executable,),
        mutating=False,
        independent_review=True,
    )
    with pytest.raises(NightShiftContractError, match="not authorized for mutation"):
        reviewer.execute(
            ProcessAgentRequest(
                task_id="bad-review",
                command=(sys.executable, str(FIXTURE), "build"),
                workspace=str(workspace),
                mutating=True,
                timeout_seconds=10,
            )
        )


def test_workspace_escape_and_unlisted_executable_fail_closed(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    executor = BoundedProcessAgentExecutor(
        executor_id="zero_cost_local_builder",
        workspace_root=workspace,
        allowed_executables=(sys.executable,),
        mutating=True,
        independent_review=False,
    )
    with pytest.raises(NightShiftContractError, match="escapes"):
        executor.execute(
            ProcessAgentRequest(
                task_id="escape",
                command=(sys.executable, str(FIXTURE), "build"),
                workspace=str(tmp_path),
                mutating=True,
            )
        )
    with pytest.raises(NightShiftContractError, match="allow-listed"):
        executor.execute(
            ProcessAgentRequest(
                task_id="unlisted",
                command=("definitely-not-allowed", "x"),
                workspace=str(workspace),
                mutating=True,
            )
        )
