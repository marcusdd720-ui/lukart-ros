"""Receipt durability and stale-lease rejection for the existing Groq builder.

Tests use the real SQLite LeaseStore and hash-chained journal, while mocking
only the child process and the external Groq broker. No secret/network needed.
"""
from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.night_shift import groq_builder_integration as integration
from core.night_shift.contracts import NightShiftContractError
from core.night_shift.groq_builder_scope import ApprovedBuilderScope
from core.night_shift.groq_local_broker import GroqBrokerPolicy
from core.night_shift.journal import DurableEventJournal
from core.night_shift.leases import LeaseStore

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux bwrap policy")


def _rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *,
         lease_owner: str = "worker-1", expired: bool = False) -> dict:
    worktree = tmp_path / "isolated"
    worktree.mkdir()
    gitdir = tmp_path / "private-host-gitdir"
    gitdir.mkdir()
    (worktree / ".git").write_text(f"gitdir: {gitdir}\n")
    journal_db = tmp_path / "existing-state.db"
    leases = LeaseStore(journal_db)
    journal = DurableEventJournal(journal_db)
    started = int(time.time())
    lease = leases.acquire(
        task_id="scope-fixture", lease_id="lease-fixture", worker_id=lease_owner,
        now_epoch=started - 120 if expired else started,
        ttl_seconds=30 if expired else 120,
    )
    argv = integration._required_isolated_bwrap_prefix(
        SimpleNamespace(worktree=worktree), tmp_path / "private.sock",
    ) + ("/usr/bin/python3", "-c", "print('synthetic')")
    plan = SimpleNamespace(
        role="BUILDER", task_id=lease.task_id, worker_id="worker-1",
        worktree=worktree, base_sha="a" * 40,
        executable=Path("/usr/bin/bwrap"), arguments=argv,
        lease_id=lease.lease_id, fencing_token=lease.fencing_token,
    )
    scope = ApprovedBuilderScope(
        task_id=lease.task_id, worktree=worktree,
        branch="night-shift/scope-fixture", base_sha=plan.base_sha,
        allowed_files=("fixed.py",),
    )
    broker_policy = GroqBrokerPolicy(
        task_id=lease.task_id, task_marker="ISOLATED_SCOPE_FIXTURE_2026",
    )

    class SyntheticBroker:
        def __init__(self, **_kwargs: object) -> None:
            self.evidence = SimpleNamespace(
                attempts=1, denied=0, client_disconnected=False,
                response_overflow=False, upstream_statuses=[200],
                response_bytes=36, upstream_incomplete=False,
            )

        def __enter__(self) -> SyntheticBroker:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    class SyntheticBridge:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def execute(self, _plan: object) -> SimpleNamespace:
            return SimpleNamespace(
                status="EXITED_ZERO", exit_code=0, pid=456,
                plan_digest="b" * 64,
            )

    monkeypatch.setattr(integration, "read_groq_key", lambda _path: "gsk_" + "Z" * 32)
    monkeypatch.setattr(integration, "GroqLocalBroker", SyntheticBroker)
    monkeypatch.setattr(integration, "ChildProcessBridge", SyntheticBridge)
    monkeypatch.setattr(
        integration, "verify_builder_changes", lambda _scope: {"fixed.py": "e" * 64}
    )

    return dict(
        leases=leases, journal=journal, plan=plan, scope=scope,
        broker_policy=broker_policy, auth_file=tmp_path / "not-loaded",
        broker_socket=tmp_path / "private.sock",
        pinned_launch_arguments_sha256=hashlib.sha256("\0".join(argv).encode()).hexdigest(),
        trusted_admission_checker=lambda _candidate: True,
    )


