"""TM-1.0 temporal semantics for auditable cognitive objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TemporalCertainty(StrEnum):
    EXACT = "exact"
    BOUNDED_INTERVAL = "bounded_interval"
    APPROXIMATE = "approximate"
    RELATIVE = "relative"
    UNKNOWN = "unknown"
    DISPUTED = "disputed"


@dataclass(frozen=True, slots=True)
class TemporalValue:
    value: str | None
    certainty: TemporalCertainty
    provenance_ref: str | None = None
    anchor_ref: str | None = None
    interval_end: str | None = None

    def __post_init__(self) -> None:
        if self.value is not None and not self.value.strip():
            raise ValueError("TemporalValue.value cannot be blank")
        if self.provenance_ref is not None and not self.provenance_ref.strip():
            raise ValueError("TemporalValue.provenance_ref cannot be blank")
        if self.anchor_ref is not None and not self.anchor_ref.strip():
            raise ValueError("TemporalValue.anchor_ref cannot be blank")
        if self.interval_end is not None and not self.interval_end.strip():
            raise ValueError("TemporalValue.interval_end cannot be blank")
        if self.certainty is TemporalCertainty.UNKNOWN and self.value is not None:
            raise ValueError("UNKNOWN temporal value cannot carry an exact value")
        if self.certainty is TemporalCertainty.BOUNDED_INTERVAL:
            if self.value is None or self.interval_end is None:
                raise ValueError("bounded interval requires start and end")
        elif self.interval_end is not None:
            raise ValueError("interval_end is valid only for bounded intervals")
        if self.certainty is TemporalCertainty.RELATIVE and self.anchor_ref is None:
            raise ValueError("relative time requires a reliable anchor reference")


@dataclass(frozen=True, slots=True)
class TemporalCoordinates:
    event_time: TemporalValue
    source_time: TemporalValue
    knowledge_time: TemporalValue
    system_time: TemporalValue
    valid_from: TemporalValue | None = None
    valid_to: TemporalValue | None = None

    def __post_init__(self) -> None:
        if self.knowledge_time.certainty is not TemporalCertainty.EXACT:
            raise ValueError("knowledge_time must be recorded exactly")
        if self.system_time.certainty is not TemporalCertainty.EXACT:
            raise ValueError("system_time must be recorded exactly")
        if self.valid_to is not None and self.valid_from is None:
            raise ValueError("valid_to cannot exist without valid_from")


@dataclass(frozen=True, slots=True)
class TemporalRevision:
    object_id: str
    object_version: str
    coordinates: TemporalCoordinates
    supersedes_version: str | None = None

    def __post_init__(self) -> None:
        if not self.object_id.strip() or not self.object_version.strip():
            raise ValueError("TemporalRevision identity fields cannot be empty")
        if self.supersedes_version is not None and not self.supersedes_version.strip():
            raise ValueError("supersedes_version cannot be blank")

    def revise_event_time(
        self,
        *,
        object_version: str,
        event_time: TemporalValue,
        knowledge_time: TemporalValue,
        system_time: TemporalValue,
    ) -> TemporalRevision:
        if object_version == self.object_version:
            raise ValueError("temporal correction requires a new object version")
        coordinates = TemporalCoordinates(
            event_time=event_time,
            source_time=self.coordinates.source_time,
            knowledge_time=knowledge_time,
            system_time=system_time,
            valid_from=self.coordinates.valid_from,
            valid_to=self.coordinates.valid_to,
        )
        return TemporalRevision(
            object_id=self.object_id,
            object_version=object_version,
            coordinates=coordinates,
            supersedes_version=self.object_version,
        )


@dataclass(frozen=True, slots=True)
class TimelineProjectionRef:
    object_id: str
    object_version: str
    event_time: TemporalValue
    provenance_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.object_id.strip() or not self.object_version.strip():
            raise ValueError("TimelineProjectionRef identity fields cannot be empty")
        if any(not ref.strip() for ref in self.provenance_refs):
            raise ValueError("timeline provenance refs cannot contain empty values")


def known_order(left: TemporalValue, right: TemporalValue) -> int | None:
    """Return lexical order only when both values are exact; otherwise preserve uncertainty."""
    if left.certainty is not TemporalCertainty.EXACT:
        return None
    if right.certainty is not TemporalCertainty.EXACT:
        return None
    if left.value is None or right.value is None:
        return None
    if left.value < right.value:
        return -1
    if left.value > right.value:
        return 1
    return 0
