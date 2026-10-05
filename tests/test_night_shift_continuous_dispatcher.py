from __future__ import annotations

import pytest

from core.night_shift.continuous_dispatcher import (
    DispatchTask,
    ExecutionState,
    ProviderCandidate,
    ProviderState,
    WorkerEvidence,
    authoritative_execution_state,
    executable_tasks,
    is_transient_tool_path,
    normalize_legacy_result,
    notification_suppressed,
    path_change_action,
    provider_benchmark_allowed,
    provider_unavailability_state,
    select_next_task,
    select_next_routed_task,
    select_zero_cost_provider,
)
from core.night_shift.contracts import NightShiftContractError
from core.night_shift.execution_exchange import (
    ExecutionRoute,
    QuotaReservationLedger,
    QuotaWindow,
    RouteStatus,
)


def test_ready_task_dispatches() -> None:
    selected = select_next_task((DispatchTask("a", 0),), now_epoch=10)
    assert selected is not None
    assert selected.task_id == "a"


def test_done_dependency_unlocks_next_task() -> None:
    tasks = (DispatchTask("a", 0, status="DONE"), DispatchTask("b", 1, depends_on=("a",)))
    selected = select_next_task(tasks, now_epoch=10)
    assert selected is not None
    assert selected.task_id == "b"


def test_unfinished_dependency_blocks() -> None:
    tasks = (DispatchTask("a", 0), DispatchTask("b", 1, depends_on=("a",)))
    assert [t.task_id for t in executable_tasks(tasks, now_epoch=10)] == ["a"]


def test_quiet_hours_are_not_execution_input() -> None:
    selected = select_next_task((DispatchTask("night", 0),), now_epoch=23 * 3600)
    assert selected is not None
    assert selected.task_id == "night"


def test_no_work_is_idle_no_work() -> None:
    d = authoritative_execution_state(ready_work_exists=False, worker=None, now_epoch=10)
    assert d.state is ExecutionState.IDLE_NO_WORK


def test_ready_work_without_worker_is_p0_recovery() -> None:
    d = authoritative_execution_state(ready_work_exists=True, worker=None, now_epoch=10)
    assert d.incident == "NO_EXECUTOR" and d.recover


def test_dead_worker_is_detected() -> None:
    w = WorkerEvidence("w", False, False, None, 10, 10)
    assert (
        authoritative_execution_state(ready_work_exists=True, worker=w, now_epoch=11).incident
        == "DEAD_PROCESS"
    )


def test_stale_heartbeat_is_detected() -> None:
    w = WorkerEvidence("w", True, False, None, 0, 10)
    assert (
        authoritative_execution_state(ready_work_exists=True, worker=w, now_epoch=200).incident
        == "STALE_HEARTBEAT"
    )


def test_shell_waiting_for_input_is_not_execution() -> None:
    w = WorkerEvidence("w", True, False, None, 10, 10, True)
    assert (
        authoritative_execution_state(ready_work_exists=True, worker=w, now_epoch=11).incident
        == "SHELL_WAITING_INPUT"
    )


def test_running_without_child_is_not_execution() -> None:
    w = WorkerEvidence("w", True, False, "t", 10, 10)
    assert (
        authoritative_execution_state(ready_work_exists=True, worker=w, now_epoch=11).incident
        == "RUNNING_WITHOUT_CHILD"
    )


def test_running_without_progress_is_detected() -> None:
    w = WorkerEvidence("w", True, True, "t", 500, 0)
    assert (
        authoritative_execution_state(ready_work_exists=True, worker=w, now_epoch=500).incident
        == "RUNNING_WITHOUT_PROGRESS"
    )


def test_real_execution_requires_child_and_fresh_progress() -> None:
    w = WorkerEvidence("w", True, True, "t", 100, 100)
    assert (
        authoritative_execution_state(ready_work_exists=True, worker=w, now_epoch=101).state
        is ExecutionState.EXECUTING
    )


def test_queued_with_alive_idle_worker_is_incident() -> None:
    w = WorkerEvidence("w", True, False, None, 100, 100)
    assert (
        authoritative_execution_state(ready_work_exists=True, worker=w, now_epoch=101).incident
        == "QUEUED_WITH_ZERO_EXECUTION"
    )


def test_cache_is_transient() -> None:
    assert is_transient_tool_path(".aider.tags.cache.v4/foo")


def test_protected_path_is_not_transient() -> None:
    assert not is_transient_tool_path(".github/workflows/ci.yml")


