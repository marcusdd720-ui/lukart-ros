from typing import Any


class Configuration:
    """
    Centralna konfiguracja KOS.
    """

    def __init__(self):
        self._config: dict[str, Any] = {}

    def set(self, key: str, value: Any):
        """Ustawia wartość konfiguracji."""
        self._config[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Pobiera wartość konfiguracji."""
        return self._config.get(key, default)

    def has(self, key: str) -> bool:
        """Sprawdza istnienie klucza."""
        return key in self._config

    def remove(self, key: str):
        """Usuwa klucz konfiguracji."""
        self._config.pop(key, None)

    def clear(self):
        """Czyści konfigurację."""
        self._config.clear()

    def count(self) -> int:
        """Liczba wpisów."""
        return len(self._config)

    def keys(self):
        """Lista kluczy."""
        return sorted(self._config.keys())

    def as_dict(self) -> dict[str, Any]:
        """Zwraca kopię konfiguracji."""
        return dict(self._config)
