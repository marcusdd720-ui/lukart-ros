"""Temporal consistency validation for case timeline events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class TimelineCheckEvent:
    event_id: str
    event_date: date
    label: str = ""


def validate_timeline(events: list[TimelineCheckEvent]) -> list[str]:
    """Validate chronological order and reject duplicate conflicting IDs."""
    errors: list[str] = []
    seen: dict[str, date] = {}
    for event in events:
        prior = seen.get(event.event_id)
        if prior is not None and prior != event.event_date:
            errors.append(
                f"Event {event.event_id!r} has conflicting dates: {prior.isoformat()} "
                f"vs {event.event_date.isoformat()}"
            )
        seen[event.event_id] = event.event_date
    ordered = sorted(events, key=lambda item: (item.event_date, item.event_id))
    if events and events != ordered:
        errors.append("Timeline events are not in deterministic chronological order")
    return errors


def require_valid_timeline(events: list[TimelineCheckEvent]) -> None:
    errors = validate_timeline(events)
    if errors:
        raise ValueError("Timeline validation failed: " + "; ".join(errors))
