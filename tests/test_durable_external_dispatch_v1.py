from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.case_ledger import CaseId, ContentAddress, ObjectId
from core.case_product_hardening_v1 import (
    CaseProductHardeningError,
    ExternalActionIdentity,
    ExternalActionReceipt,
    ReceiptOutcome,
)
from core.durable_external_dispatch_v1 import (
    DispatchResolution,
    DurableExternalActionExecutor,
)
from core.external_action_execution_v1 import ReservationDisposition


def _identity() -> ExternalActionIdentity:
    return ExternalActionIdentity(
        case_id=CaseId("CASE-DISPATCH-TEST-001"),
        artifact_id=ObjectId("artifact-001"),
        artifact_version="v1",
        artifact_digest=ContentAddress.for_value({"artifact": "v1"}),
        logical_action_id="send-001",
        action_type="FILE",
        channel="SYNTHETIC_PROVIDER",
        payload_digest=ContentAddress.for_value({"payload": "payload-v1"}),
    )


def _receipt(
    identity: ExternalActionIdentity,
    *,
    attempt_id: str = "attempt-001",
) -> ExternalActionReceipt:
    return ExternalActionReceipt.build(
        receipt_id=f"receipt-{attempt_id}",
        identity=identity,
        attempt_id=attempt_id,
        outcome=ReceiptOutcome.CONFIRMED_SUCCESS,
        evidence_ref="synthetic-provider-receipt",
        provider_reference=f"provider-{attempt_id}",
        external_timestamp=datetime(2026, 9, 14, 9, 0, tzinfo=UTC),
    )


def test_dispatch_fence_survives_hard_crash_and_forces_reconciliation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "external-actions.sqlite"
    identity = _identity()

    with DurableExternalActionExecutor(path) as executor:
        reserved = executor.reserve(identity, attempt_id="attempt-001")
        assert reserved.disposition is ReservationDisposition.INVOKE_ALLOWED
        executor.begin_dispatch(
            identity,
            attempt_id="attempt-001",
            dispatch_ref="dispatch-001",
        )

    with DurableExternalActionExecutor(path) as executor:
        retry = executor.reserve(identity, attempt_id="attempt-002")
        assert retry.disposition is ReservationDisposition.RECONCILE_REQUIRED
        assert not retry.invoke_allowed
        fence = executor.dispatch_fence(identity, attempt_id="attempt-001")
        assert fence is not None
        assert fence.active


def test_execute_persists_fence_before_provider_and_replays_success(
    tmp_path: Path,
) -> None:
    path = tmp_path / "external-actions.sqlite"
    identity = _identity()
    calls = 0

    def provider_call() -> ExternalActionReceipt:
        nonlocal calls
        calls += 1
        with DurableExternalActionExecutor(path) as observer:
            observed = observer.reserve(identity, attempt_id="observer-attempt")
            assert observed.disposition is ReservationDisposition.RECONCILE_REQUIRED
        return _receipt(identity)

    with DurableExternalActionExecutor(path) as executor:
        receipt = executor.execute(
            identity,
            attempt_id="attempt-001",
            dispatch_ref="dispatch-001",
            provider_call=provider_call,
        )
        assert receipt.receipt_id == "receipt-attempt-001"

    with DurableExternalActionExecutor(path) as executor:
        replay = executor.execute(
            identity,
            attempt_id="attempt-002",
            dispatch_ref="dispatch-002",
            provider_call=provider_call,
        )
        assert replay == receipt

    assert calls == 1


def test_provider_exception_leaves_reconciliation_required(tmp_path: Path) -> None:
    path = tmp_path / "external-actions.sqlite"
    identity = _identity()

    def provider_call() -> ExternalActionReceipt:
        raise RuntimeError("synthetic provider timeout after dispatch")

    with DurableExternalActionExecutor(path) as executor:
        with pytest.raises(RuntimeError):
            executor.execute(
                identity,
                attempt_id="attempt-001",
                dispatch_ref="dispatch-001",
                provider_call=provider_call,
            )

    with DurableExternalActionExecutor(path) as executor:
        retry = executor.reserve(identity, attempt_id="attempt-002")
        assert retry.disposition is ReservationDisposition.RECONCILE_REQUIRED
        assert not retry.invoke_allowed


