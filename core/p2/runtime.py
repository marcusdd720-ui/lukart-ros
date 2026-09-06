"""P2 bounded agent runtime, API contract, scalability and plugin ecosystem."""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import RLock
from typing import Callable, Generic, Mapping, Sequence, TypeVar


class RuntimeContractError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ExecutionBudget:
    max_steps: int = 16
    max_input_items: int = 1000

    def __post_init__(self) -> None:
        if self.max_steps < 1 or self.max_input_items < 1:
            raise RuntimeContractError("execution budgets must be positive")


@dataclass(frozen=True, slots=True)
class AgentTask:
    task_id: str
    required_capability: str
    payload: Mapping[str, object]
    budget: ExecutionBudget = ExecutionBudget()

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.required_capability.strip():
            raise RuntimeContractError("task_id and required_capability are required")
        if len(self.payload) > self.budget.max_input_items:
            raise RuntimeContractError("task payload exceeds max_input_items")


@dataclass(frozen=True, slots=True)
class AgentResult:
    task_id: str
    provider_id: str
    provider_version: str
    steps_used: int
    artifact: Mapping[str, object]


class Plugin(ABC):
    plugin_id: str = ""
    version: str = ""
    capabilities: frozenset[str] = frozenset()

    @classmethod
    def identity(cls) -> str:
        if not cls.plugin_id.strip() or not cls.version.strip():
            raise RuntimeContractError("plugin identity is incomplete")
        return f"{cls.plugin_id}@{cls.version}"


class AgentProvider(Plugin):
    @classmethod
    @abstractmethod
    def execute(cls, task: AgentTask) -> AgentResult:
        raise NotImplementedError


P = TypeVar("P", bound=Plugin)


class PluginRegistry(Generic[P]):
    """Class-based registry; provider instances are never stored as authority."""

    def __init__(self) -> None:
        self._providers: dict[str, type[P]] = {}

    def register(self, provider: type[P]) -> None:
        identity = provider.identity()
        if identity in self._providers:
            raise RuntimeContractError(f"duplicate plugin identity: {identity}")
        self._providers[identity] = provider

    def providers(self) -> tuple[type[P], ...]:
        return tuple(self._providers[key] for key in sorted(self._providers))

    def by_capability(self, capability: str) -> tuple[type[P], ...]:
        return tuple(
            provider
            for provider in self.providers()
            if capability in provider.capabilities
        )


class BoundedAgentRuntime:
    def __init__(self, registry: PluginRegistry[AgentProvider]) -> None:
        self._registry = registry

    def run(self, task: AgentTask) -> AgentResult:
        providers = self._registry.by_capability(task.required_capability)
        if not providers:
            raise RuntimeContractError(
                f"no certified provider for capability: {task.required_capability}"
            )
        provider = providers[0]
        result = provider.execute(task)
        if result.task_id != task.task_id:
            raise RuntimeContractError("provider returned mismatched task_id")
        identity_matches = (
            result.provider_id == provider.plugin_id
            and result.provider_version == provider.version
        )
        if not identity_matches:
            raise RuntimeContractError("provider returned mismatched identity")
        if result.steps_used < 0 or result.steps_used > task.budget.max_steps:
            raise RuntimeContractError("provider exceeded execution step budget")
        return result


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ApiEnvelope:
    schema: str
    version: str
    payload: Mapping[str, object]
    payload_digest: str

    @classmethod
    def build(
        cls,
        *,
        schema: str,
        version: str,
        payload: Mapping[str, object],
    ) -> ApiEnvelope:
        if not schema.strip() or not version.strip():
            raise RuntimeContractError("API schema and version are required")
        copied = dict(payload)
        return cls(schema.strip(), version.strip(), copied, _digest(copied))

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema": self.schema,
                "version": self.version,
                "payload": self.payload,
                "payload_digest": self.payload_digest,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, raw: str) -> ApiEnvelope:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise RuntimeContractError("API envelope must be an object")
        payload = parsed.get("payload")
        if not isinstance(payload, dict):
            raise RuntimeContractError("API payload must be an object")
        envelope = cls(
            schema=str(parsed.get("schema", "")),
            version=str(parsed.get("version", "")),
            payload=payload,
            payload_digest=str(parsed.get("payload_digest", "")),
        )
        if not envelope.schema or not envelope.version:
            raise RuntimeContractError("API schema and version are required")
        if envelope.payload_digest != _digest(payload):
            raise RuntimeContractError("API payload digest mismatch")
        return envelope


K = TypeVar("K")
V = TypeVar("V")


class LruArtifactCache(Generic[K, V]):
    def __init__(self, capacity: int = 128) -> None:
        if capacity < 1:
            raise RuntimeContractError("cache capacity must be positive")
        self._capacity = capacity
        self._items: OrderedDict[K, V] = OrderedDict()
        self._lock = RLock()

    def get(self, key: K) -> V | None:
        with self._lock:
            if key not in self._items:
                return None
            value = self._items.pop(key)
            self._items[key] = value
            return value

    def put(self, key: K, value: V) -> None:
        with self._lock:
            if key in self._items:
                self._items.pop(key)
            self._items[key] = value
            while len(self._items) > self._capacity:
                self._items.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


T = TypeVar("T")
R = TypeVar("R")


def bounded_parallel_map(
    function: Callable[[T], R],
    items: Sequence[T],
    *,
    max_workers: int = 4,
) -> tuple[R, ...]:
    if max_workers < 1:
        raise RuntimeContractError("max_workers must be positive")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return tuple(executor.map(function, items))
