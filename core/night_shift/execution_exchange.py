"""LUKART Execution Exchange (LEX) runtime primitives.

This module is intentionally provider-neutral. It turns live route evidence into a
fail-closed dispatch decision and reserves finite capacity transactionally before a
worker is launched.

It does not perform network calls and it does not launch agents. Provider adapters
refresh route evidence; worker launchers consume DispatchDecision.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from .contracts import NightShiftContractError


class RouteStatus(StrEnum):
    READY = "READY"
    READY_AFTER_RESET = "READY_AFTER_RESET"
    READY_AFTER_RESOURCE_RELEASE = "READY_AFTER_RESOURCE_RELEASE"
    READY_AFTER_HUMAN_START = "READY_AFTER_HUMAN_START"
    DEGRADED = "DEGRADED"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"
    QUARANTINED = "QUARANTINED"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class QuotaWindow:
    metric: str
    limit: int
    remaining: int
    observed_at_epoch: int
    max_age_seconds: int
    next_reset_epoch: int | None = None

    def __post_init__(self) -> None:
        if not self.metric.strip():
            raise NightShiftContractError("quota metric is required")
        if self.limit < 0 or self.remaining < 0:
            raise NightShiftContractError("quota values cannot be negative")
        if self.remaining > self.limit:
            raise NightShiftContractError("quota remaining cannot exceed limit")
        if self.observed_at_epoch < 0 or self.max_age_seconds < 1:
            raise NightShiftContractError("quota freshness values are invalid")
        if self.next_reset_epoch is not None and self.next_reset_epoch < 0:
            raise NightShiftContractError("next_reset_epoch cannot be negative")

    def is_fresh(self, *, now_epoch: int) -> bool:
        return 0 <= now_epoch - self.observed_at_epoch <= self.max_age_seconds


@dataclass(frozen=True, slots=True)
class ExecutionRoute:
    route_id: str
    provider_id: str
    executor_id: str
    substrate_id: str
    model_id: str | None
    status: RouteStatus
    capabilities: frozenset[str]
    privacy_classes: frozenset[str]
    certified: bool
    zero_cost: bool
    external: bool
    human_start_required: bool
    health_observed_at_epoch: int
    health_max_age_seconds: int
    expected_start_delay_ms: int
    expected_runtime_ms: int
    expected_validation_ms: int
    retry_risk_penalty_ms: int = 0
    scarcity_penalty_ms: int = 0
    quality_score: int = 50
    success_basis_points: int = 5000
    quota_windows: tuple[QuotaWindow, ...] = ()

    def __post_init__(self) -> None:
        required = (
            self.route_id,
            self.provider_id,
            self.executor_id,
            self.substrate_id,
        )
        if any(not value.strip() for value in required):
            raise NightShiftContractError("route identity fields are required")
        if self.health_observed_at_epoch < 0 or self.health_max_age_seconds < 1:
            raise NightShiftContractError("route health freshness values are invalid")
        timing = (
            self.expected_start_delay_ms,
            self.expected_runtime_ms,
            self.expected_validation_ms,
            self.retry_risk_penalty_ms,
            self.scarcity_penalty_ms,
        )
        if any(value < 0 for value in timing):
            raise NightShiftContractError("route timing values cannot be negative")
        if not 0 <= self.quality_score <= 100:
            raise NightShiftContractError("quality_score must be within 0..100")
        if not 0 <= self.success_basis_points <= 10_000:
            raise NightShiftContractError("success_basis_points must be within 0..10000")
        metrics = [window.metric for window in self.quota_windows]
        if len(metrics) != len(set(metrics)):
            raise NightShiftContractError("route quota metrics must be unique")

    def health_is_fresh(self, *, now_epoch: int) -> bool:
        return 0 <= now_epoch - self.health_observed_at_epoch <= self.health_max_age_seconds

    def quota_window(self, metric: str) -> QuotaWindow | None:
        return next((item for item in self.quota_windows if item.metric == metric), None)

    def earliest_useful_completion_ms(self, *, now_epoch: int) -> int:
        reset_wait_ms = 0
        if self.status is RouteStatus.READY_AFTER_RESET:
            resets = [
                item.next_reset_epoch
                for item in self.quota_windows
                if item.next_reset_epoch is not None and item.next_reset_epoch > now_epoch
            ]
            if not resets:
                raise NightShiftContractError("READY_AFTER_RESET requires an evidenced reset")
            reset_wait_ms = (min(resets) - now_epoch) * 1000
        return (
            reset_wait_ms
            + self.expected_start_delay_ms
            + self.expected_runtime_ms
            + self.expected_validation_ms
            + self.retry_risk_penalty_ms
            + self.scarcity_penalty_ms
        )


@dataclass(frozen=True, slots=True)
class DispatchRequirement:
    task_id: str
    required_capability: str
    privacy_class: str
    require_zero_cost: bool = True
    autonomous_required: bool = True
    require_certified: bool = True
    independent_from_provider_id: str | None = None
    quota_demand: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.required_capability.strip():
            raise NightShiftContractError("task_id and required_capability are required")
        if not self.privacy_class.strip():
            raise NightShiftContractError("privacy_class is required")
        metrics = [metric for metric, _ in self.quota_demand]
        if len(metrics) != len(set(metrics)):
            raise NightShiftContractError("quota demand metrics must be unique")
        if any(not metric.strip() or amount < 1 for metric, amount in self.quota_demand):
            raise NightShiftContractError("quota demand entries must be positive")


@dataclass(frozen=True, slots=True)
class DispatchDecision:
    task_id: str
    route_id: str
    provider_id: str
    executor_id: str
    model_id: str | None
    euc_ms: int
    reservation_id: str | None
    registry_digest: str
    reason: str

    def digest(self) -> str:
        payload = {
            "task_id": self.task_id,
            "route_id": self.route_id,
            "provider_id": self.provider_id,
            "executor_id": self.executor_id,
            "model_id": self.model_id,
            "euc_ms": self.euc_ms,
            "reservation_id": self.reservation_id,
            "registry_digest": self.registry_digest,
            "reason": self.reason,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()


class QuotaReservationLedger:
    """SQLite-WAL reservation ledger preventing internal quota overbooking."""

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=10.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS quota_reservations (
                    reservation_id TEXT NOT NULL,
                    route_id TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    reserved_amount INTEGER NOT NULL CHECK (reserved_amount > 0),
                    actual_amount INTEGER,
                    created_at_epoch INTEGER NOT NULL,
                    expires_at_epoch INTEGER NOT NULL,
                    state TEXT NOT NULL CHECK (
                        state IN ('ACTIVE', 'RELEASED', 'RECONCILED')
                    ),
                    PRIMARY KEY (reservation_id, metric)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_quota_reservations_active
                ON quota_reservations(route_id, metric, state, expires_at_epoch)
                """
            )

    def active_reserved(self, *, route_id: str, metric: str, now_epoch: int) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(SUM(reserved_amount), 0) AS total
                FROM quota_reservations
                WHERE route_id = ?
                  AND metric = ?
                  AND state = 'ACTIVE'
                  AND expires_at_epoch > ?
                """,
                (route_id, metric, now_epoch),
            ).fetchone()
        return int(row["total"])

    def reserve(
        self,
        *,
        route: ExecutionRoute,
        demand: tuple[tuple[str, int], ...],
        now_epoch: int,
        ttl_seconds: int,
    ) -> str | None:
        if not demand:
            return None
        if ttl_seconds < 1:
            raise NightShiftContractError("reservation ttl_seconds must be positive")

        reservation_id = str(uuid.uuid4())
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE quota_reservations
                SET state = 'RELEASED'
                WHERE state = 'ACTIVE' AND expires_at_epoch <= ?
                """,
                (now_epoch,),
            )

            for metric, amount in demand:
                window = route.quota_window(metric)
                if window is None:
                    raise NightShiftContractError(
                        f"route {route.route_id} lacks quota window for {metric}"
                    )
                if not window.is_fresh(now_epoch=now_epoch):
                    raise NightShiftContractError(
                        f"route {route.route_id} quota window {metric} is stale"
                    )
                row = connection.execute(
                    """
                    SELECT COALESCE(SUM(reserved_amount), 0) AS total
                    FROM quota_reservations
                    WHERE route_id = ?
                      AND metric = ?
                      AND state = 'ACTIVE'
                      AND expires_at_epoch > ?
                    """,
                    (route.route_id, metric, now_epoch),
                ).fetchone()
                already_reserved = int(row["total"])
                schedulable = window.remaining - already_reserved
                if amount > schedulable:
                    raise NightShiftContractError(
                        f"insufficient {metric} capacity on route {route.route_id}"
                    )

            for metric, amount in demand:
                connection.execute(
                    """
                    INSERT INTO quota_reservations (
                        reservation_id,
                        route_id,
                        metric,
                        reserved_amount,
                        actual_amount,
                        created_at_epoch,
                        expires_at_epoch,
                        state
                    ) VALUES (?, ?, ?, ?, NULL, ?, ?, 'ACTIVE')
                    """,
                    (
                        reservation_id,
                        route.route_id,
                        metric,
                        amount,
                        now_epoch,
                        now_epoch + ttl_seconds,
                    ),
                )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
        return reservation_id

    def release(self, reservation_id: str) -> None:
        if not reservation_id.strip():
            raise NightShiftContractError("reservation_id is required")
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE quota_reservations
                SET state = 'RELEASED'
                WHERE reservation_id = ? AND state = 'ACTIVE'
                """,
                (reservation_id,),
            )

    def reconcile(self, reservation_id: str, actual_by_metric: dict[str, int]) -> None:
        if not reservation_id.strip():
            raise NightShiftContractError("reservation_id is required")
        if any(amount < 0 for amount in actual_by_metric.values()):
            raise NightShiftContractError("actual usage cannot be negative")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT metric FROM quota_reservations
                WHERE reservation_id = ?
                """,
                (reservation_id,),
            ).fetchall()
            metrics = {str(row["metric"]) for row in rows}
            if not metrics:
                raise NightShiftContractError("unknown reservation_id")
            if not set(actual_by_metric).issubset(metrics):
                raise NightShiftContractError("actual usage references unreserved metric")
            for metric in metrics:
                actual = actual_by_metric.get(metric, 0)
                connection.execute(
                    """
                    UPDATE quota_reservations
                    SET actual_amount = ?, state = 'RECONCILED'
                    WHERE reservation_id = ? AND metric = ?
                    """,
                    (actual, reservation_id, metric),
                )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()


