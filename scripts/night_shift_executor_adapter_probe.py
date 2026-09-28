#!/usr/bin/env python
"""Execute the validated Night Shift deterministic-local adapter probe."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.enterprise import IsolationPolicy
from core.night_shift.executor_adapters import (
    ExecutorAdapterRegistry,
    ExecutorRequest,
    ProcessIsolationExecutorAdapter,
    load_executor_adapter_bindings,
)
from core.night_shift.executor_registry import load_executor_profiles
from core.night_shift.routing import route_executor

PROFILES = REPO_ROOT / "docs/execution_profiles/NIGHT_SHIFT_EXECUTOR_REGISTRY_V1.yaml"
BINDINGS = REPO_ROOT / "docs/execution_profiles/NIGHT_SHIFT_EXECUTOR_ADAPTERS_V1.yaml"
FIXTURE = "core.night_shift._executor_fixture"


def main() -> int:
    profiles = load_executor_profiles(PROFILES)
    bindings = load_executor_adapter_bindings(BINDINGS)
    profile = next(item for item in profiles if item.executor_id == "deterministic_local")
    adapter = ProcessIsolationExecutorAdapter(
        profile=profile,
        policy=IsolationPolicy(
            timeout_seconds=10.0,
            memory_bytes=512 * 1024 * 1024,
            cpu_seconds=2,
            network_allowed=False,
            allowed_entrypoints=(f"{FIXTURE}:canonical_echo",),
        ),
    )
    registry = ExecutorAdapterRegistry(
        profiles=profiles,
        bindings=bindings,
        adapters=(adapter,),
    )
    route = route_executor(
        required_capabilities=("git", "deterministic_validation"),
        executors=profiles,
        mutating=False,
    )
    result = registry.execute(
        route=route,
        request=ExecutorRequest(
            task_id="v208-adapter-probe",
            executor_id=route.executor_id,
            required_capabilities=("git", "deterministic_validation"),
            mutating=False,
            module=FIXTURE,
            function="canonical_echo",
            payload={"probe": "v2-08"},
        ),
    )
    print(
        json.dumps(
            {
                "task_id": "v208-adapter-probe",
                "executor_id": result.executor_id,
                "adapter_kind": result.adapter_kind,
                "request_digest": result.request_digest,
                "output_digest": result.output_digest,
                "isolation_digest": result.isolation_digest,
                "output": dict(result.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
