from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from factory.rqm.model.severity import Severity


@dataclass(slots=True, frozen=True)
class Finding:
    """Single finding produced by a rule or provider."""

    rule_id: str
    severity: Severity
    message: str

    file: str | None = None
    line: int | None = None

    category: str = "general"
    provider: str = ""

    metadata: dict[str, Any] = field(default_factory=dict)
