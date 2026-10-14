from __future__ import annotations

from pathlib import Path

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.execution_exchange import (
    DispatchRequirement,
    ExecutionRoute,
    QuotaReservationLedger,
    QuotaWindow,
    RouteStatus,
    load_routes_yaml,
    registry_digest,
    select_and_reserve_route,
)


def _route(
    route_id: str,
    *,
    provider_id: str,
    now: int,
    status: RouteStatus = RouteStatus.READY,
    certified: bool = True,
    zero_cost: bool = True,
    human_start_required: bool = False,
    external: bool = True,
    start_ms: int = 0,
    runtime_ms: int = 1000,
    validation_ms: int = 100,
    retry_penalty_ms: int = 0,
    scarcity_penalty_ms: int = 0,
    quality_score: int = 80,
    success_basis_points: int = 9000,
    request_remaining: int = 100,
    token_remaining: int = 10000,
    quota_age: int = 0,
) -> ExecutionRoute:
    return ExecutionRoute(
        route_id=route_id,
        provider_id=provider_id,
        executor_id="codex",
        substrate_id="cloud",
        model_id="model",
        status=status,
        capabilities=frozenset({"code", "review"}),
        privacy_classes=frozenset({"SYNTHETIC", "PUBLIC"}),
        certified=certified,
        zero_cost=zero_cost,
        external=external,
        human_start_required=human_start_required,
        health_observed_at_epoch=now,
        health_max_age_seconds=60,
        expected_start_delay_ms=start_ms,
        expected_runtime_ms=runtime_ms,
        expected_validation_ms=validation_ms,
        retry_risk_penalty_ms=retry_penalty_ms,
        scarcity_penalty_ms=scarcity_penalty_ms,
        quality_score=quality_score,
        success_basis_points=success_basis_points,
        quota_windows=(
            QuotaWindow(
                metric="requests",
                limit=1000,
                remaining=request_remaining,
                observed_at_epoch=now - quota_age,
                max_age_seconds=300,
            ),
            QuotaWindow(
                metric="tokens",
                limit=200000,
                remaining=token_remaining,
                observed_at_epoch=now - quota_age,
                max_age_seconds=300,
            ),
        ),
    )


def _req(
    *,
    provider_to_avoid: str | None = None,
    privacy: str = "SYNTHETIC",
) -> DispatchRequirement:
    return DispatchRequirement(
        task_id="task-1",
        required_capability="code",
        privacy_class=privacy,
        independent_from_provider_id=provider_to_avoid,
        quota_demand=(("requests", 1), ("tokens", 1000)),
    )


def test_selects_lowest_euc_ready_route(tmp_path: Path) -> None:
    now = 1000
    slow = _route("slow", provider_id="p1", now=now, runtime_ms=5000)
    fast = _route("fast", provider_id="p2", now=now, runtime_ms=1000)
    ledger = QuotaReservationLedger(tmp_path / "lex.db")

    decision = select_and_reserve_route(
        (slow, fast), _req(), now_epoch=now, ledger=ledger
    )

    assert decision is not None
    assert decision.route_id == "fast"
    assert decision.reservation_id is not None


def test_stale_health_fails_closed(tmp_path: Path) -> None:
    now = 1000
    route = ExecutionRoute(
        route_id="stale",
        provider_id="p",
        executor_id="codex",
        substrate_id="cloud",
        model_id="m",
        status=RouteStatus.READY,
        capabilities=frozenset({"code"}),
        privacy_classes=frozenset({"SYNTHETIC"}),
        certified=True,
        zero_cost=True,
        external=True,
        human_start_required=False,
        health_observed_at_epoch=900,
        health_max_age_seconds=60,
        expected_start_delay_ms=0,
        expected_runtime_ms=100,
        expected_validation_ms=10,
        quota_windows=(),
    )
    ledger = QuotaReservationLedger(tmp_path / "lex.db")
    req = DispatchRequirement(
        task_id="t",
        required_capability="code",
        privacy_class="SYNTHETIC",
    )

    assert select_and_reserve_route((route,), req, now_epoch=now, ledger=ledger) is None


