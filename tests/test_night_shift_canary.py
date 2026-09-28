from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from core.night_shift.canary import run_controlled_canary
from core.night_shift.contracts import (
    AutonomyEnvelope,
    LiveStateSnapshot,
    NightShiftContractError,
    PolicyRef,
    PromotionMode,
    RiskClass,
    TaskCapsule,
)
from core.night_shift.failure_gate import (
    FailureInjectionEvidence,
    FailureInjectionReport,
    load_required_failure_scenarios,
)
from core.night_shift.promotion import VerificationQuorum

POLICY_PATH = Path("docs/execution_profiles/NIGHT_SHIFT_POLICY_V2.yaml")


def _run(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        list(args),
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(repo, "git", "init", "-b", "main")
    _run(repo, "git", "config", "user.name", "Canary Test")
    synthetic_email = "canary" + chr(64) + "example.test"
    _run(repo, "git", "config", "user.email", synthetic_email)
    _run(repo, "git", "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    (repo / "OTHER.md").write_text("other\n", encoding="utf-8")
    _run(repo, "git", "add", ".")
    _run(repo, "git", "commit", "-m", "baseline")
    return repo, _run(repo, "git", "rev-parse", "HEAD")


def _quorum(sha: str, task_digest: str) -> VerificationQuorum:
    return VerificationQuorum(
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        "builder",
        "reviewer",
        sha,
        task_digest,
        "f" * 64,
        100,
    )


def _failure_report() -> tuple[FailureInjectionReport, tuple[str, ...]]:
    required = load_required_failure_scenarios(POLICY_PATH)
    report = FailureInjectionReport(
        tuple(
            FailureInjectionEvidence(item, True, f"test:{item}")
            for item in required
        )
    )
    return report, required


def _inputs(
    *,
    sha: str,
    risk: RiskClass = RiskClass.R0,
    allowed_paths: tuple[str, ...] = ("README.md",),
):
    policy = PolicyRef("night-shift", "v2", "a" * 64)
    state = LiveStateSnapshot(
        snapshot_id="canary-state",
        repository="synthetic/canary",
        branch="main",
        base_sha=sha,
        head_sha=sha,
        observed_at_epoch=1,
        expires_at_epoch=100,
        evidence_refs=("git:synthetic",),
    )
    task = TaskCapsule(
        task_id="canary-001",
        repository="synthetic/canary",
        state_snapshot_digest=state.digest(),
        policy_digest=policy.policy_digest,
        objective="local-only controlled canary",
        risk_class=risk,
        allowed_paths=allowed_paths,
        forbidden_paths=(".github/**",),
        acceptance_checks=("pytest",),
        max_files_changed=1,
        max_lines_changed=20,
    )
    mode = PromotionMode.AUTO if risk is RiskClass.R0 else PromotionMode.PREAUTHORIZED
    envelope = AutonomyEnvelope(
        envelope_id="canary-envelope",
        issued_at_epoch=1,
        expires_at_epoch=100,
        repositories=("synthetic/canary",),
        allowed_risk_classes=(risk,),
        max_tasks=1,
        promotion_mode=mode,
    )
    return policy, state, task, envelope


def test_controlled_canary_mutates_only_isolated_worktree_and_rolls_back(
    tmp_path: Path,
) -> None:
    repo, sha = _repo(tmp_path)
    policy, state, task, envelope = _inputs(sha=sha)
    report, required = _failure_report()

    result = run_controlled_canary(
        repository=repo,
        worktree_root=tmp_path / "night-worktrees",
        task=task,
        state=state,
        policy=policy,
        envelope=envelope,
        quorum=_quorum(state.head_sha, task.digest()),
        failure_report=report,
        required_failure_scenarios=required,
        target_path="README.md",
        replacement_text="canary\n",
        now_epoch=10,
    )

    assert result.input_sha == sha
    assert result.output_sha != sha
    assert result.rollback_verified
    assert result.published is False
    assert _run(repo, "git", "rev-parse", "HEAD") == sha
    assert _run(repo, "git", "status", "--porcelain") == ""
    assert "night-shift/canary-001" not in _run(
        repo, "git", "branch", "--format=%(refname:short)"
    ).splitlines()


def test_controlled_canary_rejects_r2(tmp_path: Path) -> None:
    repo, sha = _repo(tmp_path)
    policy, state, task, _ = _inputs(sha=sha, risk=RiskClass.R0)
    task = TaskCapsule(
        task_id=task.task_id,
        repository=task.repository,
        state_snapshot_digest=task.state_snapshot_digest,
        policy_digest=task.policy_digest,
        objective=task.objective,
        risk_class=RiskClass.R2,
        allowed_paths=task.allowed_paths,
        forbidden_paths=task.forbidden_paths,
        acceptance_checks=task.acceptance_checks,
    )
    envelope = AutonomyEnvelope(
        envelope_id="human-only",
        issued_at_epoch=1,
        expires_at_epoch=100,
        repositories=("synthetic/canary",),
        allowed_risk_classes=(RiskClass.R2,),
        max_tasks=1,
        promotion_mode=PromotionMode.HUMAN,
    )
    report, required = _failure_report()
    with pytest.raises(NightShiftContractError, match="limited to R0/R1"):
        run_controlled_canary(
            repository=repo,
            worktree_root=tmp_path / "night-worktrees",
            task=task,
            state=state,
            policy=policy,
            envelope=envelope,
            quorum=_quorum(state.head_sha, task.digest()),
            failure_report=report,
            required_failure_scenarios=required,
            target_path="README.md",
            replacement_text="blocked\n",
            now_epoch=10,
        )


def test_scope_violation_rolls_back_and_cleans_branch(tmp_path: Path) -> None:
    repo, sha = _repo(tmp_path)
    policy, state, task, envelope = _inputs(sha=sha)
    report, required = _failure_report()

    with pytest.raises(NightShiftContractError, match="outside allowed task scope"):
        run_controlled_canary(
            repository=repo,
            worktree_root=tmp_path / "night-worktrees",
            task=task,
            state=state,
            policy=policy,
            envelope=envelope,
            quorum=_quorum(state.head_sha, task.digest()),
            failure_report=report,
            required_failure_scenarios=required,
            target_path="OTHER.md",
            replacement_text="not allowed\n",
            now_epoch=10,
        )

    assert _run(repo, "git", "rev-parse", "HEAD") == sha
    assert "night-shift/canary-001" not in _run(
        repo, "git", "branch", "--format=%(refname:short)"
    ).splitlines()


def test_reviewer_timeout_blocks_before_mutation(tmp_path: Path) -> None:
    repo, sha = _repo(tmp_path)
    policy, state, task, envelope = _inputs(sha=sha)
    report, required = _failure_report()
    quorum = VerificationQuorum(
        True,
        True,
        True,
        True,
        False,
        True,
        True,
        "builder",
        "reviewer-timeout",
        state.head_sha,
        task.digest(),
        "f" * 64,
        100,
    )
    with pytest.raises(NightShiftContractError, match="requires ELIGIBLE_AUTO"):
        run_controlled_canary(
            repository=repo,
            worktree_root=tmp_path / "night-worktrees",
            task=task,
            state=state,
            policy=policy,
            envelope=envelope,
            quorum=quorum,
            failure_report=report,
            required_failure_scenarios=required,
            target_path="README.md",
            replacement_text="blocked\n",
            now_epoch=10,
        )
    assert _run(repo, "git", "rev-parse", "HEAD") == sha


def test_disk_write_failure_cleans_worktree_and_branch(tmp_path: Path) -> None:
    repo, sha = _repo(tmp_path)
    policy, state, task, envelope = _inputs(sha=sha)
    report, required = _failure_report()

    def fail_write(_path: Path, _text: str) -> None:
        raise OSError("simulated disk pressure")

    with pytest.raises(OSError, match="disk pressure"):
        run_controlled_canary(
            repository=repo,
            worktree_root=tmp_path / "night-worktrees",
            task=task,
            state=state,
            policy=policy,
            envelope=envelope,
            quorum=_quorum(state.head_sha, task.digest()),
            failure_report=report,
            required_failure_scenarios=required,
            target_path="README.md",
            replacement_text="canary\n",
            now_epoch=10,
            mutation_writer=fail_write,
        )
    assert _run(repo, "git", "rev-parse", "HEAD") == sha
    assert "night-shift/canary-001" not in _run(
        repo, "git", "branch", "--format=%(refname:short)"
    ).splitlines()


def test_concurrent_operator_branch_advance_fails_rollback_verification(
    tmp_path: Path,
) -> None:
    repo, sha = _repo(tmp_path)
    policy, state, task, envelope = _inputs(sha=sha)
    report, required = _failure_report()

    def advance_operator_then_write(path: Path, text: str) -> None:
        (repo / "OPERATOR.txt").write_text("advance\n", encoding="utf-8")
        _run(repo, "git", "add", "OPERATOR.txt")
        _run(repo, "git", "commit", "-m", "concurrent operator advance")
        path.write_text(text, encoding="utf-8")

    with pytest.raises(NightShiftContractError, match="rollback verification failed"):
        run_controlled_canary(
            repository=repo,
            worktree_root=tmp_path / "night-worktrees",
            task=task,
            state=state,
            policy=policy,
            envelope=envelope,
            quorum=_quorum(state.head_sha, task.digest()),
            failure_report=report,
            required_failure_scenarios=required,
            target_path="README.md",
            replacement_text="canary\n",
            now_epoch=10,
            mutation_writer=advance_operator_then_write,
        )
    assert _run(repo, "git", "rev-parse", "HEAD") != sha
    assert "night-shift/canary-001" not in _run(
        repo, "git", "branch", "--format=%(refname:short)"
    ).splitlines()
