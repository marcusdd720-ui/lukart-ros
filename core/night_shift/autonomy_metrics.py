"""Metrics for autonomous progress and human friction."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import NightShiftContractError


@dataclass(frozen=True, slots=True)
class AutonomyMetrics:
    attempted: int
    closed: int
    human_signing_events: int
    human_interventions: int
    elapsed_seconds: int

    def __post_init__(self) -> None:
        if (
            min(
                self.attempted,
                self.closed,
                self.human_signing_events,
                self.human_interventions,
                self.elapsed_seconds,
            )
            < 0
            or self.closed > self.attempted
        ):
            raise NightShiftContractError("invalid autonomy metrics")

    @property
    def closure_rate(self) -> float:
        return 0.0 if self.attempted == 0 else self.closed / self.attempted

    @property
    def signing_friction(self) -> float:
        return 0.0 if self.closed == 0 else self.human_signing_events / self.closed