def test_uncertified_route_fails_closed(tmp_path: Path) -> None:
    now = 1000
    route = _route("x", provider_id="p", now=now, certified=False)
    ledger = QuotaReservationLedger(tmp_path / "lex.db")
    assert select_and_reserve_route((route,), _req(), now_epoch=now, ledger=ledger) is None


def test_paid_route_rejected_when_zero_cost_required(tmp_path: Path) -> None:
    now = 1000
    route = _route("x", provider_id="p", now=now, zero_cost=False)
    ledger = QuotaReservationLedger(tmp_path / "lex.db")
    assert select_and_reserve_route((route,), _req(), now_epoch=now, ledger=ledger) is None


def test_human_start_route_rejected_for_autonomous_dispatch(tmp_path: Path) -> None:
    now = 1000
    route = _route("work", provider_id="openai", now=now, human_start_required=True)
    ledger = QuotaReservationLedger(tmp_path / "lex.db")
    assert select_and_reserve_route((route,), _req(), now_epoch=now, ledger=ledger) is None


def test_private_data_rejected_by_external_public_route(tmp_path: Path) -> None:
    now = 1000
    route = _route("x", provider_id="p", now=now)
    ledger = QuotaReservationLedger(tmp_path / "lex.db")
    assert (
        select_and_reserve_route(
            (route,),
            _req(privacy="PRIVATE"),
            now_epoch=now,
            ledger=ledger,
        )
        is None
    )


def test_independent_verifier_avoids_builder_provider(tmp_path: Path) -> None:
    now = 1000
    same = _route("same", provider_id="groq", now=now, runtime_ms=100)
    other = _route("other", provider_id="ollama", now=now, runtime_ms=1000)
    ledger = QuotaReservationLedger(tmp_path / "lex.db")

    decision = select_and_reserve_route(
        (same, other),
        _req(provider_to_avoid="groq"),
        now_epoch=now,
        ledger=ledger,
    )

    assert decision is not None
    assert decision.provider_id == "ollama"


def test_quota_reservation_prevents_overbooking(tmp_path: Path) -> None:
    now = 1000
    route = _route(
        "groq",
        provider_id="groq",
        now=now,
        request_remaining=1,
        token_remaining=1500,
    )
    ledger = QuotaReservationLedger(tmp_path / "lex.db")

    first = select_and_reserve_route(
        (route,), _req(), now_epoch=now, ledger=ledger, reservation_ttl_seconds=60
    )
    second = select_and_reserve_route(
        (route,), _req(), now_epoch=now, ledger=ledger, reservation_ttl_seconds=60
    )

    assert first is not None
    assert second is None
    assert ledger.active_reserved(route_id="groq", metric="requests", now_epoch=now) == 1
    assert ledger.active_reserved(route_id="groq", metric="tokens", now_epoch=now) == 1000


def test_release_restores_schedulable_capacity(tmp_path: Path) -> None:
    now = 1000
    route = _route(
        "groq",
        provider_id="groq",
        now=now,
        request_remaining=1,
        token_remaining=1500,
    )
    ledger = QuotaReservationLedger(tmp_path / "lex.db")

    first = select_and_reserve_route((route,), _req(), now_epoch=now, ledger=ledger)
    assert first is not None and first.reservation_id is not None

    ledger.release(first.reservation_id)

    second = select_and_reserve_route((route,), _req(), now_epoch=now, ledger=ledger)
    assert second is not None


def test_expired_reservation_does_not_block_new_task(tmp_path: Path) -> None:
    now = 1000
    route = _route(
        "groq",
        provider_id="groq",
        now=now,
        request_remaining=1,
        token_remaining=1500,
    )
    ledger = QuotaReservationLedger(tmp_path / "lex.db")

    first = select_and_reserve_route(
        (route,), _req(), now_epoch=now, ledger=ledger, reservation_ttl_seconds=1
    )
    assert first is not None

    second = select_and_reserve_route(
        (route,), _req(), now_epoch=now + 2, ledger=ledger
    )
    assert second is not None


def test_stale_quota_window_fails_closed(tmp_path: Path) -> None:
    now = 1000
    route = _route("x", provider_id="p", now=now, quota_age=301)
    ledger = QuotaReservationLedger(tmp_path / "lex.db")

    assert select_and_reserve_route((route,), _req(), now_epoch=now, ledger=ledger) is None


