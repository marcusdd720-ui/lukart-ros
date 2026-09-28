from __future__ import annotations

import pytest

from core.night_shift.contracts import (
    LiveStateSnapshot,
    NightShiftContractError,
    PolicyRef,
    RiskClass,
    TaskCapsule,
)
from core.night_shift.scope import ChangedFile, validate_mutation_scope


def _task(
    *,
    max_files_changed: int = 3,
    max_lines_changed: int = 20,
    allow_binary_changes: bool = False,
) -> TaskCapsule:
    policy = PolicyRef(
        policy_id="policy",
        version="v2",
        policy_digest="a" * 64,
    )
    state = LiveStateSnapshot(
        snapshot_id="state",
        repository="repo",
        branch="branch",
        base_sha="b" * 40,
        head_sha="c" * 40,
        observed_at_epoch=1,
        expires_at_epoch=100,
        evidence_refs=("git:head",),
    )
    return TaskCapsule(
        task_id="task",
        repository="repo",
        state_snapshot_digest=state.digest(),
        policy_digest=policy.policy_digest,
        objective="bounded mutation",
        risk_class=RiskClass.R1,
        allowed_paths=("core/night_shift/**", "tests/test_night_shift_*.py"),
        forbidden_paths=("core/night_shift/secrets/**",),
        acceptance_checks=("pytest",),
        max_files_changed=max_files_changed,
        max_lines_changed=max_lines_changed,
        allow_binary_changes=allow_binary_changes,
    )


def test_scope_accepts_bounded_allowed_change() -> None:
    result = validate_mutation_scope(
        task=_task(),
        changes=(
            ChangedFile("core/night_shift/engine.py", additions=5, deletions=2),
            ChangedFile("tests/test_night_shift_engine.py", additions=4, deletions=1),
        ),
    )
    assert result.changed_files == 2
    assert result.changed_lines == 12


def test_forbidden_path_fails_closed() -> None:
    with pytest.raises(NightShiftContractError, match="forbidden task scope"):
        validate_mutation_scope(
            task=_task(),
            changes=(
                ChangedFile(
                    "core/night_shift/secrets/key.py",
                    additions=1,
                    deletions=0,
                ),
            ),
        )


def test_path_outside_allowed_scope_fails_closed() -> None:
    with pytest.raises(NightShiftContractError, match="outside allowed task scope"):
        validate_mutation_scope(
            task=_task(),
            changes=(ChangedFile(".github/workflows/ci.yml", 1, 0),),
        )


def test_file_and_line_budgets_fail_closed() -> None:
    with pytest.raises(NightShiftContractError, match="file count"):
        validate_mutation_scope(
            task=_task(max_files_changed=1),
            changes=(
                ChangedFile("core/night_shift/a.py", 1, 0),
                ChangedFile("core/night_shift/b.py", 1, 0),
            ),
        )

    with pytest.raises(NightShiftContractError, match="line count"):
        validate_mutation_scope(
            task=_task(max_lines_changed=2),
            changes=(ChangedFile("core/night_shift/a.py", 2, 1),),
        )


def test_binary_change_requires_explicit_authority() -> None:
    with pytest.raises(NightShiftContractError, match="binary change"):
        validate_mutation_scope(
            task=_task(),
            changes=(ChangedFile("core/night_shift/blob.bin", 0, 0, binary=True),),
        )