def test_attempts_over_budget_fail_closed() -> None:
    t = DispatchTask("a", 0, attempts=4, max_attempts=3)
    normalized = executable_tasks((t,), now_epoch=10)
    assert normalized == ()


def test_success_cannot_remain_blocked() -> None:
    t = normalize_legacy_result(
        DispatchTask("a", 0, status="BLOCKED"), last_detail="agent success provider=x"
    )
    assert t.status == "DONE"


def test_retry_future_not_selected() -> None:
    assert (
        select_next_task((DispatchTask("a", 0, status="RETRY", next_run_epoch=20),), now_epoch=10)
        is None
    )


def test_human_gate_only_blocks_that_task() -> None:
    tasks = (DispatchTask("a", 0, human_gate=True), DispatchTask("b", 1))
    selected = select_next_task(tasks, now_epoch=10)
    assert selected is not None
    assert selected.task_id == "b"


def test_external_gate_only_blocks_that_task() -> None:
    tasks = (DispatchTask("a", 0, external_gate=True), DispatchTask("b", 1))
    selected = select_next_task(tasks, now_epoch=10)
    assert selected is not None
    assert selected.task_id == "b"


def test_write_worktree_collision_rejected() -> None:
    tasks = (DispatchTask("a", 0, worktree="x", write_task=True), DispatchTask("b", 1))
    selected = select_next_task(tasks, now_epoch=10, active_write_worktrees=frozenset({"x"}))
    assert selected is not None
    assert selected.task_id == "b"


def test_zero_cost_provider_fallback() -> None:
    providers = (
        ProviderCandidate(
            "quota", ProviderState.QUOTA_EXHAUSTED, frozenset({"code"}), True, True, 100
        ),
        ProviderCandidate("free", ProviderState.AVAILABLE, frozenset({"code"}), True, True, 50),
    )
    selected = select_zero_cost_provider(providers, required_capability="code", private_data=False)
    assert selected is not None
    assert selected.provider_id == "free"


def test_unverified_free_provider_rejected() -> None:
    providers = (
        ProviderCandidate("x", ProviderState.AVAILABLE, frozenset({"code"}), True, False, 100),
    )
    assert (
        select_zero_cost_provider(providers, required_capability="code", private_data=False) is None
    )


def test_private_data_requires_privacy_eligibility() -> None:
    providers = (
        ProviderCandidate(
            "external", ProviderState.AVAILABLE, frozenset({"code"}), False, True, 100
        ),
        ProviderCandidate(
            "private",
            ProviderState.AVAILABLE,
            frozenset({"code"}),
            True,
            True,
            10,
            external=False,
        ),
    )
    selected = select_zero_cost_provider(providers, required_capability="code", private_data=True)
    assert selected is not None
    assert selected.provider_id == "private"


def test_invalid_attempts_fail_closed() -> None:
    with pytest.raises(NightShiftContractError, match="attempts"):
        DispatchTask("a", 0, attempts=-1)


def test_quiet_hours_only_suppress_notifications() -> None:
    assert notification_suppressed(hour=23)
    assert not notification_suppressed(hour=12)
    assert select_next_task((DispatchTask("night", 0),), now_epoch=23 * 3600) is not None


def test_transient_cache_does_not_quarantine() -> None:
    assert path_change_action(".aider.tags.cache.v4/index") == "IGNORE_TRANSIENT"


def test_protected_path_fails_closed_to_quarantine() -> None:
    assert path_change_action(".github/workflows/ci.yml") == "QUARANTINE"
    assert path_change_action("config/worker.json") == "QUARANTINE"


def test_all_providers_unavailable_waits_then_blocks_at_budget() -> None:
    assert provider_unavailability_state(attempts=1, max_attempts=3) is ExecutionState.WAITING_RETRY
    assert (
        provider_unavailability_state(attempts=3, max_attempts=3)
        is ExecutionState.BLOCKED_TECHNICAL
    )


def test_external_provider_never_receives_private_customer_data() -> None:
    providers = (
        ProviderCandidate(
            "external",
            ProviderState.AVAILABLE,
            frozenset({"code"}),
            True,
            True,
            100,
            external=True,
        ),
    )
    assert (
        select_zero_cost_provider(
            providers,
            required_capability="code",
            private_data=True,
        )
        is None
    )


def test_provider_benchmark_requires_synthetic_data() -> None:
    assert provider_benchmark_allowed("SYNTHETIC")
    assert not provider_benchmark_allowed("CUSTOMER")
    assert not provider_benchmark_allowed("PRIVATE")

