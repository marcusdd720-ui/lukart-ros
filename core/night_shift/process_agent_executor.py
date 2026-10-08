"""Bounded real child-process executor for zero-cost local agents.

This adapter is intentionally provider-neutral. It launches one allow-listed executable
without a shell, binds it to a workspace root, records child identity and meaningful
progress markers, and fails closed on timeout/non-zero exit/no progress.
"""

from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from core.p3.contracts import content_digest

from .contracts import NightShiftContractError


@dataclass(frozen=True, slots=True)
class ProcessAgentRequest:
    task_id: str
    command: tuple[str, ...]
    workspace: str
    mutating: bool
    timeout_seconds: float = 120.0
    progress_prefix: str = "LUKART_PROGRESS:"

    def __post_init__(self) -> None:
        task_id = self.task_id.strip()
        command = tuple(part.strip() for part in self.command)
        workspace = self.workspace.strip()
        prefix = self.progress_prefix.strip()
        if not task_id or not command or any(not part for part in command):
            raise NightShiftContractError("process-agent task/command is invalid")
        if not workspace:
            raise NightShiftContractError("process-agent workspace is required")
        if self.timeout_seconds <= 0:
            raise NightShiftContractError("process-agent timeout must be positive")
        if not prefix:
            raise NightShiftContractError("progress prefix is required")
        object.__setattr__(self, "task_id", task_id)
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "workspace", workspace)
        object.__setattr__(self, "progress_prefix", prefix)

    def digest(self) -> str:
        return content_digest(
            {
                "task_id": self.task_id,
                "command": list(self.command),
                "workspace": self.workspace,
                "mutating": self.mutating,
                "timeout_seconds": self.timeout_seconds,
                "progress_prefix": self.progress_prefix,
            }
        )


@dataclass(frozen=True, slots=True)
class ProcessAgentResult:
    task_id: str
    run_id: str
    child_pid: int
    request_digest: str
    exit_code: int
    progress_events: tuple[str, ...]
    stdout_tail: tuple[str, ...]
    stderr_tail: tuple[str, ...]
    elapsed_seconds: float
    output_digest: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0 and bool(self.progress_events)


class BoundedProcessAgentExecutor:
    """Launch an allow-listed real child process and preserve liveness evidence."""

    def __init__(
        self,
        *,
        executor_id: str,
        workspace_root: str | Path,
        allowed_executables: tuple[str, ...],
        mutating: bool,
        independent_review: bool,
        tail_lines: int = 100,
    ) -> None:
        executor_id = executor_id.strip()
        root = Path(workspace_root).resolve(strict=False)
        allowed = tuple(sorted({Path(item).name.lower() for item in allowed_executables if item.strip()}))
        if not executor_id or not allowed:
            raise NightShiftContractError("process-agent executor identity/allowlist is invalid")
        if tail_lines < 1:
            raise NightShiftContractError("tail_lines must be positive")
        self.executor_id = executor_id
        self.workspace_root = root
        self.allowed_executables = allowed
        self.mutating = mutating
        self.independent_review = independent_review
        self.tail_lines = tail_lines

    def _workspace(self, value: str) -> Path:
        path = Path(value).resolve(strict=False)
        if path != self.workspace_root and self.workspace_root not in path.parents:
            raise NightShiftContractError("workspace escapes configured root")
        if not path.is_dir():
            raise NightShiftContractError("workspace does not exist")
        return path

    def execute(self, request: ProcessAgentRequest) -> ProcessAgentResult:
        if request.mutating and not self.mutating:
            raise NightShiftContractError("executor is not authorized for mutation")
        executable = Path(request.command[0]).name.lower()
        if executable not in self.allowed_executables:
            raise NightShiftContractError("process-agent executable is not allow-listed")
        workspace = self._workspace(request.workspace)

        run_id = str(uuid4())
        env = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "PYTHONPATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME"}
        }
        env["LUKART_AGENT_RUN_ID"] = run_id
        env["LUKART_AGENT_TASK_ID"] = request.task_id
        env["LUKART_AGENT_MUTATING"] = "1" if request.mutating else "0"

        started = time.monotonic()
        process = subprocess.Popen(
            request.command,
            cwd=workspace,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            shell=False,
        )
        if process.stdout is None or process.stderr is None:
            process.kill()
            raise NightShiftContractError("process-agent streams unavailable")

        events: queue.Queue[tuple[str, str]] = queue.Queue()

        def pump(name: str, stream) -> None:
            try:
                for line in iter(stream.readline, ""):
                    events.put((name, line.rstrip("\r\n")))
            finally:
                stream.close()

        threads = (
            threading.Thread(target=pump, args=("stdout", process.stdout), daemon=True),
            threading.Thread(target=pump, args=("stderr", process.stderr), daemon=True),
        )
        for thread in threads:
            thread.start()

        stdout: list[str] = []
        stderr: list[str] = []
        progress: list[str] = []
        deadline = started + request.timeout_seconds

        while True:
            now = time.monotonic()
            if now >= deadline and process.poll() is None:
                process.kill()
                process.wait(timeout=5)
                raise NightShiftContractError("process-agent hard timeout")

            try:
                source, line = events.get(timeout=0.05)
                if source == "stdout":
                    stdout.append(line)
                    if line.startswith(request.progress_prefix):
                        marker = line[len(request.progress_prefix):].strip()
                        if marker:
                            progress.append(marker)
                else:
                    stderr.append(line)
            except queue.Empty:
                pass

            if process.poll() is not None and events.empty() and all(not t.is_alive() for t in threads):
                break

        for thread in threads:
            thread.join(timeout=1)
        exit_code = int(process.returncode or 0)
        elapsed = time.monotonic() - started
        stdout_tail = tuple(stdout[-self.tail_lines :])
        stderr_tail = tuple(stderr[-self.tail_lines :])
        progress_events = tuple(progress)

        output_digest = content_digest(
            {
                "task_id": request.task_id,
                "run_id": run_id,
                "child_pid": process.pid,
                "exit_code": exit_code,
                "progress_events": list(progress_events),
                "stdout_tail": list(stdout_tail),
                "stderr_tail": list(stderr_tail),
            }
        )
        result = ProcessAgentResult(
            task_id=request.task_id,
            run_id=run_id,
            child_pid=process.pid,
            request_digest=request.digest(),
            exit_code=exit_code,
            progress_events=progress_events,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
            elapsed_seconds=elapsed,
            output_digest=output_digest,
        )
        if exit_code != 0:
            raise NightShiftContractError(
                f"process-agent exited non-zero: {exit_code}; stderr={stderr_tail[-3:]}"
            )
        if not progress_events:
            raise NightShiftContractError("process-agent produced no meaningful progress evidence")
        return result
