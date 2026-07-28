from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class EventBus:
    """
    Lightweight typed event bus used by RQM.

    Subscribers register handlers for a concrete event type.
    When an event is emitted, only handlers registered for
    that event class are executed.
    """

    def __init__(self) -> None:
        self._subscribers: defaultdict[type[Any], list[Callable[[Any], None]]] = (
            defaultdict(list)
        )

    def subscribe(
        self,
        event_type: type[T],
        handler: Callable[[T], None],
    ) -> None:
        """Register handler for event type."""
        self._subscribers[event_type].append(handler)

    def unsubscribe(
        self,
        event_type: type[T],
        handler: Callable[[T], None],
    ) -> None:
        """Remove handler if registered."""
        handlers = self._subscribers.get(event_type)
        if handlers and handler in handlers:
            handlers.remove(handler)

    def emit(self, event: Any) -> None:
        """Publish event to all subscribers."""
        for handler in list(self._subscribers.get(type(event), [])):
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Event handler failed for %s",
                    type(event).__name__,
                )

    def clear(self) -> None:
        """Remove all subscriptions."""
        self._subscribers.clear()

    def has_subscribers(self, event_type: type[Any]) -> bool:
        """Return True if any handler is registered."""
        return bool(self._subscribers.get(event_type))

    @property
    def subscriber_count(self) -> int:
        """Return total number of registered handlers."""
        return sum(len(v) for v in self._subscribers.values())
