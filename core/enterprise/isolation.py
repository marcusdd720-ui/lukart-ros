"""E2 process isolation boundary for untrusted agent/plugin execution.

This module enforces a real child-process lifetime boundary and hard parent-side termination.
It does not claim a kernel/container sandbox. POSIX resource limits and the Python socket guard are
reported explicitly so callers can distinguish enforced controls from unavailable controls.
"""

from __future__ import annotations

import importlib
import multiprocessing
import os
import queue
import socket
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass

from core.p3.contracts import content_digest

from .contracts import EnterpriseContractError


@dataclass(frozen=True, slots=True)
class IsolationPolicy:
    timeout_seconds: float
    memory_bytes: int
    cpu_seconds: int
    network_allowed: bool
    allowed_entrypoints: tuple[str, ...]
    allowed_environment_keys: tuple[str, ...] = (
        "PATH",
        "PYTHONPATH",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
    )

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise EnterpriseContractError("isolation timeout must be positive")
        if self.memory_bytes < 16 * 1024 * 1024:
            raise EnterpriseContractError("memory limit is unrealistically small")
        if self.cpu_seconds < 1:
            raise EnterpriseContractError("cpu_seconds must be positive")
        entrypoints = tuple(sorted({item.strip() for item in self.allowed_entrypoints}))
        if not entrypoints or any(not item or ":" not in item for item in entrypoints):
            raise EnterpriseContractError("at least one module:function entrypoint is required")
        env_keys = tuple(sorted({item.strip() for item in self.allowed_environment_keys}))
        if any(not item for item in env_keys):
            raise EnterpriseContractError("environment key allow-list cannot contain blanks")
        object.__setattr__(self, "allowed_entrypoints", entrypoints)
        object.__setattr__(self, "allowed_environment_keys", env_keys)


@dataclass(frozen=True, slots=True)
class IsolatedTask:
    module: str
    function: str
    payload: Mapping[str, object]

    @property
    def entrypoint(self) -> str:
        return f"{self.module}:{self.function}"

    def digest(self) -> str:
        return content_digest(
            {
                "module": self.module,
                "function": self.function,
                "payload": dict(self.payload),
            }
        )


@dataclass(frozen=True, slots=True)
class IsolationControls:
    separate_process: bool
    hard_timeout_kill: bool
    environment_sanitized: bool
    temporary_workspace: bool
    posix_memory_limit: bool
    posix_cpu_limit: bool
    network_control: str
    kernel_sandbox: bool = False


@dataclass(frozen=True, slots=True)
class IsolatedResult:
    task_digest: str
    output: Mapping[str, object]
    output_digest: str
    controls: IsolationControls
    elapsed_seconds: float


class IsolatedExecutionError(EnterpriseContractError):
    pass


def _deny_network() -> None:
    def denied(*_args: object, **_kwargs: object) -> object:
        raise PermissionError("network access denied by LUKART worker policy")

    setattr(socket, "socket", denied)
    setattr(socket, "create_connection", denied)
    setattr(socket, "getaddrinfo", denied)


def _apply_posix_limits(memory_bytes: int, cpu_seconds: int) -> tuple[bool, bool]:
    try:
        import resource
    except ImportError:
        return False, False

    memory_enforced = False
    cpu_enforced = False
    try:
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        memory_enforced = True
    except (OSError, ValueError):
        memory_enforced = False
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        cpu_enforced = True
    except (OSError, ValueError):
        cpu_enforced = False
    return memory_enforced, cpu_enforced


def _worker_entry(
    result_queue: multiprocessing.Queue[dict[str, object]],
    task: IsolatedTask,
    policy: IsolationPolicy,
) -> None:
    allowed = set(policy.allowed_environment_keys)
    for key in tuple(os.environ):
        if key not in allowed:
            os.environ.pop(key, None)
    os.environ["LUKART_WORKER_ISOLATION"] = "process"
    os.environ["LUKART_NETWORK_POLICY"] = "allow" if policy.network_allowed else "deny"

    memory_limit, cpu_limit = _apply_posix_limits(policy.memory_bytes, policy.cpu_seconds)
    if not policy.network_allowed:
        _deny_network()

    try:
        with tempfile.TemporaryDirectory(prefix="lukart-worker-") as workspace:
            os.chdir(workspace)
            module = importlib.import_module(task.module)
            function = getattr(module, task.function, None)
            if not callable(function):
                raise IsolatedExecutionError("worker entrypoint is not callable")
            raw = function(dict(task.payload))
            if not isinstance(raw, Mapping):
                raise IsolatedExecutionError("worker output must be a mapping")
            output = dict(raw)
            content_digest(output)
            result_queue.put(
                {
                    "ok": True,
                    "output": output,
                    "memory_limit": memory_limit,
                    "cpu_limit": cpu_limit,
                }
            )
    except BaseException as exc:  # child boundary must return a bounded error, not a traceback
        result_queue.put(
            {
                "ok": False,
                "error_type": type(exc).__name__,
                "error": str(exc)[:500],
                "memory_limit": memory_limit,
                "cpu_limit": cpu_limit,
            }
        )


class ProcessIsolationExecutor:
    def __init__(self, policy: IsolationPolicy) -> None:
        self.policy = policy

    def run(self, task: IsolatedTask) -> IsolatedResult:
        if task.entrypoint not in self.policy.allowed_entrypoints:
            raise IsolatedExecutionError("worker entrypoint is not allow-listed")
        task_digest = task.digest()
        context = multiprocessing.get_context("spawn")
        result_queue: multiprocessing.Queue[dict[str, object]] = context.Queue(maxsize=1)
        process = context.Process(
            target=_worker_entry,
            args=(result_queue, task, self.policy),
            daemon=True,
        )
        started = time.monotonic()
        process.start()
        process.join(self.policy.timeout_seconds)
        if process.is_alive():
            process.terminate()
            process.join(1.0)
            if process.is_alive() and hasattr(process, "kill"):
                process.kill()
                process.join(1.0)
            raise IsolatedExecutionError("worker hard timeout; process terminated")

        elapsed = time.monotonic() - started
        try:
            message = result_queue.get(timeout=1.0)
        except queue.Empty as exc:
            raise IsolatedExecutionError(
                f"worker exited without result; exitcode={process.exitcode}"
            ) from exc
        finally:
            result_queue.close()

        if message.get("ok") is not True:
            error_type = str(message.get("error_type", "WorkerError"))
            error = str(message.get("error", "worker failed"))
            raise IsolatedExecutionError(f"{error_type}: {error}")

        output = message.get("output")
        if not isinstance(output, dict):
            raise IsolatedExecutionError("worker result contract violated")
        controls = IsolationControls(
            separate_process=True,
            hard_timeout_kill=True,
            environment_sanitized=True,
            temporary_workspace=True,
            posix_memory_limit=bool(message.get("memory_limit")),
            posix_cpu_limit=bool(message.get("cpu_limit")),
            network_control=(
                "allowed" if self.policy.network_allowed else "python-runtime-guard"
            ),
            kernel_sandbox=False,
        )
        return IsolatedResult(
            task_digest=task_digest,
            output=output,
            output_digest=content_digest(output),
            controls=controls,
            elapsed_seconds=elapsed,
        )
