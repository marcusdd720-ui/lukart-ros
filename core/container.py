from typing import Any, Callable, Dict


class Container:
    """
    Prosty kontener Dependency Injection dla KOS.
    """

    def __init__(self):
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._instances: Dict[str, Any] = {}

    def register(self, name: str, factory: Callable[[], Any]):
        """
        Rejestruje fabrykę tworzącą obiekt.
        """
        if name in self._factories:
            raise ValueError(f"Service '{name}' already registered")

        self._factories[name] = factory

    def resolve(self, name: str):
        """
        Zwraca singleton tworzony przez factory.
        """
        if name not in self._factories:
            raise KeyError(f"Service '{name}' not registered")

        if name not in self._instances:
            self._instances[name] = self._factories[name]()

        return self._instances[name]

    def has(self, name: str) -> bool:
        return name in self._factories

    def unregister(self, name: str):
        self._factories.pop(name, None)
        self._instances.pop(name, None)

    def clear(self):
        self._factories.clear()
        self._instances.clear()

    def count(self) -> int:
        return len(self._factories)

    def list(self):
        return sorted(self._factories.keys())