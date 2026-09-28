from __future__ import annotations

from pathlib import Path

import pytest

from core.enterprise import IsolationPolicy
from core.night_shift.contracts import NightShiftContractError
from core.night_shift.executor_adapters import (
    AdapterStatus,
    ExecutorAdapterBinding,
    ExecutorAdapterRegistry,
    ExecutorRequest,
    ProcessIsolationExecutorAdapter,
    load_executor_adapter_bindings,
)
from core.night_shift.executor_registry import load_executor_profiles
from core.night_shift.routing import route_executor

PROFILES = Path("docs/execution_profiles/NIGHT_SHIFT_EXECUTOR_REGISTRY_V1.yaml")
BINDINGS = Path("docs/execution_profiles/NIGHT_SHIFT_EXECUTOR_ADAPTERS_V1.yaml")
FIXTURE = "core.night_shift._executor_fixture"


def _inputs():
    profiles = load_executor_profiles(PROFILES)
    bindings = load_executor_adapter_bindings(BINDINGS)
    profile = next(item for item in profiles if item.executor_id == "deterministic_local")
    policy = IsolationPolicy(
        timeout_seconds=10.0,
        memory_bytes=512 * 1024 * 1024,
        cpu_seconds=2,
        network_allowed=False,
        allowed_entrypoints=(
            f"{FIXTURE}:canonical_echo",
            f"{FIXTURE}:attempt_network",
        ),
    )
    adapter = ProcessIsolationExecutorAdapter(profile=profile, policy=policy)
    registry = ExecutorAdapterRegistry(
        profiles=profiles,
        bindings=bindings,
        adapters=(adapter,),
    )
    return profiles, bindings, adapter, registry


def test_validated_local_adapter_executes_in_isolated_process() -> None:
    profiles, _, _, registry = _inputs()
    route = route_executor(
        required_capabilities=("git", "deterministic_validation"),
        executors=profiles,
        mutating=False,
    )
    request = ExecutorRequest(
        task_id="adapter-probe",
        executor_id=route.executor_id,
        required_capabilities=("git", "deterministic_validation"),
        mutating=False,
        module=FIXTURE,
        function="canonical_echo",
        payload={"value": 7},
    )

    result = registry.execute(route=route, request=request)

    assert result.executor_id == "deterministic_local"
    assert result.adapter_kind == "process_isolation"
    assert result.output["status"] == "PASS"
    assert result.output["payload"] == {"value": 7}
    assert len(result.output_digest) == 64
    assert len(result.isolation_digest) == 64


def test_documented_only_codex_adapter_fails_closed() -> None:
    profiles, _, _, registry = _inputs()
    route = route_executor(
        required_capabilities=("git", "bounded_code_change"),
        executors=profiles,
        mutating=True,
    )
    request = ExecutorRequest(
        task_id="writer-probe",
        executor_id=route.executor_id,
        required_capabilities=("git", "bounded_code_change"),
        mutating=True,
        module=FIXTURE,
        function="canonical_echo",
        payload={},
    )

    assert route.executor_id == "codex_adapter"
    with pytest.raises(NightShiftContractError, match="not validated"):
        registry.execute(route=route, request=request)


def test_read_only_adapter_rejects_mutating_request() -> None:
    profiles, _, _, registry = _inputs()
    route = route_executor(
        required_capabilities=("git", "deterministic_validation"),
        executors=profiles,
        mutating=False,
    )
    request = ExecutorRequest(
        task_id="mutation-probe",
        executor_id=route.executor_id,
        required_capabilities=("git",),
        mutating=True,
        module=FIXTURE,
        function="canonical_echo",
        payload={},
    )
    with pytest.raises(NightShiftContractError, match="forbids mutation"):
        registry.execute(route=route, request=request)


def test_adapter_process_denies_network() -> None:
    profiles, _, _, registry = _inputs()
    route = route_executor(
        required_capabilities=("git", "deterministic_validation"),
        executors=profiles,
        mutating=False,
    )
    request = ExecutorRequest(
        task_id="network-probe",
        executor_id=route.executor_id,
        required_capabilities=("git",),
        mutating=False,
        module=FIXTURE,
        function="attempt_network",
        payload={},
    )
    with pytest.raises(NightShiftContractError, match="isolated executor failed"):
        registry.execute(route=route, request=request)


def test_validated_binding_requires_implementation() -> None:
    profiles = load_executor_profiles(PROFILES)
    bindings = load_executor_adapter_bindings(BINDINGS)
    with pytest.raises(NightShiftContractError, match="requires implementation"):
        ExecutorAdapterRegistry(
            profiles=profiles,
            bindings=bindings,
            adapters=(),
        )


def test_documented_only_binding_cannot_expose_implementation() -> None:
    profiles, bindings, local_adapter, _ = _inputs()
    local_binding = next(
        item for item in bindings if item.executor_id == "deterministic_local"
    )
    downgraded = tuple(
        ExecutorAdapterBinding(
            item.executor_id,
            item.adapter_kind,
            AdapterStatus.DOCUMENTED_ONLY,
        )
        if item.executor_id == local_binding.executor_id
        else item
        for item in bindings
    )
    with pytest.raises(NightShiftContractError, match="cannot expose implementation"):
        ExecutorAdapterRegistry(
            profiles=profiles,
            bindings=downgraded,
            adapters=(local_adapter,),
        )


def test_route_and_request_executor_identity_must_match() -> None:
    profiles, _, _, registry = _inputs()
    route = route_executor(
        required_capabilities=("git", "deterministic_validation"),
        executors=profiles,
        mutating=False,
    )
    request = ExecutorRequest(
        task_id="identity-probe",
        executor_id="codex_adapter",
        required_capabilities=("git",),
        mutating=False,
        module=FIXTURE,
        function="canonical_echo",
        payload={},
    )
    with pytest.raises(NightShiftContractError, match="route executor"):
        registry.execute(route=route, request=request)


@pytest.mark.parametrize(
    (
        "network_allowed",
        "process_spawn_allowed",
        "native_ffi_allowed",
        "workspace_write_only",
        "match",
    ),
    (
        (True, False, False, True, "deny network access"),
        (False, True, False, True, "deny process spawning"),
        (False, False, True, True, "deny native FFI"),
        (False, False, False, False, "restrict writes to workspace"),
    ),
)
def test_reference_adapter_rejects_permissive_isolation_policy(
    network_allowed: bool,
    process_spawn_allowed: bool,
    native_ffi_allowed: bool,
    workspace_write_only: bool,
    match: str,
) -> None:
    profiles = load_executor_profiles(PROFILES)
    profile = next(item for item in profiles if item.executor_id == "deterministic_local")
    policy = IsolationPolicy(
        timeout_seconds=10.0,
        memory_bytes=512 * 1024 * 1024,
        cpu_seconds=2,
        network_allowed=network_allowed,
        allowed_entrypoints=(f"{FIXTURE}:canonical_echo",),
        process_spawn_allowed=process_spawn_allowed,
        native_ffi_allowed=native_ffi_allowed,
        workspace_write_only=workspace_write_only,
    )
    with pytest.raises(NightShiftContractError, match=match):
        ProcessIsolationExecutorAdapter(profile=profile, policy=policy)
