from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.night_shift.contracts import NightShiftContractError, RiskClass
from core.night_shift.controlled_pilot import (
    ControlledNightPilotContext,
    ControlledNightPilotPolicy,
    run_controlled_night_pilot,
)
from core.night_shift.executor_registry import ExecutorProfile
from core.night_shift.portfolio import PortfolioSnapshot, ProjectState
from core.night_shift.project_registry import ProjectConfig, ProjectRegistry
from core.night_shift.scheduler import ResourcePolicy
from tests.test_night_shift_canary import (
    _failure_report,
    _inputs,
    _repo,
    _shadow_clearance,
    _verification,
)


def _registry() -> ProjectRegistry:
    return ProjectRegistry(
        (
            ProjectConfig(
                "PILOT",
                "synthetic/canary",
                0,
                RiskClass.R0,
                ("bounded_code_change", "git"),
                True,
            ),
        )
    )


def _executors() -> tuple[ExecutorProfile, ...]:
    return (
        ExecutorProfile(
            "local-writer",
            ("bounded_code_change", "git"),
            True,
            False,
            0,
            True,
            True,
            False,
            1,
        ),
    )


def _snapshot(sha: str, *, risk: RiskClass = RiskClass.R0) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        "pilot-snapshot",
        1,
        100,
        (
            ProjectState(
                "PILOT",
                "synthetic/canary",
                sha,
                "canary-001",
                90,
                risk,
                evidence_refs=(f"git:synthetic:{sha}",),
            ),
        ),
    )


def _context(
    tmp_path: Path,
    sha: str,
    *,
    risk: RiskClass = RiskClass.R0,
) -> ControlledNightPilotContext:
    policy, state, task, envelope = _inputs(sha=sha, risk=risk)
    report, required = _failure_report(
        subject_sha=state.head_sha,
        state_snapshot_digest=state.digest(),
        task_capsule_digest=task.digest(),
        policy_digest=policy.policy_digest,
    )
    quorum, crypto = _verification(state.head_sha, task.digest())
    return ControlledNightPilotContext(
        repository=tmp_path / "repo",
        worktree_root=tmp_path / "pilot-worktrees",
        task=task,
        state=state,
        policy=policy,
        envelope=envelope,
        quorum=quorum,
        cryptographic_context=crypto,
        shadow_clearance=_shadow_clearance(state.head_sha, task.digest()),
        expected_shadow_ledger_digest="a" * 64,
        failure_report=report,
        expected_failure_report_digest=report.digest(),
        expected_failure_suite_profile_digest="b" * 64,
        required_failure_scenarios=required,
        target_path="README.md",
        replacement_text="controlled night pilot\n",
    )


def test_controlled_night_pilot_closes_one_local_task_and_rolls_back(
    tmp_path: Path,
) -> None:
    repo, sha = _repo(tmp_path)
    context = _context(tmp_path, sha)
    assert Path(context.repository) == repo

    result = run_controlled_night_pilot(
        snapshot=_snapshot(sha),
        registry=_registry(),
        executors=_executors(),
        resource_policy=ResourcePolicy(
            technical_active_max=1,
            local_code_writers_max=1,
            heavy_local_compute_max=0,
        ),
        pilot_policy=ControlledNightPilotPolicy(),
        context=context,
        now_epoch=10,
    )

    assert result.task_id == "canary-001"
    assert result.project_id == "PILOT"
    assert result.canary.input_sha == sha
    assert result.canary.output_sha != sha
    assert result.canary.rollback_verified is True
    assert result.canary.published is False
    assert result.report.closed == ()
    assert result.report.ready_for_human == ("canary-001",)
    assert result.report.planned == ()
    assert any(ref.startswith("receipt:") for ref in result.report.evidence_refs)
    assert result.digest()


def test_controlled_night_pilot_rejects_multiple_dispatches(tmp_path: Path) -> None:
    repo, sha = _repo(tmp_path)
    context = _context(tmp_path, sha)
    registry = ProjectRegistry(
        (
            ProjectConfig(
                "PILOT",
                "synthetic/canary",
                0,
                RiskClass.R0,
                ("bounded_code_change", "git"),
                True,
            ),
            ProjectConfig(
                "SECOND",
                "synthetic/second",
                1,
                RiskClass.R0,
                ("bounded_code_change", "git"),
                True,
            ),
        )
    )
    snapshot = PortfolioSnapshot(
        "two",
        1,
        100,
        (
            ProjectState(
                "PILOT",
                "synthetic/canary",
                sha,
                "canary-001",
                90,
                RiskClass.R0,
                evidence_refs=("git:first",),
            ),
            ProjectState(
                "SECOND",
                "synthetic/second",
                "b" * 40,
                "second-task",
                80,
                RiskClass.R0,
                evidence_refs=("git:second",),
            ),
        ),
    )
    assert Path(context.repository) == repo

    with pytest.raises(NightShiftContractError, match="exactly one planned dispatch"):
        run_controlled_night_pilot(
            snapshot=snapshot,
            registry=registry,
            executors=(
                ExecutorProfile(
                    "parallel-writer",
                    ("bounded_code_change", "git"),
                    True,
                    False,
                    0,
                    True,
                    True,
                    False,
                    2,
                ),
            ),
            resource_policy=ResourcePolicy(
                technical_active_max=2,
                local_code_writers_max=2,
                heavy_local_compute_max=0,
            ),
            pilot_policy=ControlledNightPilotPolicy(),
            context=context,
            now_epoch=10,
        )


