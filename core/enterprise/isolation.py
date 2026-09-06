"""E2/H4 process and capability isolation boundary for untrusted worker execution.

The executor enforces a real child-process lifetime boundary, hard parent-side termination,
resource limits where the host exposes them, environment sanitization, a temporary workspace and
a Python audit-hook capability policy for filesystem/network/process/native-FFI operations.

This is intentionally not described as a kernel/container sandbox. The returned controls report
exactly which boundary controls were enforced so callers cannot silently promote a weaker runtime
boundary into a stronger security claim.
"""

from __future__ import annotations

import importlib
import multiprocessing
import os
import queue
import socket
import sys
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from core.p3.contracts import content_digest

from .contracts import EnterpriseContractError

_ROOT = Path(__file__).resolve().parents[2]


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
    allowed_read_roots: tuple[str, ...] = ()
    process_spawn_allowed: bool = False
    native_ffi_allowed: bool = False
    workspace_write_only: bool = True

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
        read_roots = tuple(
            sorted(
                {
                    str(Path(item).expanduser().resolve(strict=False))
                    for item in self.allowed_read_roots
                    if item.strip()
                }
            )
        )
        if len(read_roots) != len({item for item in self.allowed_read_roots if item.strip()}):
            raise EnterpriseContractError("filesystem read-root allow-list is ambiguous")
        object.__setattr__(self, "allowed_entrypoints", entrypoints)
        object.__setattr__(self, "allowed_environment_keys", env_keys)
        object.__setattr__(self, "allowed_read_roots", read_roots)


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
    filesystem_control: str
    process_control: str
    native_ffi_control: str
    audit_hook_enforced: bool
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


def _path_from_audit(value: object, *, cwd: Path) -> Path | None:
    if value is None or isinstance(value, int):
        return None
    try:
        raw = os.fspath(value)
    except TypeError:
        return None
    if isinstance(raw, bytes):
        raw = os.fsdecode(raw)
    path = Path(raw)
    if not path.is_absolute():
        path = cwd / path
    return path.resolve(strict=False)


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _open_is_write(mode: object, flags: object) -> bool:
    if isinstance(mode, str) and any(marker in mode for marker in ("w", "a", "x", "+")):
        return True
    if isinstance(flags, int):
        mask = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
        return bool(flags & mask)
    return False


def _default_read_roots() -> tuple[Path, ...]:
    roots = {
        _ROOT.resolve(strict=False),
        Path(sys.prefix).resolve(strict=False),
        Path(sys.base_prefix).resolve(strict=False),
    }
    return tuple(sorted(roots, key=str))


def _capability_audit_hook(
    *,
    workspace: Path,
    read_roots: tuple[Path, ...],
    network_allowed: bool,
    process_spawn_allowed: bool,
    native_ffi_allowed: bool,
    workspace_write_only: bool,
) -> Callable[[str, tuple[object, ...]], None]:
    workspace = workspace.resolve(strict=False)
    readable = tuple(dict.fromkeys((workspace, *read_roots)))

    def require_readable(value: object) -> None:
        path = _path_from_audit(value, cwd=Path.cwd())
        if path is None:
            return
        if not any(_is_within(path, root) for root in readable):
            raise PermissionError(f"filesystem read denied by LUKART worker policy: {path}")

    def require_workspace(value: object) -> None:
        path = _path_from_audit(value, cwd=Path.cwd())
        if path is None:
            return
        if workspace_write_only and not _is_within(path, workspace):
            raise PermissionError(f"filesystem write denied by LUKART worker policy: {path}")

    def audit(event: str, args: tuple[object, ...]) -> None:
        if event.startswith("socket.") and not network_allowed:
            raise PermissionError("network access denied by LUKART worker capability policy")

        if not process_spawn_allowed and (
            event.startswith("subprocess.")
            or event in {
                "os.system",
                "os.posix_spawn",
                "os.fork",
                "os.forkpty",
                "pty.spawn",
            }
            or event.startswith("os.spawn")
        ):
            raise PermissionError("process spawn denied by LUKART worker capability policy")

        if event.startswith("ctypes.") and not native_ffi_allowed:
            raise PermissionError("native FFI denied by LUKART worker capability policy")

        if event == "open":
            path = args[0] if args else None
            mode = args[1] if len(args) > 1 else None
            flags = args[2] if len(args) > 2 else None
            if _open_is_write(mode, flags):
                require_workspace(path)
            else:
                require_readable(path)
            return

        if event in {"os.listdir", "os.scandir", "os.chdir"}:
            require_readable(args[0] if args else None)
            return

        if event in {
            "os.remove",
            "os.unlink",
            "os.rmdir",
            "os.mkdir",
            "os.chmod",
            "os.chown",
            "os.utime",
            "os.truncate",
            "os.symlink",
        }:
            require_workspace(args[0] if args else None)
            return

        if event in {"os.rename", "os.replace", "os.link"}:
            require_workspace(args[0] if args else None)
            require_workspace(args[1] if len(args) > 1 else None)

    return audit


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
    os.environ["LUKART_PROCESS_POLICY"] = (
        "allow" if policy.process_spawn_allowed else "deny"
    )
    os.environ["LUKART_NATIVE_FFI_POLICY"] = (
        "allow" if policy.native_ffi_allowed else "deny"
    )

    memory_limit, cpu_limit = _apply_posix_limits(policy.memory_bytes, policy.cpu_seconds)

    try:
        with tempfile.TemporaryDirectory(prefix="lukart-worker-") as workspace_text:
            workspace = Path(workspace_text).resolve(strict=False)
            os.chdir(workspace)
            sys.dont_write_bytecode = True
            read_roots = tuple(
                dict.fromkeys(
                    (
                        *_default_read_roots(),
                        *(Path(item).resolve(strict=False) for item in policy.allowed_read_roots),
                    )
                )
            )
            sys.addaudithook(
                _capability_audit_hook(
                    workspace=workspace,
                    read_roots=read_roots,
                    network_allowed=policy.network_allowed,
                    process_spawn_allowed=policy.process_spawn_allowed,
                    native_ffi_allowed=policy.native_ffi_allowed,
                    workspace_write_only=policy.workspace_write_only,
                )
            )
            if not policy.network_allowed:
                _deny_network()

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
                "allowed"
                if self.policy.network_allowed
                else "python-audit-hook+socket-guard"
            ),
            filesystem_control=(
                "python-audit-hook-read-roots-workspace-write-only"
                if self.policy.workspace_write_only
                else "python-audit-hook-read-roots"
            ),
            process_control=(
                "allowed" if self.policy.process_spawn_allowed else "python-audit-hook-deny"
            ),
            native_ffi_control=(
                "allowed" if self.policy.native_ffi_allowed else "python-audit-hook-deny"
            ),
            audit_hook_enforced=True,
            kernel_sandbox=False,
        )
        return IsolatedResult(
            task_digest=task_digest,
            output=output,
            output_digest=content_digest(output),
            controls=controls,
            elapsed_seconds=elapsed,
        )
