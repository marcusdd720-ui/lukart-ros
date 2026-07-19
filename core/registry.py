from typing import Any, Dict


class Registry:
    """
    Centralny rejestr komponentów KOS.
    """

    def __init__(self):
        self._services: Dict[str, Any] = {}

    def register(self, name: str, service: Any):
        if name in self._services:
            raise ValueError(f"Service '{name}' already registered")

        self._services[name] = service

    def get(self, name: str) -> Any:
        if name not in self._services:
            raise KeyError(f"Service '{name}' not found")

        return self._services[name]

    def has(self, name: str) -> bool:
        return name in self._services

    def unregister(self, name: str):
        self._services.pop(name, None)

    def clear(self):
        self._services.clear()

    def count(self) -> int:
        return len(self._services)

    def list(self):
        return sorted(self._services.keys())