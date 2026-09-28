"""Provider-neutral executor adapter boundary for Night Shift."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

import yaml

from core.enterprise import (
    IsolatedExecutionError,
    IsolatedTask,
    IsolationPolicy,
    ProcessIsolationExecutor,
)
from core.p3.contracts import content_digest

from .config_validation import require_string
from .contracts import NightShiftContractError
from .executor_registry import ExecutorProfile
from .routing import RouteDecision


class AdapterStatus(StrEnum):
    VALIDATED = "VALIDATED"
    DOCUMENTED_ONLY = "DOCUMENTED_ONLY"
    DISABLED = "DISABLED"


@dataclass(frozen=True, slots=True)
class ExecutorAdapterBinding:
    executor_id: str
    adapter_kind: str
    status: AdapterStatus

    def __post_init__(self) -> None:
        executor_id = self.executor_id.strip()
        adapter_kind = self.adapter_kind.strip()
        if not executor_id or not adapter_kind:
            raise NightShiftContractError("executor adapter binding must be nonblank")
        object.__setattr__(self, "executor_id", executor_id)
        object.__setattr__(self, "adapter_kind", adapter_kind)


@dataclass(frozen=True, slots=True)
class ExecutorRequest:
    task_id: str
    executor_id: str
    required_capabilities: tuple[str, ...]
    mutating: bool
    module: str
    function: str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        task_id = self.task_id.strip()
        executor_id = self.executor_id.strip()
        module = self.module.strip()
        function = self.function.strip()
        capabilities = tuple(sorted({item.strip() for item in self.required_capabilities}))
        if (
            not task_id
            or not executor_id
            or not module
            or not function
            or not capabilities
            or any(not item for item in capabilities)
        ):
            raise NightShiftContractError("executor request identity/capabilities are invalid")
        object.__setattr__(self, "task_id", task_id)
        object.__setattr__(self, "executor_id", executor_id)
        object.__setattr__(self, "module", module)
        object.__setattr__(self, "function", function)
        object.__setattr__(self, "required_capabilities", capabilities)

    def digest(self) -> str:
        return content_digest(
            {
                "task_id": self.task_id,
                "executor_id": self.executor_id,
                "required_capabilities": list(self.required_capabilities),
                "mutating": self.mutating,
                "module": self.module,
                "function": self.function,
                "payload": dict(self.payload),
            }
        )


@dataclass(frozen=True, slots=True)
class ExecutorAdapterResult:
    executor_id: str
    adapter_kind: str
    request_digest: str
    output: Mapping[str, object]
    output_digest: str
    isolation_digest: str


class ExecutorAdapter(Protocol):
    @property
    def executor_id(self) -> str:
        ...

    @property
    def adapter_kind(self) -> str:
        ...

    @property
    def capabilities(self) -> tuple[str, ...]:
        ...

    @property
    def mutating(self) -> bool:
        ...

    def execute(self, request: ExecutorRequest) -> ExecutorAdapterResult:
        ...


class ProcessIsolationExecutorAdapter:
    """Validated read-only adapter backed by the enterprise process boundary."""

    def __init__(
        self,
        *,
        profile: ExecutorProfile,
        policy: IsolationPolicy,
    ) -> None:
        if profile.mutating:
            raise NightShiftContractError(
                "process-isolation reference adapter is read-only"
            )
        if not profile.enabled:
            raise NightShiftContractError("executor profile is disabled")
        if policy.network_allowed:
            raise NightShiftContractError(
                "process-isolation reference adapter must deny network access"
            )
        if policy.process_spawn_allowed:
            raise NightShiftContractError(
                "process-isolation reference adapter must deny process spawning"
            )
        if policy.native_ffi_allowed:
            raise NightShiftContractError(
                "process-isolation reference adapter must deny native FFI"
            )
        if not policy.workspace_write_only:
            raise NightShiftContractError(
                "process-isolation reference adapter must restrict writes to workspace"
            )
        self.profile = profile
        self.policy = policy
        self._executor = ProcessIsolationExecutor(policy)

    @property
    def executor_id(self) -> str:
        return self.profile.executor_id

    @property
    def adapter_kind(self) -> str:
        return "process_isolation"

    @property
    def capabilities(self) -> tuple[str, ...]:
        return self.profile.capabilities

    @property
    def mutating(self) -> bool:
        return False

    def execute(self, request: ExecutorRequest) -> ExecutorAdapterResult:
        if request.executor_id != self.executor_id:
            raise NightShiftContractError("request executor does not match adapter")
        if request.mutating:
            raise NightShiftContractError("read-only adapter cannot execute mutation")
        if not set(request.required_capabilities).issubset(set(self.capabilities)):
            raise NightShiftContractError("adapter lacks requested capabilities")
        try:
            isolated = self._executor.run(
                IsolatedTask(
                    module=request.module,
                    function=request.function,
                    payload=request.payload,
                )
            )
        except IsolatedExecutionError as exc:
            raise NightShiftContractError(f"isolated executor failed: {exc}") from exc

        controls = isolated.controls
        if not (
            controls.separate_process
            and controls.hard_timeout_kill
            and controls.environment_sanitized
            and controls.temporary_workspace
            and controls.audit_hook_enforced
            and controls.network_control == "python-runtime-guard"
            and controls.filesystem_control
            == "python-audit-hook-read-roots-workspace-write-only"
            and controls.process_control == "python-audit-hook-deny"
            and controls.native_ffi_control == "python-audit-hook-deny"
        ):
            raise NightShiftContractError("executor isolation controls are incomplete")
        isolation_digest = content_digest(
            {
                "separate_process": controls.separate_process,
                "hard_timeout_kill": controls.hard_timeout_kill,
                "environment_sanitized": controls.environment_sanitized,
                "temporary_workspace": controls.temporary_workspace,
                "network_control": controls.network_control,
                "filesystem_control": controls.filesystem_control,
                "process_control": controls.process_control,
                "native_ffi_control": controls.native_ffi_control,
                "audit_hook_enforced": controls.audit_hook_enforced,
                "kernel_sandbox": controls.kernel_sandbox,
            }
        )
        return ExecutorAdapterResult(
            executor_id=self.executor_id,
            adapter_kind=self.adapter_kind,
            request_digest=request.digest(),
            output=isolated.output,
            output_digest=isolated.output_digest,
            isolation_digest=isolation_digest,
        )


class ExecutorAdapterRegistry:
    def __init__(
        self,
        *,
        profiles: tuple[ExecutorProfile, ...],
        bindings: tuple[ExecutorAdapterBinding, ...],
        adapters: tuple[ExecutorAdapter, ...],
    ) -> None:
        self._profiles = {item.executor_id: item for item in profiles}
        if len(self._profiles) != len(profiles):
            raise NightShiftContractError("executor profiles must be unique")
        self._bindings = {item.executor_id: item for item in bindings}
        if len(self._bindings) != len(bindings):
            raise NightShiftContractError("executor adapter bindings must be unique")
        self._adapters = {item.executor_id: item for item in adapters}
        if len(self._adapters) != len(adapters):
            raise NightShiftContractError("executor adapters must be unique")
        self._validate()

    def _validate(self) -> None:
        for executor_id, binding in self._bindings.items():
            profile = self._profiles.get(executor_id)
            if profile is None:
                raise NightShiftContractError("adapter binding has no executor profile")
            adapter = self._adapters.get(executor_id)
            if binding.status is AdapterStatus.VALIDATED:
                if adapter is None:
                    raise NightShiftContractError(
                        "validated adapter binding requires implementation"
                    )
                if adapter.adapter_kind != binding.adapter_kind:
                    raise NightShiftContractError("adapter kind does not match binding")
                if adapter.mutating != profile.mutating:
                    raise NightShiftContractError(
                        "adapter mutation capability does not match profile"
                    )
                if not set(profile.capabilities).issubset(set(adapter.capabilities)):
                    raise NightShiftContractError(
                        "adapter capabilities do not satisfy executor profile"
                    )
            elif adapter is not None:
                raise NightShiftContractError(
                    "non-validated adapter binding cannot expose implementation"
                )

        undeclared = set(self._adapters) - set(self._bindings)
        if undeclared:
            raise NightShiftContractError("executor adapter implementation is undeclared")

    def execute(
        self,
        *,
        route: RouteDecision,
        request: ExecutorRequest,
    ) -> ExecutorAdapterResult:
        if route.executor_id != request.executor_id:
            raise NightShiftContractError("route executor does not match request")
        profile = self._profiles.get(route.executor_id)
        binding = self._bindings.get(route.executor_id)
        adapter = self._adapters.get(route.executor_id)
        if profile is None or not profile.enabled:
            raise NightShiftContractError("routed executor profile is unavailable")
        if binding is None:
            raise NightShiftContractError("routed executor has no adapter binding")
        if binding.status is not AdapterStatus.VALIDATED or adapter is None:
            raise NightShiftContractError("routed executor adapter is not validated")
        if request.mutating and not profile.mutating:
            raise NightShiftContractError("routed executor profile forbids mutation")
        if not set(request.required_capabilities).issubset(set(profile.capabilities)):
            raise NightShiftContractError("request exceeds routed executor capabilities")
        return adapter.execute(request)


def load_executor_adapter_bindings(
    path: str | Path,
) -> tuple[ExecutorAdapterBinding, ...]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("bindings"), list):
        raise NightShiftContractError("executor adapter registry must contain bindings")
    items: list[ExecutorAdapterBinding] = []
    for entry in raw["bindings"]:
        if not isinstance(entry, dict):
            raise NightShiftContractError("executor adapter binding must be a mapping")
        try:
            status = AdapterStatus(require_string(entry["status"], field_name="status"))
        except ValueError as exc:
            raise NightShiftContractError("invalid executor adapter status") from exc
        items.append(
            ExecutorAdapterBinding(
                executor_id=require_string(
                    entry["executor_id"], field_name="executor_id"
                ),
                adapter_kind=require_string(
                    entry["adapter_kind"], field_name="adapter_kind"
                ),
                status=status,
            )
        )
    if len({item.executor_id for item in items}) != len(items):
        raise NightShiftContractError("executor adapter bindings must be unique")
    return tuple(items)