def _lex_route(
    route_id: str,
    *,
    provider_id: str,
    now: int,
    capability: str = "code",
    privacy_classes: frozenset[str] = frozenset({"SYNTHETIC", "PUBLIC"}),
    remaining_requests: int = 10,
    remaining_tokens: int = 10_000,
) -> ExecutionRoute:
    return ExecutionRoute(
        route_id=route_id,
        provider_id=provider_id,
        executor_id="codex",
        substrate_id="cloud",
        model_id="model",
        status=RouteStatus.READY,
        capabilities=frozenset({capability}),
        privacy_classes=privacy_classes,
        certified=True,
        zero_cost=True,
        external=True,
        human_start_required=False,
        health_observed_at_epoch=now,
        health_max_age_seconds=60,
        expected_start_delay_ms=0,
        expected_runtime_ms=100,
        expected_validation_ms=10,
        quota_windows=(
            QuotaWindow(
                metric="requests",
                limit=1000,
                remaining=remaining_requests,
                observed_at_epoch=now,
                max_age_seconds=300,
            ),
            QuotaWindow(
                metric="tokens",
                limit=200_000,
                remaining=remaining_tokens,
                observed_at_epoch=now,
                max_age_seconds=300,
            ),
        ),
    )


def test_routed_dispatch_reserves_quota_before_return(tmp_path) -> None:
    now = 1000
    task = DispatchTask(
        "routed",
        0,
        required_capability="code",
        quota_demand=(("requests", 1), ("tokens", 500)),
    )
    route = _lex_route("groq", provider_id="groq", now=now)
    ledger = QuotaReservationLedger(tmp_path / "lex.db")

    routed = select_next_routed_task(
        (task,),
        (route,),
        now_epoch=now,
        ledger=ledger,
    )

    assert routed is not None
    assert routed.task.task_id == "routed"
    assert routed.decision.route_id == "groq"
    assert routed.decision.reservation_id is not None
    assert ledger.active_reserved(route_id="groq", metric="requests", now_epoch=now) == 1
    assert ledger.active_reserved(route_id="groq", metric="tokens", now_epoch=now) == 500


def test_routed_dispatch_skips_head_of_line_when_route_incompatible(tmp_path) -> None:
    now = 1000
    tasks = (
        DispatchTask("needs-vision", 0, required_capability="vision"),
        DispatchTask("can-code", 1, required_capability="code"),
    )
    route = _lex_route("groq", provider_id="groq", now=now)
    ledger = QuotaReservationLedger(tmp_path / "lex.db")

    routed = select_next_routed_task(
        tasks,
        (route,),
        now_epoch=now,
        ledger=ledger,
    )

    assert routed is not None
    assert routed.task.task_id == "can-code"


def test_routed_dispatch_private_task_does_not_use_public_external_route(tmp_path) -> None:
    now = 1000
    task = DispatchTask("private", 0, privacy_class="PRIVATE")
    route = _lex_route("groq", provider_id="groq", now=now)
    ledger = QuotaReservationLedger(tmp_path / "lex.db")

    assert (
        select_next_routed_task(
            (task,),
            (route,),
            now_epoch=now,
            ledger=ledger,
        )
        is None
    )


def test_routed_dispatch_honours_verifier_provider_independence(tmp_path) -> None:
    now = 1000
    task = DispatchTask(
        "verify",
        0,
        required_capability="code",
        independent_from_provider_id="groq",
    )
    groq = _lex_route("groq", provider_id="groq", now=now)
    ollama = _lex_route("ollama", provider_id="ollama", now=now)
    ledger = QuotaReservationLedger(tmp_path / "lex.db")

    routed = select_next_routed_task(
        (task,),
        (groq, ollama),
        now_epoch=now,
        ledger=ledger,
    )

    assert routed is not None
    assert routed.decision.provider_id == "ollama"


def test_routed_dispatch_quota_overbooking_moves_to_next_route(tmp_path) -> None:
    now = 1000
    task = DispatchTask(
        "q",
        0,
        quota_demand=(("requests", 1), ("tokens", 1000)),
    )
    groq = _lex_route(
        "groq",
        provider_id="groq",
        now=now,
        remaining_requests=1,
        remaining_tokens=1500,
    )
    ollama = _lex_route("ollama", provider_id="ollama", now=now)
    ledger = QuotaReservationLedger(tmp_path / "lex.db")

    first = select_next_routed_task(
        (task,),
        (groq,),
        now_epoch=now,
        ledger=ledger,
    )
    assert first is not None

    second = select_next_routed_task(
        (task,),
        (groq, ollama),
        now_epoch=now,
        ledger=ledger,
    )

    assert second is not None
    assert second.decision.provider_id == "ollama"

