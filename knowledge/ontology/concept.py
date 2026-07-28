from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.models.entity import Entity
from core.models.ids import EntityId


@dataclass(slots=True)
class OntologyConcept(Entity):
    """Podstawowa jednostka ontologii KOS."""

    name: str
    description: str = ""

    aliases: set[str] = field(default_factory=set)

    properties: dict[str, Any] = field(default_factory=dict)

    parents: set[EntityId] = field(default_factory=set)

    children: set[EntityId] = field(default_factory=set)

    relations: set[EntityId] = field(default_factory=set)
