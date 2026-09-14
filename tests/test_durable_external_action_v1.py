from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier

import pytest

from core.case_ledger import CaseId, ContentAddress, ObjectId
from core.case_product_hardening_v1 import (
    ExternalActionIdentity,
    ExternalActionReceipt,
    IdempotencyConflictError,
    ReceiptOutcome,
)
from core.durable_external_action_v1 import DurableExternalActionCoordinator
from core.external_action_execution_v1 import ReservationDisposition


def _identity(*, payload: str = "payload-v1") -> ExternalActionIdentity:
    return ExternalActionIdentity(
        case_id=CaseId("CASE-DURABLE-TEST-001"),
        artifact_id=ObjectId("artifact-001"),
        artifact_version="v1",
        artifact_digest=ContentAddress.for_value({"artifact": "v1"}),
        logical_action_id="send-001",
        action_type="FILE",
        channel="SYNTHETIC_PROVIDER",
        payload_digest=ContentAddress.for_value({"payload": payload}),
    )


def _receipt(identity: ExternalActionIdentity) -> ExternalActionReceipt:
    return ExternalActionReceipt.build(
        receipt_id="receipt-001",
        identity=identity,
        attempt_id="attempt-001",
        outcome=ReceiptOutcome.CONFIRMED_SUCCESS,
        evidence_ref="synthetic-provider-receipt",
        provider_reference="provider-ref-001",
        external_timestamp=datetime(2026, 9, 14, 8, 0, tzinfo=UTC),
    )


def test_restart_preserves_unknown_and_recovered_receipt(tmp_path: Path) -> None:
    path = tmp_path / "external-actions.sqlite"
    identity = _identity()
    receipt = _receipt(identity)

    with DurableExternalActionCoordinator(path) as coordinator:
        first = coordinator.reserve(identity, attempt_id="attempt-001")
        assert first.disposition is ReservationDisposition.INVOKE_ALLOWED
        coordinator.mark_outcome_unknown(identity, attempt_id="attempt-001")

    with DurableExternalActionCoordinator(path) as coordinator:
        retry = coordinator.reserve(identity, attempt_id="attempt-002")
        assert retry.disposition is ReservationDisposition.RECONCILE_REQUIRED
        assert not retry.invoke_allowed
        recovered = coordinator.recover_receipt(
            identity,
            receipt=receipt,
            reconciliation_ref="provider-lookup-001",
        )
        assert recovered.receipt == receipt

    with DurableExternalActionCoordinator(path) as coordinator:
        replay = coordinator.reserve(identity, attempt_id="attempt-003")
        assert replay.disposition is ReservationDisposition.REPLAY_CONFIRMED
        assert not replay.invoke_allowed
        assert replay.record.receipt == receipt


def test_two_workers_share_one_atomic_reservation(tmp_path: Path) -> None:
    path = tmp_path / "external-actions.sqlite"
    identity = _identity()
    barrier = Barrier(2)

    def reserve(attempt_id: str) -> ReservationDisposition:
        with DurableExternalActionCoordinator(path) as coordinator:
            barrier.wait(timeout=10)
            return coordinator.reserve(identity, attempt_id=attempt_id).disposition

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                reserve,
                ("attempt-worker-a", "attempt-worker-b"),
            )
        )

    assert results.count(ReservationDisposition.INVOKE_ALLOWED) == 1
    assert results.count(ReservationDisposition.IN_PROGRESS) == 1


def test_restart_rejects_changed_immutable_intent(tmp_path: Path) -> None:
    path = tmp_path / "external-actions.sqlite"
    original = _identity(payload="payload-one")
    changed = _identity(payload="payload-two")

    with DurableExternalActionCoordinator(path) as coordinator:
        coordinator.reserve(original, attempt_id="attempt-001")

    with DurableExternalActionCoordinator(path) as coordinator:
        with pytest.raises(IdempotencyConflictError):
            coordinator.reserve(changed, attempt_id="attempt-002")


def test_pre_effect_failure_allows_retry_after_restart(tmp_path: Path) -> None:
    path = tmp_path / "external-actions.sqlite"
    identity = _identity()

    with DurableExternalActionCoordinator(path) as coordinator:
        coordinator.reserve(identity, attempt_id="attempt-001")
        coordinator.mark_pre_effect_failed(identity, attempt_id="attempt-001")

    with DurableExternalActionCoordinator(path) as coordinator:
        retry = coordinator.reserve(identity, attempt_id="attempt-002")
        assert retry.disposition is ReservationDisposition.INVOKE_ALLOWED
        assert retry.record.owner_attempt_id == "attempt-002"
        assert retry.record.attempt_count == 2


def test_confirmed_no_effect_allows_retry_after_restart(tmp_path: Path) -> None:
    path = tmp_path / "external-actions.sqlite"
    identity = _identity()

    with DurableExternalActionCoordinator(path) as coordinator:
        coordinator.reserve(identity, attempt_id="attempt-001")
        coordinator.mark_outcome_unknown(identity, attempt_id="attempt-001")
        coordinator.confirm_no_effect(
            identity,
            reconciliation_ref="provider-no-effect-001",
        )

    with DurableExternalActionCoordinator(path) as coordinator:
        retry = coordinator.reserve(identity, attempt_id="attempt-002")
        assert retry.disposition is ReservationDisposition.INVOKE_ALLOWED
        assert retry.record.attempt_count == 2


def test_duplicate_success_callback_is_idempotent_after_restart(tmp_path: Path) -> None:
    path = tmp_path / "external-actions.sqlite"
    identity = _identity()
    receipt = _receipt(identity)

    with DurableExternalActionCoordinator(path) as coordinator:
        coordinator.reserve(identity, attempt_id="attempt-001")
        coordinator.confirm_success(
            identity,
            attempt_id="attempt-001",
            receipt=receipt,
        )

    with DurableExternalActionCoordinator(path) as coordinator:
        duplicate = coordinator.confirm_success(
            identity,
            attempt_id="attempt-001",
            receipt=receipt,
        )
        assert duplicate.receipt == receipt
        replay = coordinator.reserve(identity, attempt_id="attempt-002")
        assert replay.disposition is ReservationDisposition.REPLAY_CONFIRMED
        assert not replay.invoke_allowed