def test_scarcity_penalty_preserves_scarce_route(tmp_path: Path) -> None:
    now = 1000
    scarce = _route(
        "120b",
        provider_id="groq",
        now=now,
        runtime_ms=500,
        scarcity_penalty_ms=5000,
    )
    ordinary = _route(
        "20b",
        provider_id="ollama",
        now=now,
        runtime_ms=1500,
        scarcity_penalty_ms=0,
    )
    ledger = QuotaReservationLedger(tmp_path / "lex.db")

    decision = select_and_reserve_route(
        (scarce, ordinary), _req(), now_epoch=now, ledger=ledger
    )

    assert decision is not None
    assert decision.route_id == "20b"


def test_degraded_route_can_be_used_with_explicit_penalty(tmp_path: Path) -> None:
    now = 1000
    degraded = _route(
        "degraded",
        provider_id="p1",
        now=now,
        status=RouteStatus.DEGRADED,
        runtime_ms=500,
        retry_penalty_ms=2000,
    )
    healthy = _route("healthy", provider_id="p2", now=now, runtime_ms=1000)
    ledger = QuotaReservationLedger(tmp_path / "lex.db")

    decision = select_and_reserve_route(
        (degraded, healthy), _req(), now_epoch=now, ledger=ledger
    )

    assert decision is not None
    assert decision.route_id == "healthy"


def test_ready_after_reset_is_not_dispatched_early(tmp_path: Path) -> None:
    now = 1000
    route = _route(
        "reset",
        provider_id="p",
        now=now,
        status=RouteStatus.READY_AFTER_RESET,
    )
    ledger = QuotaReservationLedger(tmp_path / "lex.db")

    assert select_and_reserve_route((route,), _req(), now_epoch=now, ledger=ledger) is None


def test_reconcile_records_actual_usage(tmp_path: Path) -> None:
    now = 1000
    route = _route("groq", provider_id="groq", now=now)
    ledger = QuotaReservationLedger(tmp_path / "lex.db")

    decision = select_and_reserve_route((route,), _req(), now_epoch=now, ledger=ledger)
    assert decision is not None and decision.reservation_id is not None

    ledger.reconcile(
        decision.reservation_id,
        {"requests": 1, "tokens": 730},
    )
    assert ledger.active_reserved(route_id="groq", metric="tokens", now_epoch=now) == 0


def test_registry_digest_is_order_independent(tmp_path: Path) -> None:
    now = 1000
    a = _route("a", provider_id="p1", now=now)
    b = _route("b", provider_id="p2", now=now)

    assert registry_digest((a, b)) == registry_digest((b, a))


def test_load_routes_yaml(tmp_path: Path) -> None:
    registry = tmp_path / "routes.yaml"
    registry.write_text(
        """
schema_version: 1
routes:
  - route_id: groq-20b
    provider_id: groq
    executor_id: codex
    substrate_id: groq-cloud
    model_id: openai/gpt-oss-20b
    status: READY
    capabilities: [code, review]
    privacy_classes: [SYNTHETIC, PUBLIC]
    certified: true
    zero_cost: true
    external: true
    human_start_required: false
    health_observed_at_epoch: 1000
    health_max_age_seconds: 60
    expected_start_delay_ms: 0
    expected_runtime_ms: 1000
    expected_validation_ms: 100
    quota_windows:
      - metric: requests
        limit: 1000
        remaining: 999
        observed_at_epoch: 1000
        max_age_seconds: 300
      - metric: tokens
        limit: 8000
        remaining: 7886
        observed_at_epoch: 1000
        max_age_seconds: 300
""".strip(),
        encoding="utf-8",
    )

    routes = load_routes_yaml(registry)

    assert len(routes) == 1
    assert routes[0].route_id == "groq-20b"
    assert routes[0].quota_window("tokens") is not None


def test_invalid_quota_fails_closed() -> None:
    with pytest.raises(NightShiftContractError, match="remaining"):
        QuotaWindow(
            metric="tokens",
            limit=100,
            remaining=101,
            observed_at_epoch=1,
            max_age_seconds=60,
        )
