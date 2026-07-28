from collections import defaultdict
from collections.abc import Callable
from typing import Any


class EventBus:
    """
    Centralna magistrala zdarzeń KOS.
    """

    def __init__(self):
        self._subscribers: defaultdict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable):
        """Rejestruje handler dla zdarzenia."""
        if handler not in self._subscribers[event]:
            self._subscribers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable):
        """Usuwa handler."""
        if event in self._subscribers:
            self._subscribers[event] = [
                h for h in self._subscribers[event] if h != handler
            ]

            if not self._subscribers[event]:
                del self._subscribers[event]

    def publish(self, event: str, data: Any = None):
        """Publikuje zdarzenie."""
        for handler in self._subscribers.get(event, []):
            handler(data)

    def has_subscribers(self, event: str) -> bool:
        return event in self._subscribers

    def subscriber_count(self, event: str) -> int:
        return len(self._subscribers.get(event, []))

    def event_count(self) -> int:
        return len(self._subscribers)

    def clear(self):
        self._subscribers.clear()
