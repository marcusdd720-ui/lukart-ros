"""Counterfactual shadow calibration and autonomy-debt accounting."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import NightShiftContractError


@dataclass(frozen=True, slots=True)
class ShadowPrediction:
    task_id: str
    executor_class: str
    expected_terminal_state: str


@dataclass(frozen=True, slots=True)
class ShadowObservation:
    task_id: str
    executor_class: str
    terminal_state: str


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    exact_match: bool
    debt_delta: int


def compare_shadow(
    prediction: ShadowPrediction,
    observation: ShadowObservation,
) -> CalibrationResult:
    if prediction.task_id != observation.task_id:
        return CalibrationResult(False, 3)
    executor_match = prediction.executor_class == observation.executor_class
    terminal_match = (
        prediction.expected_terminal_state == observation.terminal_state
    )
    if executor_match and terminal_match:
        return CalibrationResult(True, -1)
    if terminal_match:
        return CalibrationResult(False, 1)
    return CalibrationResult(False, 2)


@dataclass(frozen=True, slots=True)
class AutonomyDebt:
    value: int
    downgrade_threshold: int = 10

    def __post_init__(self) -> None:
        if self.value < 0:
            raise NightShiftContractError("autonomy debt cannot be negative")
        if self.downgrade_threshold < 1:
            raise NightShiftContractError(
                "autonomy debt threshold must be positive"
            )

    def apply(self, result: CalibrationResult) -> AutonomyDebt:
        return AutonomyDebt(
            value=max(0, self.value + result.debt_delta),
            downgrade_threshold=self.downgrade_threshold,
        )

    @property
    def requires_downgrade(self) -> bool:
        return self.value >= self.downgrade_threshold