def _route_eligible(
    route: ExecutionRoute,
    requirement: DispatchRequirement,
    *,
    now_epoch: int,
    ledger: QuotaReservationLedger,
) -> tuple[bool, str]:
    if route.status not in {RouteStatus.READY, RouteStatus.READY_AFTER_RESET}:
        return False, f"STATUS_{route.status.value}"
    if not route.health_is_fresh(now_epoch=now_epoch):
        return False, "STALE_HEALTH"
    if requirement.require_certified and not route.certified:
        return False, "NOT_CERTIFIED"
    if requirement.require_zero_cost and not route.zero_cost:
        return False, "NOT_ZERO_COST"
    if requirement.autonomous_required and route.human_start_required:
        return False, "HUMAN_START_REQUIRED"
    if requirement.required_capability not in route.capabilities:
        return False, "CAPABILITY_MISMATCH"
    if requirement.privacy_class not in route.privacy_classes:
        return False, "PRIVACY_MISMATCH"
    if (
        requirement.independent_from_provider_id is not None
        and route.provider_id == requirement.independent_from_provider_id
    ):
        return False, "INDEPENDENCE_MISMATCH"

    for metric, amount in requirement.quota_demand:
        window = route.quota_window(metric)
        if window is None:
            return False, f"MISSING_QUOTA_{metric}"
        if not window.is_fresh(now_epoch=now_epoch):
            return False, f"STALE_QUOTA_{metric}"
        reserved = ledger.active_reserved(
            route_id=route.route_id,
            metric=metric,
            now_epoch=now_epoch,
        )
        if amount > window.remaining - reserved:
            return False, f"INSUFFICIENT_QUOTA_{metric}"

    return True, "ELIGIBLE"


