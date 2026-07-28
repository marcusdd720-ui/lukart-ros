from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from factory.rqm.provider.base_provider import BaseProvider
from factory.rqm.provider.pytest_provider import PytestProvider
from factory.rqm.provider.audit_provider import AuditProvider


class ProviderRegistry:
    """
    Central registry for RQM providers.
    Stores provider classes, not instances.
    """

    def __init__(self) -> None:
        self._providers: dict[str, type[BaseProvider]] = {}

    @classmethod
    def default(cls) -> ProviderRegistry:
        """Create registry with built-in providers."""
        registry = cls()
        registry.register(PytestProvider)
        registry.register(AuditProvider)
        return registry

    def register(self, provider_cls: type[BaseProvider]) -> None:
        """Register a provider class."""
        if not issubclass(provider_cls, BaseProvider):
            raise TypeError(f"{provider_cls.__name__} must inherit from BaseProvider.")

        name = getattr(provider_cls, "name", None)
        if not name or not isinstance(name, str):
            raise ValueError(
                f"{provider_cls.__name__} must define a non-empty string attribute 'name'."
            )

        if name in self._providers:
            raise ValueError(f"Provider '{name}' is already registered.")

        self._providers[name] = provider_cls

    def unregister(self, name: str) -> None:
        """Remove provider by name."""
        self._providers.pop(name, None)

    def create(self, name: str, root: Path) -> BaseProvider:
        """Create a single provider instance."""
        if name not in self._providers:
            raise KeyError(f"Provider '{name}' is not registered.")
        return self._providers[name](root)

    def create_all(self, root: Path) -> list[BaseProvider]:
        """Create instances of all registered providers."""
        return [provider_cls(root) for provider_cls in self._providers.values()]

    def get(self, name: str) -> type[BaseProvider]:
        """Return provider class by name."""
        return self._providers[name]

    def all(self) -> list[type[BaseProvider]]:
        """Return all registered provider classes."""
        return list(self._providers.values())

    def names(self) -> list[str]:
        """Return sorted provider names."""
        return sorted(self._providers.keys())

    def exists(self, name: str) -> bool:
        return name in self._providers

    def clear(self) -> None:
        self._providers.clear()

    def __contains__(self, name: str) -> bool:
        return name in self._providers

    def __len__(self) -> int:
        return len(self._providers)

    def __iter__(self) -> Iterable[type[BaseProvider]]:
        return iter(self._providers.values())