def test_crash_after_dispatch_can_recover_receipt_without_second_invoke(
    tmp_path: Path,
) -> None:
    path = tmp_path / "external-actions.sqlite"
    identity = _identity()
    receipt = _receipt(identity)

    with DurableExternalActionExecutor(path) as executor:
        executor.reserve(identity, attempt_id="attempt-001")
        executor.begin_dispatch(
            identity,
            attempt_id="attempt-001",
            dispatch_ref="dispatch-001",
        )

    with DurableExternalActionExecutor(path) as executor:
        recovered = executor.recover_receipt(
            identity,
            receipt=receipt,
            reconciliation_ref="provider-query-success-001",
        )
        assert recovered == receipt
        fence = executor.dispatch_fence(identity, attempt_id="attempt-001")
        assert fence is not None
        assert fence.resolution is DispatchResolution.SUCCESS

    with DurableExternalActionExecutor(path) as executor:
        retry = executor.reserve(identity, attempt_id="attempt-002")
        assert retry.disposition is ReservationDisposition.REPLAY_CONFIRMED
        assert not retry.invoke_allowed


def test_confirmed_no_effect_after_crash_allows_controlled_retry(
    tmp_path: Path,
) -> None:
    path = tmp_path / "external-actions.sqlite"
    identity = _identity()

    with DurableExternalActionExecutor(path) as executor:
        executor.reserve(identity, attempt_id="attempt-001")
        executor.begin_dispatch(
            identity,
            attempt_id="attempt-001",
            dispatch_ref="dispatch-001",
        )

    with DurableExternalActionExecutor(path) as executor:
        executor.confirm_no_effect(
            identity,
            attempt_id="attempt-001",
            reconciliation_ref="provider-query-no-effect-001",
        )
        fence = executor.dispatch_fence(identity, attempt_id="attempt-001")
        assert fence is not None
        assert fence.resolution is DispatchResolution.NO_EFFECT
        retry = executor.reserve(identity, attempt_id="attempt-002")
        assert retry.disposition is ReservationDisposition.INVOKE_ALLOWED
        assert retry.invoke_allowed


def test_pre_effect_failure_cannot_be_claimed_after_dispatch_started(
    tmp_path: Path,
) -> None:
    path = tmp_path / "external-actions.sqlite"
    identity = _identity()

    with DurableExternalActionExecutor(path) as executor:
        executor.reserve(identity, attempt_id="attempt-001")
        executor.begin_dispatch(
            identity,
            attempt_id="attempt-001",
            dispatch_ref="dispatch-001",
        )
        with pytest.raises(CaseProductHardeningError):
            executor.mark_pre_effect_failed(identity, attempt_id="attempt-001")


def test_receipt_attempt_must_match_dispatched_attempt(tmp_path: Path) -> None:
    path = tmp_path / "external-actions.sqlite"
    identity = _identity()

    with DurableExternalActionExecutor(path) as executor:
        executor.reserve(identity, attempt_id="attempt-001")
        executor.begin_dispatch(
            identity,
            attempt_id="attempt-001",
            dispatch_ref="dispatch-001",
        )
        with pytest.raises(CaseProductHardeningError):
            executor.confirm_success(
                identity,
                attempt_id="attempt-001",
                receipt=_receipt(identity, attempt_id="attempt-other"),
            )


def test_dispatch_ref_is_immutable_for_one_attempt(tmp_path: Path) -> None:
    path = tmp_path / "external-actions.sqlite"
    identity = _identity()

    with DurableExternalActionExecutor(path) as executor:
        executor.reserve(identity, attempt_id="attempt-001")
        first = executor.begin_dispatch(
            identity,
            attempt_id="attempt-001",
            dispatch_ref="dispatch-001",
        )
        same = executor.begin_dispatch(
            identity,
            attempt_id="attempt-001",
            dispatch_ref="dispatch-001",
        )
        assert same == first
        with pytest.raises(CaseProductHardeningError):
            executor.begin_dispatch(
                identity,
                attempt_id="attempt-001",
                dispatch_ref="dispatch-conflict",
            )
