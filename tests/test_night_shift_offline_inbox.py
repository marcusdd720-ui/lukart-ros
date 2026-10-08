"""No network, credential or live-provider access during these regression tests."""
from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from core.night_shift.continuous_dispatcher import DispatchTask
from core.night_shift.contracts import NightShiftContractError
from core.night_shift.offline_inbox import InboxCapsule, OfflineTaskInbox


def capsule(task_id="T1", **kwargs):
    task = DispatchTask(task_id, 1, **kwargs)
    return InboxCapsule(
        task=task,
        source_ref="https://github.com/marcusdd720-ui/lukart-ros/issues/346",
        source_digest="a" * 64,
        git_sha="b" * 40,
        policy_digest="c" * 64,
        observed_at_epoch=100,
        max_age_seconds=100,
    )


def test_restart_recovers_intact_queue(tmp_path: Path):
    path = tmp_path / "queue.db"
    first = OfflineTaskInbox(path)
    c = capsule()
    digest = first.enqueue(c, now_epoch=110)
    assert OfflineTaskInbox(path).snapshot() == (c,)
    assert OfflineTaskInbox(path).enqueue(c, now_epoch=120) == digest
    assert first.next_safe_local_probe(now_epoch=120).task_id == "T1"


def test_enqueued_task_cannot_be_silently_redefined(tmp_path: Path):
    inbox = OfflineTaskInbox(tmp_path / "queue.db")
    inbox.enqueue(capsule(), now_epoch=110)
    with pytest.raises(NightShiftContractError, match="identity conflict"):
        inbox.enqueue(replace(capsule(), source_digest="d" * 64), now_epoch=110)


def test_future_and_stale_sources_fail_closed(tmp_path: Path):
    inbox = OfflineTaskInbox(tmp_path / "queue.db")
    for instant in (99, 201):
        with pytest.raises(NightShiftContractError, match="stale or future"):
            inbox.enqueue(capsule(), now_epoch=instant)


def test_mutating_and_gated_work_is_retained_but_not_auto_selected(tmp_path: Path):
    inbox = OfflineTaskInbox(tmp_path / "queue.db")
    for i, kw in enumerate(({"write_task": True}, {"human_gate": True}, {"external_gate": True})):
        inbox.enqueue(capsule(f"T{i}", **kw), now_epoch=110)
    assert len(OfflineTaskInbox(inbox.path).snapshot()) == 3
    assert inbox.next_safe_local_probe(now_epoch=120) is None


def test_existing_hermes_lease_is_never_preempted(tmp_path: Path):
    inbox = OfflineTaskInbox(tmp_path / "queue.db")
    inbox.enqueue(capsule(), now_epoch=110)
    inbox.leases.acquire(task_id="T1", lease_id="hermes-existing-lease",
                         worker_id="Hermes", now_epoch=111, ttl_seconds=10)
    assert inbox.next_safe_local_probe(now_epoch=112) is None
    assert OfflineTaskInbox(inbox.path).next_safe_local_probe(now_epoch=130) is None


def test_tamper_detection_is_fail_closed(tmp_path: Path):
    inbox = OfflineTaskInbox(tmp_path / "queue.db")
    inbox.enqueue(capsule(), now_epoch=110)
    with sqlite3.connect(inbox.path) as con:
        con.execute("UPDATE offline_task_capsules SET capsule_json='{}' WHERE task_id='T1'")
    with pytest.raises(NightShiftContractError):
        OfflineTaskInbox(inbox.path).snapshot()


def test_untrusted_fields_and_duplicate_keys_fail_closed():
    c = capsule()
    s = c.serialized()
    with pytest.raises(NightShiftContractError):
        InboxCapsule.parse(s.replace('"policy_digest":', '"unexpected":true,"policy_digest":', 1))
    with pytest.raises(NightShiftContractError):
        InboxCapsule.parse(s.replace('"policy_digest":', '"policy_digest":"x","policy_digest":', 1))


def test_private_task_is_forbidden():
    with pytest.raises(NightShiftContractError, match="private"):
        capsule(privacy_class="PRIVATE")


def test_offline_expiry_refuses_execution(tmp_path: Path):
    inbox = OfflineTaskInbox(tmp_path / "queue.db")
    inbox.enqueue(capsule(), now_epoch=110)
    assert inbox.next_safe_local_probe(now_epoch=201) is None


def test_cached_dependent_task_not_trusted_as_done(tmp_path: Path):
    inbox = OfflineTaskInbox(tmp_path / "queue.db")
    inbox.enqueue(capsule("T1", status="DONE"), now_epoch=110)
    inbox.enqueue(capsule("T2", depends_on=("T1",)), now_epoch=110)
    # Cached DONE is never proof of completed work.
    assert inbox.next_safe_local_probe(now_epoch=120) is None


def test_verified_lease_state_unlocks_readonly_dependent_probe(tmp_path: Path):
    inbox = OfflineTaskInbox(tmp_path / "queue.db")
    inbox.enqueue(capsule("T1"), now_epoch=110)
    inbox.enqueue(capsule("T2", depends_on=("T1",)), now_epoch=110)
    lease = inbox.leases.acquire(
        task_id="T1", lease_id="synthetic-lease", worker_id="synthetic",
        now_epoch=111, ttl_seconds=60,
    )
    state = inbox.leases.initialize_state(
        task_id="T1", state="READY", lease_id=lease.lease_id,
        fencing_token=lease.fencing_token, now_epoch=112,
    )
    inbox.leases.compare_and_swap_state(
        task_id="T1", expected_version=state.version, new_state="DONE",
        lease_id=lease.lease_id, fencing_token=lease.fencing_token,
        now_epoch=113,
    )
    assert inbox.next_safe_local_probe(now_epoch=120).task_id == "T2"
