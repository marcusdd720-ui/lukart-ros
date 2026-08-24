"""
Metadata objects used throughout KOS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from .enums import SourceType


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Provenance:
    """
    Describes where information originated.
    """

    source: SourceType
    source_id: str | None = None
    source_name: str | None = None
    author: str | None = None
    imported_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class CustodyEvent:
    """
    Single chain-of-custody event.
    """

    actor: str
    action: str
    timestamp: datetime = field(default_factory=utc_now)
    comment: str | None = None


@dataclass(slots=True)
class Metadata:
    """
    Rich metadata container.

    Shared by all domain entities.
    """

    provenance: Provenance
    confidence: float = 1.0
    checksum: str | None = None
    classification: str = "internal"
    tags: set[str] = field(default_factory=set)
    labels: dict[str, str] = field(default_factory=dict)
    custody: list[CustodyEvent] = field(default_factory=list)
    attributes: dict[str, object] = field(default_factory=dict)

    def add_tag(self, tag: str) -> None:
        self.tags.add(tag)

    def remove_tag(self, tag: str) -> None:
        self.tags.discard(tag)

    def add_label(self, key: str, value: str) -> None:
        self.labels[key] = value

    def add_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def add_custody_event(self, event: CustodyEvent) -> None:
        self.custody.append(event)
