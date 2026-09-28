from __future__ import annotations

from dataclasses import replace

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.shadow import (
    AutonomyDebt,
    AutonomyDebtLedger,
    ShadowDivergence,
    ShadowObservation,
    ShadowPrediction,
    compare_shadow,
    issue_shadow_clearance,
)

REPO = "repo"
SHA = "a" * 40
STATE = "b" * 64
TASK = "c" * 64
POLICY = "d" * 64


def _prediction(
    *,
    task_id: str = "task-1",
    executor: str = "deterministic_local",
    terminal: str = "CLOSED_PASS",
    task_digest: str = TASK,
) -> ShadowPrediction:
    return ShadowPrediction(
        task_id=task_id,
        repository=REPO,
        subject_sha=SHA,
        state_snapshot_digest=STATE,
        task_capsule_digest=task_digest,
        policy_digest=POLICY,
        executor_class=executor,
        expected_terminal_state=terminal,
        predicted_at_epoch=10,
        expires_at_epoch=100,
    )


def _observation(
    prediction: ShadowPrediction,
    *,
    executor: str | None = None,
    terminal: str | None = None,
    observed_at_epoch: int = 20,
) -> ShadowObservation:
    return ShadowObservation(
        task_id=prediction.task_id,
        repository=prediction.repository,
        subject_sha=prediction.subject_sha,
        state_snapshot_digest=prediction.state_snapshot_digest,
        task_capsule_digest=prediction.task_capsule_digest,
        policy_digest=prediction.policy_digest,
        executor_class=executor or prediction.executor_class,
        terminal_state=terminal or prediction.expected_terminal_state,
        observed_at_epoch=observed_at_epoch,
    )


def test_exact_shadow_match_retires_debt_without_going_negative() -> None:
    prediction = _prediction()
    result = compare_shadow(prediction, _observation(prediction))
    assert result.exact_match
    assert result.divergence is ShadowDivergence.EXACT_MATCH
    assert result.debt_delta == -1
    assert AutonomyDebt(0).apply(result).value == 0
    assert AutonomyDebt(3).apply(result).value == 2


def test_terminal_divergence_increases_debt() -> None:
    prediction = _prediction()
    result = compare_shadow(
        prediction,
        _observation(prediction, terminal="BLOCKED"),
    )
    assert result.divergence is ShadowDivergence.TERMINAL_DIVERGENCE
    ledger = AutonomyDebtLedger(
        REPO,
        POLICY,
        opening_value=9,
        downgrade_threshold=10,
        minimum_samples_for_auto=1,
    ).apply(result)
    assert ledger.value == 11
    assert ledger.requires_downgrade


def test_executor_and_terminal_divergence_has_maximum_delta() -> None:
    prediction = _prediction()
    result = compare_shadow(
        prediction,
        _observation(
            prediction,
            executor="other",
            terminal="BLOCKED",
        ),
    )
    assert (
        result.divergence
        is ShadowDivergence.EXECUTOR_AND_TERMINAL_DIVERGENCE
    )
    assert result.debt_delta == 3


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("task_id", "other"),
        ("repository", "other/repo"),
        ("subject_sha", "e" * 40),
        ("state_snapshot_digest", "e" * 64),
        ("task_capsule_digest", "e" * 64),
        ("policy_digest", "e" * 64),
    ),
)
def test_shadow_twin_identity_mismatch_fails_closed(
    field_name: str,
    value: str,
) -> None:
    prediction = _prediction()
    observation = _observation(prediction)
    if field_name == "task_id":
        observation = replace(observation, task_id=value)
    elif field_name == "repository":
        observation = replace(observation, repository=value)
    elif field_name == "subject_sha":
        observation = replace(observation, subject_sha=value)
    elif field_name == "state_snapshot_digest":
        observation = replace(observation, state_snapshot_digest=value)
    elif field_name == "task_capsule_digest":
        observation = replace(observation, task_capsule_digest=value)
    elif field_name == "policy_digest":
        observation = replace(observation, policy_digest=value)
    else:
        raise AssertionError(f"unsupported test field: {field_name}")
    with pytest.raises(NightShiftContractError, match="identity mismatch"):
        compare_shadow(prediction, observation)


def test_shadow_observation_cannot_precede_prediction() -> None:
    prediction = _prediction()
    with pytest.raises(NightShiftContractError, match="predates prediction"):
        compare_shadow(
            prediction,
            _observation(prediction, observed_at_epoch=9),
        )


def test_expired_prediction_cannot_be_calibrated() -> None:
    prediction = _prediction()
    with pytest.raises(NightShiftContractError, match="expired"):
        compare_shadow(
            prediction,
            _observation(prediction, observed_at_epoch=100),
        )


def test_debt_ledger_rejects_duplicate_calibration() -> None:
    prediction = _prediction()
    result = compare_shadow(prediction, _observation(prediction))
    ledger = AutonomyDebtLedger(
        REPO,
        POLICY,
        minimum_samples_for_auto=1,
    ).apply(result)
    with pytest.raises(NightShiftContractError, match="already accounted"):
        ledger.apply(result)


def test_debt_ledger_rejects_foreign_repository_and_policy() -> None:
    prediction = _prediction()
    result = compare_shadow(prediction, _observation(prediction))
    with pytest.raises(NightShiftContractError, match="different repository"):
        AutonomyDebtLedger(
            "other",
            POLICY,
            minimum_samples_for_auto=1,
        ).apply(result)
    with pytest.raises(NightShiftContractError, match="different policy"):
        AutonomyDebtLedger(
            REPO,
            "e" * 64,
            minimum_samples_for_auto=1,
        ).apply(result)


def test_clearance_requires_minimum_shadow_samples_for_auto() -> None:
    ledger = AutonomyDebtLedger(
        REPO,
        POLICY,
        minimum_samples_for_auto=3,
    )
    clearance = issue_shadow_clearance(
        ledger=ledger,
        subject_sha=SHA,
        task_capsule_digest=TASK,
        now_epoch=20,
        ttl_seconds=30,
    )
    assert not clearance.allows_auto
    assert clearance.sample_count == 0


def test_clearance_allows_auto_after_minimum_exact_samples() -> None:
    ledger = AutonomyDebtLedger(
        REPO,
        POLICY,
        minimum_samples_for_auto=3,
    )
    for index in range(3):
        task_digest = f"{index + 1:064x}"
        prediction = _prediction(
            task_id=f"sample-{index}",
            task_digest=task_digest,
        )
        ledger = ledger.apply(
            compare_shadow(prediction, _observation(prediction))
        )
    clearance = issue_shadow_clearance(
        ledger=ledger,
        subject_sha=SHA,
        task_capsule_digest=TASK,
        now_epoch=20,
        ttl_seconds=30,
    )
    assert clearance.allows_auto
    assert clearance.sample_count == 3
    assert clearance.debt_value == 0


def test_clearance_expiry_fails_closed() -> None:
    clearance = issue_shadow_clearance(
        ledger=AutonomyDebtLedger(
            REPO,
            POLICY,
            minimum_samples_for_auto=1,
        ),
        subject_sha=SHA,
        task_capsule_digest=TASK,
        now_epoch=20,
        ttl_seconds=10,
    )
    with pytest.raises(NightShiftContractError, match="clearance expired"):
        clearance.require_fresh(now_epoch=30)


def test_shadow_identity_changes_content_addressed_prediction() -> None:
    prediction = _prediction()
    assert prediction.digest() != replace(
        prediction,
        subject_sha="f" * 40,
    ).digest()
