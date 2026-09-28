from __future__ import annotations

from pathlib import Path

import pytest

from core.night_shift.authority import AuthorityBudgetStore
from core.night_shift.contracts import (
    AuthorityReservation,
    AutonomyEnvelope,
    NightShiftContractError,
    PromotionMode,
    RiskClass,
)


def _envelope(max_tasks: int = 2) -> AutonomyEnvelope:
    return AutonomyEnvelope(
        envelope_id="night-budget",
        issued_at_epoch=10,
        expires_at_epoch=100,
        repositories=("marcusdd720-ui/lukart-ros",),
        allowed_risk_classes=(RiskClass.R1,),
        max_tasks=max_tasks,
        promotion_mode=PromotionMode.PREAUTHORIZED,
    )


def _store(tmp_path: Path) -> AuthorityBudgetStore:
    return AuthorityBudgetStore(tmp_path / "authority.db")
def test_unique_tasks_consume_budget_once(tmp_path: Path) -> None:
    store = _store(tmp_path)
    envelope = _envelope(max_tasks=2)

    first = store.reserve_task(
        envelope=envelope,
        task_id="task-1",
        now_epoch=20,
    )
    duplicate = store.reserve_task(
        envelope=envelope,
        task_id="task-1",
        now_epoch=21,
    )
    second = store.reserve_task(
        envelope=envelope,
        task_id="task-2",
        now_epoch=22,
    )

    assert first == duplicate
    assert first.ordinal == 1
    assert second.ordinal == 2


def test_task_budget_exhaustion_fails_closed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    envelope = _envelope(max_tasks=1)
    store.reserve_task(
        envelope=envelope,
        task_id="task-1",
        now_epoch=20,
    )

    with pytest.raises(NightShiftContractError, match="task budget exhausted"):
        store.reserve_task(
            envelope=envelope,
            task_id="task-2",
            now_epoch=21,
        )


def test_expired_envelope_cannot_reserve_task(tmp_path: Path) -> None:
    store = _store(tmp_path)
    envelope = _envelope(max_tasks=1)

    with pytest.raises(NightShiftContractError, match="authority envelope expired"):
        store.reserve_task(
            envelope=envelope,
            task_id="task-1",
            now_epoch=100,
        )


def test_forged_reservation_is_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    envelope = _envelope(max_tasks=2)
    real = store.reserve_task(
        envelope=envelope,
        task_id="task-1",
        now_epoch=20,
    )
    store.require_reserved(real)

    forged = AuthorityReservation(
        envelope_digest=real.envelope_digest,
        task_id=real.task_id,
        ordinal=real.ordinal + 1,
    )
    with pytest.raises(
        NightShiftContractError,
        match="not present in the durable budget store",
    ):
        store.require_reserved(forged)
