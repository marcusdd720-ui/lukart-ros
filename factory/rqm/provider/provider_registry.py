from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Type

from factory.rqm.provider.base_provider import BaseProvider


class ProviderRegistry:
    """
    Central registry for Release Quality Manager providers.
    """

    def __init__(self) -> None:
        self._providers: Dict[str, Type[BaseProvider]] = {}

    def register(self, provider_cls: Type[BaseProvider]) -> None:
        """
        Register a provider class.
        """
        if not issubclass(provider_cls, BaseProvider):
            raise TypeError(
                f"{provider_cls.__name__} must inherit from BaseProvider."
            )

        name = provider_cls(Path()).name

        if name in self._providers:
            raise ValueError(
                f"Provider '{name}' is already registered."
            )

        self._providers[name] = provider_cls

    def unregister(self, name: str) -> None:
        """
        Remove a provider from the registry.
        """
        self._providers.pop(name, None)

    def create(self, name: str, root: Path) -> BaseProvider:
        """
        Create a single provider instance.
        """
        return self._providers[name](root)

    def create_all(self, root: Path) -> list[BaseProvider]:
        """
        Create all enabled providers.
        """
        providers: list[BaseProvider] = []

        for provider_cls in self._providers.values():
            provider = provider_cls(root)

            if provider.enabled:
                providers.append(provider)

        return providers

    def get(self, name: str) -> Type[BaseProvider]:
        """
        Return a registered provider class.
        """
        return self._providers[name]

    def all(self) -> Iterable[Type[BaseProvider]]:
        """
        Iterate over registered provider classes.
        """
        return self._providers.values()

    def names(self) -> list[str]:
        """
        Return provider names in alphabetical order.
        """
        return sorted(self._providers.keys())

    def clear(self) -> None:
        """
        Remove all registered providers.
        """
        self._providers.clear()

    def __contains__(self, name: str) -> bool:
        return name in self._providers

    def __len__(self) -> int:
        return len(self._providers)

    def __iter__(self):
        return iter(self._providers.values())


registry = ProviderRegistry()