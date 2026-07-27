from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Score:
    """
    Represents the quality score calculated by the Release Quality Manager.
    """

    value: float

    infos: int = 0

    warnings: int = 0

    errors: int = 0

    criticals: int = 0