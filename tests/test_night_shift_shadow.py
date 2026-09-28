from core.night_shift.shadow import (
    AutonomyDebt,
    ShadowObservation,
    ShadowPrediction,
    compare_shadow,
)


def test_exact_shadow_match_retires_debt() -> None:
    result = compare_shadow(
        ShadowPrediction("task-1", "codex", "READY_FOR_HUMAN"),
        ShadowObservation("task-1", "codex", "READY_FOR_HUMAN"),
    )
    debt = AutonomyDebt(3).apply(result)
    assert result.exact_match
    assert debt.value == 2


def test_terminal_divergence_increases_debt() -> None:
    result = compare_shadow(
        ShadowPrediction("task-1", "codex", "CLOSED_PASS"),
        ShadowObservation("task-1", "codex", "BLOCKED"),
    )
    debt = AutonomyDebt(9, downgrade_threshold=10).apply(result)
    assert debt.value == 11
    assert debt.requires_downgrade
