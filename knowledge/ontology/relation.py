from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.models.entity import Entity
from core.models.ids import EntityId


@dataclass(slots=True)
class Relation(Entity):
    """Relacja pomiędzy dwoma konceptami."""

    source: EntityId

    target: EntityId

    relation_type: str

    confidence: float = 1.0

    metadata: dict[str, Any] = field(default_factory=dict)
