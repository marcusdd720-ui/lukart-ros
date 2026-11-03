"""Focused synthetic tests for the missing accepted-task/outbox boundary."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from core.night_shift.authority import AuthorityBudgetStore
from core.night_shift.contracts import (
    AutonomyEnvelope,
    LiveStateSnapshot,
    NightShiftContractError,
    PolicyRef,
    PromotionMode,
    RiskClass,
    TaskCapsule,
)
from core.night_shift.journal import DurableEventJournal
from core.night_shift.task_intake import accept_task
from scripts.integrations.ros_outbox import claim_due, connect, event_key, finish
from scripts.integrations.ros_outbox_reconcile import reconcile


def scenario(root: Path):
    policy = PolicyRef("synthetic-owner-scope", "v1", "a" * 64)
    state = LiveStateSnapshot(
        "synthetic-state",
        "marcusdd720-ui/lukart-ros",
        "integration-only",
        "b" * 40,
        "b" * 40,
        100,
        200,
        ("synthetic-integration",),
    )
    task = TaskCapsule(
        "synthetic_outbox_001",
        state.repository,
        state.digest(),
        policy.policy_digest,
        "Compute SHA256 of the synthetic canary payload; report result only.",
        RiskClass.R0,
        ("synthetic/**",),
        ("core/**",),
        ("sha256 receipt",),
    )
    envelope = AutonomyEnvelope(
        "owner-integration-20261103",
        90,
        300,
        (task.repository,),
        (RiskClass.R0,),
        1,
        PromotionMode.HUMAN,
    )
    journal = DurableEventJournal(root / "journal.sqlite3")
    authority = AuthorityBudgetStore(root / "authority.sqlite3")
    args = dict(
        journal=journal,
        authority=authority,
        policy=policy,
        state=state,
        task=task,
        envelope=envelope,
        now_epoch=150,
    )
    return args, root / "outbox.sqlite3"


def test_crash_after_source_commit_reconciles_on_restart(tmp_path):
    args, path = scenario(tmp_path)
    assert accept_task(**args)
    assert not path.exists()
    args["journal"] = DurableEventJournal(tmp_path / "journal.sqlite3")
    assert reconcile(journal=args["journal"], authority=args["authority"], outbox_path=path) == {
        "accepted": 1,
        "enqueued": 1,
        "existing": 0,
    }
    assert (
        reconcile(journal=args["journal"], authority=args["authority"], outbox_path=path)[
            "existing"
        ]
        == 1
    )
    cx = connect(path)
    try:
        assert cx.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
        assert cx.execute("SELECT event_id FROM events").fetchone()[0] == event_key(
            args["task"].task_id
        )
    finally:
        cx.close()


def test_accepted_id_conflict_and_identical_retry(tmp_path):
    args, _ = scenario(tmp_path)
    assert accept_task(**args)
    assert not accept_task(**{**args, "now_epoch": 151})
    with pytest.raises(NightShiftContractError, match="conflicting"):
        accept_task(**{**args, "task": replace(args["task"], objective="Different scope")})


def test_stale_or_unbound_authority_fails_before_accept(tmp_path):
    args, path = scenario(tmp_path)
    with pytest.raises(NightShiftContractError):
        accept_task(**{**args, "now_epoch": 250})
    with pytest.raises(NightShiftContractError):
        accept_task(**{**args, "task": replace(args["task"], policy_digest="c" * 64)})
    assert not path.exists()
    assert args["journal"].events(workflow_id="accepted-task:synthetic_outbox_001") == ()


def test_tamper_fails_before_any_outbox_write(tmp_path):
    args, path = scenario(tmp_path)
    accept_task(**args)
    cx = sqlite3.connect(args["journal"].path)
    try:
        cx.execute("UPDATE events SET payload_json='{}'")
        cx.commit()
    finally:
        cx.close()
    with pytest.raises(NightShiftContractError):
        reconcile(journal=args["journal"], authority=args["authority"], outbox_path=path)
    assert not path.exists()


def test_replay_after_lost_enqueue_response_is_deduplicated(tmp_path):
    args, path = scenario(tmp_path)
    accept_task(**args)
    reconcile(journal=args["journal"], authority=args["authority"], outbox_path=path)
    # Reconciler process dies after durable enqueue but before returning response.
    restarted = DurableEventJournal(args["journal"].path)
    assert (
        reconcile(journal=restarted, authority=args["authority"], outbox_path=path)["enqueued"] == 0
    )


def test_leased_delivery_crash_replays_same_event_without_stale_ack(tmp_path):
    args, path = scenario(tmp_path)
    accept_task(**args)
    reconcile(journal=args["journal"], authority=args["authority"], outbox_path=path)
    cx = connect(path)
    try:
        row, old = claim_due(cx, now=10_000_000_000)
        row_again, current = claim_due(cx, now=10_000_000_091)
        assert row["event_id"] == row_again["event_id"]
        assert old != current
        assert not finish(cx, row["event_id"], old, ok=True, now=10_000_000_092)
        assert finish(cx, row["event_id"], current, ok=True, now=10_000_000_092)
    finally:
        cx.close()


def test_opaque_id_and_unknown_schema_fail_closed(tmp_path):
    args, _ = scenario(tmp_path)
    with pytest.raises(NightShiftContractError, match="opaque"):
        accept_task(**{**args, "task": replace(args["task"], task_id="../case/private")})