def test_controlled_night_pilot_rejects_r2_before_mutation(tmp_path: Path) -> None:
    repo, sha = _repo(tmp_path)
    context = _context(tmp_path, sha)
    registry = ProjectRegistry(
        (
            ProjectConfig(
                "PILOT",
                "synthetic/canary",
                0,
                RiskClass.R2,
                ("bounded_code_change", "git"),
                True,
            ),
        )
    )
    assert Path(context.repository) == repo

    with pytest.raises(NightShiftContractError, match="outside the pilot envelope"):
        run_controlled_night_pilot(
            snapshot=_snapshot(sha, risk=RiskClass.R2),
            registry=registry,
            executors=_executors(),
            resource_policy=ResourcePolicy(),
            pilot_policy=ControlledNightPilotPolicy(),
            context=context,
            now_epoch=10,
        )


def test_controlled_night_pilot_rejects_stale_snapshot(tmp_path: Path) -> None:
    repo, sha = _repo(tmp_path)
    context = _context(tmp_path, sha)
    assert Path(context.repository) == repo

    with pytest.raises(NightShiftContractError, match="portfolio snapshot is stale"):
        run_controlled_night_pilot(
            snapshot=_snapshot(sha),
            registry=_registry(),
            executors=_executors(),
            resource_policy=ResourcePolicy(),
            pilot_policy=ControlledNightPilotPolicy(),
            context=context,
            now_epoch=100,
        )


def test_controlled_night_pilot_rejects_wrong_project_main(tmp_path: Path) -> None:
    repo, sha = _repo(tmp_path)
    context = _context(tmp_path, sha)
    assert Path(context.repository) == repo

    with pytest.raises(NightShiftContractError, match="current project main"):
        run_controlled_night_pilot(
            snapshot=_snapshot("b" * 40),
            registry=_registry(),
            executors=_executors(),
            resource_policy=ResourcePolicy(),
            pilot_policy=ControlledNightPilotPolicy(),
            context=context,
            now_epoch=10,
        )


def test_controlled_night_pilot_surfaces_unselected_ready_task(
    tmp_path: Path,
) -> None:
    repo, sha = _repo(tmp_path)
    context = _context(tmp_path, sha)
    registry = ProjectRegistry(
        (
            ProjectConfig(
                "PILOT",
                "synthetic/canary",
                0,
                RiskClass.R0,
                ("bounded_code_change", "git"),
                True,
            ),
            ProjectConfig(
                "SECOND",
                "synthetic/second",
                1,
                RiskClass.R0,
                ("bounded_code_change", "git"),
                True,
            ),
        )
    )
    snapshot = PortfolioSnapshot(
        "two-ready",
        1,
        100,
        (
            ProjectState(
                "PILOT",
                "synthetic/canary",
                sha,
                "canary-001",
                90,
                RiskClass.R0,
                evidence_refs=("git:first",),
            ),
            ProjectState(
                "SECOND",
                "synthetic/second",
                "b" * 40,
                "second-task",
                80,
                RiskClass.R0,
                evidence_refs=("git:second",),
            ),
        ),
    )
    assert Path(context.repository) == repo

    result = run_controlled_night_pilot(
        snapshot=snapshot,
        registry=registry,
        executors=_executors(),
        resource_policy=ResourcePolicy(
            technical_active_max=2,
            local_code_writers_max=1,
            heavy_local_compute_max=0,
        ),
        pilot_policy=ControlledNightPilotPolicy(),
        context=context,
        now_epoch=10,
    )

    assert result.report.closed == ()
    assert result.report.ready_for_human == ("canary-001", "second-task")


def test_controlled_night_pilot_rejects_broad_autonomy_envelope(
    tmp_path: Path,
) -> None:
    repo, sha = _repo(tmp_path)
    context = _context(tmp_path, sha)
    assert Path(context.repository) == repo
    context = replace(
        context,
        envelope=replace(context.envelope, max_tasks=2),
    )

    with pytest.raises(NightShiftContractError, match="single-task autonomy envelope"):
        run_controlled_night_pilot(
            snapshot=_snapshot(sha),
            registry=_registry(),
            executors=_executors(),
            resource_policy=ResourcePolicy(),
            pilot_policy=ControlledNightPilotPolicy(),
            context=context,
            now_epoch=10,
        )


def test_controlled_night_policy_cannot_enable_publication() -> None:
    with pytest.raises(NightShiftContractError, match="cannot enable external publication"):
        ControlledNightPilotPolicy(external_publication_enabled=True)