def test_receipt_persists_to_existing_hash_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    params = _rig(tmp_path, monkeypatch)
    outcome = integration.run_scoped_builder(**params)
    events = params["journal"].verify_chain(workflow_id="child-bridge:scope-fixture")
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "BUILDER_SCOPE_RECEIPT"
    assert event.event_id == "child-bridge:scope-fixture:scope-receipt"
    assert event.payload["modified_file_digests"] == {"fixed.py": "e" * 64}
    assert event.payload["plan_digest"] == outcome.plan_digest
    assert event.payload["lease_id"] == "lease-fixture"
    assert event.payload["fencing_token"] == 1
    assert event.payload["pid"] == outcome.process_pid
    assert event.payload["acceptance"] == "SCOPE_ONLY_NOT_CODE_REVIEW"
    assert "gsk_" not in repr(event)


def test_scope_receipt_rejects_expired_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    params = _rig(tmp_path, monkeypatch, expired=True)
    with pytest.raises(NightShiftContractError, match="expired"):
        integration.run_scoped_builder(**params)
    assert not params["journal"].events(workflow_id="child-bridge:scope-fixture")


def test_scope_receipt_rejects_mismatched_lease_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    params = _rig(tmp_path, monkeypatch, lease_owner="other-worker")
    with pytest.raises(NightShiftContractError, match="lease owner"):
        integration.run_scoped_builder(**params)
    assert not params["journal"].events(workflow_id="child-bridge:scope-fixture")


def test_scope_receipt_write_failure_does_not_return_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    params = _rig(tmp_path, monkeypatch)

    def disk_full(**_kwargs: object) -> bool:
        raise OSError("disk full")

    monkeypatch.setattr(params["journal"], "append_event", disk_full)
    with pytest.raises(OSError, match="disk full"):
        integration.run_scoped_builder(**params)


def test_scope_receipt_duplicate_requires_reconciliation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    params = _rig(tmp_path, monkeypatch)
    integration.run_scoped_builder(**params)
    with pytest.raises(NightShiftContractError, match="reused|already recorded"):
        integration.run_scoped_builder(**params)
    assert len(params["journal"].verify_chain(workflow_id="child-bridge:scope-fixture")) == 1


def test_rejected_scope_never_emits_scope_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    params = _rig(tmp_path, monkeypatch)

    def reject(_scope: ApprovedBuilderScope) -> dict[str, str]:
        raise NightShiftContractError("unapproved file")

    monkeypatch.setattr(integration, "verify_builder_changes", reject)
    with pytest.raises(NightShiftContractError, match="unapproved file"):
        integration.run_scoped_builder(**params)
    assert not params["journal"].events(workflow_id="child-bridge:scope-fixture")


def test_scope_receipt_lease_rotates_during_append_refuses_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    params = _rig(tmp_path, monkeypatch)
    original = params["journal"].append_event

    def rotate_after_write(**event: object) -> bool:
        inserted = original(**event)
        lease = params["leases"].require_current(
            task_id="scope-fixture", lease_id="lease-fixture", fencing_token=1,
            now_epoch=int(time.time()),
        )
        params["leases"].acquire(
            task_id="scope-fixture", lease_id="new-owner", worker_id="worker-2",
            now_epoch=lease.expires_at_epoch, ttl_seconds=120,
        )
        return inserted

    monkeypatch.setattr(params["journal"], "append_event", rotate_after_write)
    with pytest.raises(NightShiftContractError, match="stale lease"):
        integration.run_scoped_builder(**params)
    events = params["journal"].verify_chain(workflow_id="child-bridge:scope-fixture")
    assert len(events) == 1
    assert events[0].event_type == "BUILDER_SCOPE_RECEIPT"
    # The journal records an ambiguous result requiring reconciliation; no PASS.


def test_incomplete_upstream_never_produces_scope_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    params = _rig(tmp_path, monkeypatch)
    MockBroker = integration.GroqLocalBroker

    class IncompleteBroker(MockBroker):
        def __enter__(self):
            super().__enter__()
            self.evidence.upstream_incomplete = True
            return self

    monkeypatch.setattr(integration, "GroqLocalBroker", IncompleteBroker)
    with pytest.raises(NightShiftContractError, match="evidence incomplete"):
        integration.run_scoped_builder(**params)
    assert not params["journal"].events(workflow_id="child-bridge:scope-fixture")