def registry_digest(routes: tuple[ExecutionRoute, ...]) -> str:
    payload = [
        {
            "route_id": item.route_id,
            "provider_id": item.provider_id,
            "executor_id": item.executor_id,
            "substrate_id": item.substrate_id,
            "model_id": item.model_id,
            "status": item.status.value,
            "capabilities": sorted(item.capabilities),
            "privacy_classes": sorted(item.privacy_classes),
            "certified": item.certified,
            "zero_cost": item.zero_cost,
            "external": item.external,
            "human_start_required": item.human_start_required,
            "health_observed_at_epoch": item.health_observed_at_epoch,
            "health_max_age_seconds": item.health_max_age_seconds,
            "quota_windows": [
                {
                    "metric": window.metric,
                    "limit": window.limit,
                    "remaining": window.remaining,
                    "observed_at_epoch": window.observed_at_epoch,
                    "max_age_seconds": window.max_age_seconds,
                    "next_reset_epoch": window.next_reset_epoch,
                }
                for window in item.quota_windows
            ],
        }
        for item in sorted(routes, key=lambda route: route.route_id)
    ]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def select_and_reserve_route(
    routes: tuple[ExecutionRoute, ...],
    requirement: DispatchRequirement,
    *,
    now_epoch: int,
    ledger: QuotaReservationLedger,
    reservation_ttl_seconds: int = 300,
) -> DispatchDecision | None:
    eligible: list[tuple[ExecutionRoute, int]] = []
    for route in routes:
        accepted, _ = _route_eligible(
            route,
            requirement,
            now_epoch=now_epoch,
            ledger=ledger,
        )
        if accepted:
            eligible.append(
                (route, route.earliest_useful_completion_ms(now_epoch=now_epoch))
            )

    if not eligible:
        return None

    route, euc_ms = sorted(
        eligible,
        key=lambda item: (
            item[1],
            item[0].scarcity_penalty_ms,
            -item[0].success_basis_points,
            -item[0].quality_score,
            item[0].route_id,
        ),
    )[0]

    reservation_id = ledger.reserve(
        route=route,
        demand=requirement.quota_demand,
        now_epoch=now_epoch,
        ttl_seconds=reservation_ttl_seconds,
    )
    return DispatchDecision(
        task_id=requirement.task_id,
        route_id=route.route_id,
        provider_id=route.provider_id,
        executor_id=route.executor_id,
        model_id=route.model_id,
        euc_ms=euc_ms,
        reservation_id=reservation_id,
        registry_digest=registry_digest(routes),
        reason="EARLIEST_USEFUL_COMPLETION",
    )


