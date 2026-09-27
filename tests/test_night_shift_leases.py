from __future__ import annotations

from pathlib import Path

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.leases import LeaseStore


def _store(tmp_path: Path) -> LeaseStore:
    return LeaseStore(tmp_path / "leases.db")


def test_reacquire_after_expiry_increments_fencing_token(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.acquire(
        task_id="task-1",
        lease_id="lease-a",
        worker_id="worker-a",
        now_epoch=10,
        ttl_seconds=5,
    )
    second = store.acquire(
        task_id="task-1",
        lease_id="lease-b",
        worker_id="worker-b",
        now_epoch=15,
        ttl_seconds=5,
    )

    assert first.fencing_token == 1
    assert second.fencing_token == 2

def test_active_lease_cannot_be_stolen(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.acquire(
        task_id="task-1",
        lease_id="lease-a",
        worker_id="worker-a",
        now_epoch=10,
        ttl_seconds=10,
    )

    with pytest.raises(NightShiftContractError, match="active lease"):
        store.acquire(
            task_id="task-1",
            lease_id="lease-b",
            worker_id="worker-b",
            now_epoch=19,
            ttl_seconds=10,
        )

def test_stale_worker_is_rejected_after_reacquire(tmp_path: Path) -> None:
    store = _store(tmp_path)
    old = store.acquire(
        task_id="task-1",
        lease_id="lease-a",
        worker_id="worker-a",
        now_epoch=10,
        ttl_seconds=5,
    )
    new = store.acquire(
        task_id="task-1",
        lease_id="lease-b",
        worker_id="worker-b",
        now_epoch=15,
        ttl_seconds=10,
    )

    with pytest.raises(NightShiftContractError, match="stale lease or fencing token"):
        store.require_current(
            task_id=old.task_id,
            lease_id=old.lease_id,
            fencing_token=old.fencing_token,
            now_epoch=16,
        )

    current = store.require_current(
        task_id=new.task_id,
        lease_id=new.lease_id,
        fencing_token=new.fencing_token,
        now_epoch=16,
    )
    assert current.worker_id == "worker-b"


def test_heartbeat_extends_current_lease(tmp_path: Path) -> None:
    store = _store(tmp_path)
    lease = store.acquire(
        task_id="task-1",
        lease_id="lease-a",
        worker_id="worker-a",
        now_epoch=10,
        ttl_seconds=5,
    )
    renewed = store.heartbeat(
        task_id=lease.task_id,
        lease_id=lease.lease_id,
        fencing_token=lease.fencing_token,
        now_epoch=12,
        ttl_seconds=10,
    )

    assert renewed.expires_at_epoch == 22
    assert renewed.version > lease.version

def test_task_state_compare_and_swap(tmp_path: Path) -> None:
    store = _store(tmp_path)
    lease = store.acquire(
        task_id="task-1",
        lease_id="lease-a",
        worker_id="worker-a",
        now_epoch=10,
        ttl_seconds=30,
    )
    initial = store.initialize_state(
        task_id=lease.task_id,
        state="READY",
        lease_id=lease.lease_id,
        fencing_token=lease.fencing_token,
        now_epoch=11,
    )
    updated = store.compare_and_swap_state(
        task_id=lease.task_id,
        expected_version=initial.version,
        new_state="RUNNING",
        lease_id=lease.lease_id,
        fencing_token=lease.fencing_token,
        now_epoch=12,
    )

    assert updated.state == "RUNNING"
    assert updated.version == 2
    assert updated.fencing_token == lease.fencing_token

def test_stale_state_version_fails_closed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    lease = store.acquire(
        task_id="task-1",
        lease_id="lease-a",
        worker_id="worker-a",
        now_epoch=10,
        ttl_seconds=30,
    )
    state = store.initialize_state(
        task_id=lease.task_id,
        state="READY",
        lease_id=lease.lease_id,
        fencing_token=lease.fencing_token,
        now_epoch=11,
    )
    store.compare_and_swap_state(
        task_id=lease.task_id,
        expected_version=state.version,
        new_state="RUNNING",
        lease_id=lease.lease_id,
        fencing_token=lease.fencing_token,
        now_epoch=12,
    )

    with pytest.raises(NightShiftContractError, match="CAS conflict"):
        store.compare_and_swap_state(
            task_id=lease.task_id,
            expected_version=state.version,
            new_state="VALIDATING",
            lease_id=lease.lease_id,
            fencing_token=lease.fencing_token,
            now_epoch=13,
        )


def test_expired_lease_cannot_mutate_state(tmp_path: Path) -> None:
    store = _store(tmp_path)
    lease = store.acquire(
        task_id="task-1",
        lease_id="lease-a",
        worker_id="worker-a",
        now_epoch=10,
        ttl_seconds=5,
    )
    store.initialize_state(
        task_id=lease.task_id,
        state="READY",
        lease_id=lease.lease_id,
        fencing_token=lease.fencing_token,
        now_epoch=11,
    )

    with pytest.raises(NightShiftContractError, match="lease expired"):
        store.compare_and_swap_state(
            task_id=lease.task_id,
            expected_version=1,
            new_state="RUNNING",
            lease_id=lease.lease_id,
            fencing_token=lease.fencing_token,
            now_epoch=15,
        )
