"""P3-07 production hardening around the existing P2 AgentProvider authority."""

from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from enum import StrEnum
from threading import BoundedSemaphore, Event, RLock

from core.p2.runtime import AgentProvider, AgentResult, AgentTask, PluginRegistry

from .contracts import P3ContractError, content_digest


class ProviderHealth(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


class RuntimeOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    CONTRACT_ERROR = "CONTRACT_ERROR"


@dataclass(frozen=True, slots=True)
class CapabilityPolicy:
    capability: str
    timeout_seconds: float
    max_concurrency: int
    certified_provider_identities: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.capability.strip():
            raise P3ContractError("capability cannot be blank")
        if self.timeout_seconds <= 0:
            raise P3ContractError("timeout_seconds must be positive")
        if self.max_concurrency < 1:
            raise P3ContractError("max_concurrency must be positive")
        identities = tuple(sorted({item.strip() for item in self.certified_provider_identities}))
        if not identities or any(not item for item in identities):
            raise P3ContractError("at least one certified provider identity is required")
        object.__setattr__(self, "certified_provider_identities", identities)


class CancellationToken:
    def __init__(self) -> None:
        self._event = Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()


@dataclass(frozen=True, slots=True)
class AgentAuditRecord:
    task_id: str
    capability: str
    provider_identity: str | None
    outcome: RuntimeOutcome
    input_digest: str
    output_digest: str | None
    detail: str


@dataclass(frozen=True, slots=True)
class HardenedAgentExecution:
    result: AgentResult
    audit: AgentAuditRecord


class HardenedAgentRuntime:
    """Fail-closed bounded runtime with deterministic healthy-provider fallback.

    Timeout and cancellation are orchestration controls, not process isolation.
    Provider code still executes in the host Python process; P4 may introduce a
    real worker/sandbox boundary.
    """

    isolation_level = "logical-thread-boundary"

    def __init__(
        self,
        registry: PluginRegistry[AgentProvider],
        policies: Mapping[str, CapabilityPolicy],
    ) -> None:
        self._registry = registry
        self._policies = dict(policies)
        if set(self._policies) != {policy.capability for policy in self._policies.values()}:
            raise P3ContractError("capability policy keys must match capability values")
        self._health: dict[str, ProviderHealth] = {}
        self._semaphores = {
            capability: BoundedSemaphore(policy.max_concurrency)
            for capability, policy in self._policies.items()
        }
        self._audit: list[AgentAuditRecord] = []
        self._lock = RLock()

    def set_health(self, provider_identity: str, health: ProviderHealth) -> None:
        with self._lock:
            self._health[provider_identity] = health

    def audit_records(self) -> tuple[AgentAuditRecord, ...]:
        with self._lock:
            return tuple(self._audit)

    def _record(self, record: AgentAuditRecord) -> None:
        with self._lock:
            self._audit.append(record)

    def _eligible(self, policy: CapabilityPolicy) -> tuple[type[AgentProvider], ...]:
        providers = []
        certified = set(policy.certified_provider_identities)
        for provider in self._registry.by_capability(policy.capability):
            identity = provider.identity()
            health = self._health.get(identity, ProviderHealth.HEALTHY)
            if identity in certified and health is not ProviderHealth.UNHEALTHY:
                providers.append(provider)
        return tuple(sorted(providers, key=lambda provider: provider.identity()))

    def run(
        self,
        task: AgentTask,
        *,
        cancellation: CancellationToken | None = None,
    ) -> HardenedAgentExecution:
        policy = self._policies.get(task.required_capability)
        if policy is None:
            raise P3ContractError(f"no capability policy: {task.required_capability}")
        token = cancellation or CancellationToken()
        input_digest = content_digest(dict(task.payload))
        if token.cancelled:
            record = AgentAuditRecord(
                task.task_id,
                task.required_capability,
                None,
                RuntimeOutcome.CANCELLED,
                input_digest,
                None,
                "cancelled before provider execution",
            )
            self._record(record)
            raise P3ContractError(record.detail)

        providers = self._eligible(policy)
        if not providers:
            record = AgentAuditRecord(
                task.task_id,
                task.required_capability,
                None,
                RuntimeOutcome.CONTRACT_ERROR,
                input_digest,
                None,
                "no healthy certified provider",
            )
            self._record(record)
            raise P3ContractError(record.detail)

        semaphore = self._semaphores[task.required_capability]
        if not semaphore.acquire(timeout=policy.timeout_seconds):
            record = AgentAuditRecord(
                task.task_id,
                task.required_capability,
                None,
                RuntimeOutcome.TIMEOUT,
                input_digest,
                None,
                "concurrency budget acquisition timed out",
            )
            self._record(record)
            raise P3ContractError(record.detail)

        try:
            failures: list[str] = []
            for provider in providers:
                if token.cancelled:
                    record = AgentAuditRecord(
                        task.task_id,
                        task.required_capability,
                        None,
                        RuntimeOutcome.CANCELLED,
                        input_digest,
                        None,
                        "cancelled before fallback provider execution",
                    )
                    self._record(record)
                    raise P3ContractError(record.detail)

                identity = provider.identity()
                executor = ThreadPoolExecutor(max_workers=1)
                future = executor.submit(provider.execute, task)
                try:
                    result = future.result(timeout=policy.timeout_seconds)
                except FutureTimeoutError:
                    future.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    failures.append(f"{identity}:timeout")
                    self.set_health(identity, ProviderHealth.DEGRADED)
                    self._record(
                        AgentAuditRecord(
                            task.task_id,
                            task.required_capability,
                            identity,
                            RuntimeOutcome.TIMEOUT,
                            input_digest,
                            None,
                            "provider execution timed out",
                        )
                    )
                    continue
                except Exception as exc:
                    executor.shutdown(wait=False, cancel_futures=True)
                    failures.append(f"{identity}:{type(exc).__name__}")
                    self.set_health(identity, ProviderHealth.DEGRADED)
                    self._record(
                        AgentAuditRecord(
                            task.task_id,
                            task.required_capability,
                            identity,
                            RuntimeOutcome.PROVIDER_ERROR,
                            input_digest,
                            None,
                            type(exc).__name__,
                        )
                    )
                    continue
                else:
                    executor.shutdown(wait=True)

                if token.cancelled:
                    record = AgentAuditRecord(
                        task.task_id,
                        task.required_capability,
                        identity,
                        RuntimeOutcome.CANCELLED,
                        input_digest,
                        None,
                        "cancelled after provider execution",
                    )
                    self._record(record)
                    raise P3ContractError(record.detail)

                if result.task_id != task.task_id:
                    failures.append(f"{identity}:task-id-mismatch")
                    continue
                if (result.provider_id, result.provider_version) != (
                    provider.plugin_id,
                    provider.version,
                ):
                    failures.append(f"{identity}:identity-mismatch")
                    continue
                if result.steps_used < 0 or result.steps_used > task.budget.max_steps:
                    failures.append(f"{identity}:step-budget")
                    continue

                output_digest = content_digest(dict(result.artifact))
                record = AgentAuditRecord(
                    task.task_id,
                    task.required_capability,
                    identity,
                    RuntimeOutcome.SUCCESS,
                    input_digest,
                    output_digest,
                    "provider result accepted as untrusted execution artifact",
                )
                self._record(record)
                return HardenedAgentExecution(result=result, audit=record)

            raise P3ContractError("all certified providers failed: " + ";".join(failures))
        finally:
            semaphore.release()