def _as_string_set(value: Any, *, field_name: str) -> frozenset[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise NightShiftContractError(f"{field_name} must be a list of strings")
    return frozenset(item.strip() for item in value if item.strip())


def load_routes_yaml(path: str | Path) -> tuple[ExecutionRoute, ...]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("routes"), list):
        raise NightShiftContractError("LEX route registry requires a routes list")

    routes: list[ExecutionRoute] = []
    for item in raw["routes"]:
        if not isinstance(item, dict):
            raise NightShiftContractError("LEX route entry must be a mapping")
        windows: list[QuotaWindow] = []
        for window in item.get("quota_windows", []):
            if not isinstance(window, dict):
                raise NightShiftContractError("quota window must be a mapping")
            windows.append(
                QuotaWindow(
                    metric=str(window["metric"]),
                    limit=int(window["limit"]),
                    remaining=int(window["remaining"]),
                    observed_at_epoch=int(window["observed_at_epoch"]),
                    max_age_seconds=int(window["max_age_seconds"]),
                    next_reset_epoch=(
                        int(window["next_reset_epoch"])
                        if window.get("next_reset_epoch") is not None
                        else None
                    ),
                )
            )

        routes.append(
            ExecutionRoute(
                route_id=str(item["route_id"]),
                provider_id=str(item["provider_id"]),
                executor_id=str(item["executor_id"]),
                substrate_id=str(item["substrate_id"]),
                model_id=(
                    str(item["model_id"]) if item.get("model_id") is not None else None
                ),
                status=RouteStatus(str(item["status"])),
                capabilities=_as_string_set(item["capabilities"], field_name="capabilities"),
                privacy_classes=_as_string_set(
                    item["privacy_classes"], field_name="privacy_classes"
                ),
                certified=bool(item["certified"]),
                zero_cost=bool(item["zero_cost"]),
                external=bool(item["external"]),
                human_start_required=bool(item["human_start_required"]),
                health_observed_at_epoch=int(item["health_observed_at_epoch"]),
                health_max_age_seconds=int(item["health_max_age_seconds"]),
                expected_start_delay_ms=int(item["expected_start_delay_ms"]),
                expected_runtime_ms=int(item["expected_runtime_ms"]),
                expected_validation_ms=int(item["expected_validation_ms"]),
                retry_risk_penalty_ms=int(item.get("retry_risk_penalty_ms", 0)),
                scarcity_penalty_ms=int(item.get("scarcity_penalty_ms", 0)),
                quality_score=int(item.get("quality_score", 50)),
                success_basis_points=int(item.get("success_basis_points", 5000)),
                quota_windows=tuple(windows),
            )
        )
    route_ids = [route.route_id for route in routes]
    if len(route_ids) != len(set(route_ids)):
        raise NightShiftContractError("LEX route ids must be unique")
    return tuple(routes)
