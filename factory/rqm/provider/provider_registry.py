"""Central registry for RQM providers."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from factory.rqm.provider.audit_provider import AuditProvider
from factory.rqm.provider.base_provider import BaseProvider
from factory.rqm.provider.pytest_provider import PytestProvider


class ProviderRegistry:
    """Stores provider classes, not instances."""

    def __init__(self) -> None:
        self._providers: dict[str, type[BaseProvider]] = {}

    @staticmethod
    def _resolve_name(provider_cls: type[BaseProvider]) -> str:
        for key in ("provider_name", "NAME"):
            value = provider_cls.__dict__.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        value = provider_cls.__dict__.get("name")
        if isinstance(value, str) and value.strip():
            return value.strip()

        raise ValueError(
            f"{provider_cls.__name__} must define a non-empty string "
            f"class attribute 'provider_name' (or string 'name')."
        )

    @classmethod
    def default(cls) -> ProviderRegistry:
        registry = cls()
        registry.register(PytestProvider)
        registry.register(AuditProvider)
        return registry

    def register(self, provider_cls: type[BaseProvider]) -> None:
        if not issubclass(provider_cls, BaseProvider):
            raise TypeError(f"{provider_cls.__name__} must inherit from BaseProvider.")

        name = self._resolve_name(provider_cls)

        if name in self._providers:
            raise ValueError(f"Provider '{name}' is already registered.")

        self._providers[name] = provider_cls

    def unregister(self, name: str) -> None:
        self._providers.pop(name, None)

    def create(self, name: str, root: Path) -> BaseProvider:
        if name not in self._providers:
            raise KeyError(f"Provider '{name}' is not registered.")
        return self._providers[name](root)

    def create_all(self, root: Path) -> list[BaseProvider]:
        return [provider_cls(root) for provider_cls in self._providers.values()]

    def get(self, name: str) -> type[BaseProvider]:
        return self._providers[name]

    def all(self) -> list[type[BaseProvider]]:
        return list(self._providers.values())

    def names(self) -> list[str]:
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