from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TrendDirection(StrEnum):
    """
    Quality trend direction.
    """

    NEW = "NEW"
    UP = "UP"
    DOWN = "DOWN"
    STABLE = "STABLE"


@dataclass(slots=True, frozen=True)
class Trend:
    """
    Quality trend information.
    """

    direction: TrendDirection
    delta: float
    previous_score: float | None = None