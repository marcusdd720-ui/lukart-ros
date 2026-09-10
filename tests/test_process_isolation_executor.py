from __future__ import annotations

from core.enterprise import IsolatedTask, IsolationPolicy, ProcessIsolationExecutor

WORKER_MODULE = "core.enterprise._worker_fixture"


def test_spawn_executor_drains_large_result_before_waiting_for_exit() -> None:
    large_value = "x" * (1024 * 1024)
    policy = IsolationPolicy(
        timeout_seconds=10.0,
        memory_bytes=512 * 1024 * 1024,
        cpu_seconds=2,
        network_allowed=False,
        allowed_entrypoints=(f"{WORKER_MODULE}:echo",),
    )

    result = ProcessIsolationExecutor(policy).run(
        IsolatedTask(
            module=WORKER_MODULE,
            function="echo",
            payload={"blob": large_value},
        )
    )

    assert result.output["echo"] == {"blob": large_value}
    assert result.controls.separate_process is True
    assert result.controls.hard_timeout_kill is True
