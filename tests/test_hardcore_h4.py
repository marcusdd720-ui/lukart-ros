from __future__ import annotations

from pathlib import Path

import pytest

from core.enterprise import (
    IsolatedExecutionError,
    IsolatedTask,
    IsolationPolicy,
    ProcessIsolationExecutor,
)

WORKER_MODULE = "core.enterprise._worker_fixture"


def _policy(
    *functions: str,
    allowed_read_roots: tuple[str, ...] = (),
) -> IsolationPolicy:
    return IsolationPolicy(
        timeout_seconds=3.0,
        memory_bytes=512 * 1024 * 1024,
        cpu_seconds=2,
        network_allowed=False,
        allowed_entrypoints=tuple(f"{WORKER_MODULE}:{name}" for name in functions),
        allowed_read_roots=allowed_read_roots,
        process_spawn_allowed=False,
        native_ffi_allowed=False,
        workspace_write_only=True,
    )


def _run(executor: ProcessIsolationExecutor, function: str, payload: dict[str, object]) -> object:
    return executor.run(
        IsolatedTask(
            module=WORKER_MODULE,
            function=function,
            payload=payload,
        )
    )


def test_h4_reports_actual_capability_controls_without_kernel_claim() -> None:
    result = _run(ProcessIsolationExecutor(_policy("echo")), "echo", {"value": 7})

    assert result.output["echo"] == {"value": 7}
    assert result.controls.separate_process is True
    assert result.controls.hard_timeout_kill is True
    assert result.controls.environment_sanitized is True
    assert result.controls.temporary_workspace is True
    assert result.controls.audit_hook_enforced is True
    assert result.controls.network_control == "python-audit-hook+socket-guard"
    assert (
        result.controls.filesystem_control
        == "python-audit-hook-read-roots-workspace-write-only"
    )
    assert result.controls.process_control == "python-audit-hook-deny"
    assert result.controls.native_ffi_control == "python-audit-hook-deny"
    assert result.controls.kernel_sandbox is False


def test_h4_environment_secret_does_not_cross_worker_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LUKART_H4_SECRET", "must-not-cross")
    result = _run(
        ProcessIsolationExecutor(_policy("environment_snapshot")),
        "environment_snapshot",
        {"key": "LUKART_H4_SECRET"},
    )
    assert result.output["value"] is None


def test_h4_denies_external_filesystem_read_by_default(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(IsolatedExecutionError, match="filesystem read denied"):
        _run(
            ProcessIsolationExecutor(_policy("filesystem_read")),
            "filesystem_read",
            {"path": str(outside)},
        )


def test_h4_allows_explicit_read_root_but_denies_write_outside_workspace(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("approved-read", encoding="utf-8")
    executor = ProcessIsolationExecutor(
        _policy(
            "filesystem_read",
            "filesystem_write",
            allowed_read_roots=(str(tmp_path),),
        )
    )

    read_result = _run(executor, "filesystem_read", {"path": str(outside)})
    assert read_result.output["text"] == "approved-read"

    with pytest.raises(IsolatedExecutionError, match="filesystem write denied"):
        _run(
            executor,
            "filesystem_write",
            {"path": str(outside), "text": "tamper"},
        )
    assert outside.read_text(encoding="utf-8") == "approved-read"


def test_h4_allows_workspace_local_write() -> None:
    result = _run(
        ProcessIsolationExecutor(_policy("filesystem_write")),
        "filesystem_write",
        {"path": "generated.txt", "text": "bounded"},
    )
    assert result.output == {"written": "bounded", "exists": True}


def test_h4_denies_process_spawn_and_native_ffi() -> None:
    executor = ProcessIsolationExecutor(_policy("process_spawn_probe", "native_ffi_probe"))

    with pytest.raises(IsolatedExecutionError, match="process spawn denied"):
        _run(executor, "process_spawn_probe", {})

    with pytest.raises(IsolatedExecutionError, match="native FFI denied"):
        _run(executor, "native_ffi_probe", {})


def test_h4_denies_network_capability() -> None:
    result = _run(ProcessIsolationExecutor(_policy("network_probe")), "network_probe", {})
    assert result.output["network"] == "denied"
