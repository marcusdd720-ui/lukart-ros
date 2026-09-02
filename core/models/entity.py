"""
KOS - Base Entity

Base class for all domain entities.

Every entity has:
- strongly typed identifier
- creation timestamp
- update timestamp
- optimistic version number
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from .ids import EntityId, new_entity_id


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(UTC)


@dataclass(slots=True, kw_only=True)
class Entity:
    """
    Base class for all KOS entities.
    """

    id: EntityId = field(default_factory=new_entity_id)

    created_at: datetime = field(default_factory=utc_now)

    updated_at: datetime = field(default_factory=utc_now)

    version: int = 1

    def touch(self) -> None:
        """
        Update modification timestamp and increment version.
        """
        self.updated_at = utc_now()
        self.version += 1
