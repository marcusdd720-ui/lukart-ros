from datetime import UTC, datetime, timedelta

import pytest

from core.case_ledger.contracts import CaseId, ContentAddress, ObjectId
from core.case_product_hardening_v1 import (
    AuthorityApproval,
    CaseProductHardeningError,
    ExternalActionIdentity,
    ExternalActionReceipt,
    ReceiptOutcome,
    verify_receipt_for_transition,
)


def _identity(case: str = "CASE-LIFE-1") -> ExternalActionIdentity:
    return ExternalActionIdentity(
        case_id=CaseId(case),
        artifact_id=ObjectId("ARTIFACT-LIFE-1"),
        artifact_version="1",
        artifact_digest=ContentAddress.for_value({"artifact": "synthetic"}),
        logical_action_id="ACTION-LIFE-1",
        action_type="FILE",
        channel="SYNTHETIC",
    )


def test_receipt_unknown_cannot_prove_filed_transition() -> None:
    identity = _identity()
    receipt = ExternalActionReceipt.build(
        receipt_id="RECEIPT-UNKNOWN-1",
        identity=identity,
        attempt_id="ATTEMPT-1",
        outcome=ReceiptOutcome.UNKNOWN,
        evidence_ref="EVIDENCE-RECEIPT-1",
    )
    with pytest.raises(CaseProductHardeningError, match="does not prove confirmed success"):
        verify_receipt_for_transition(receipt, identity)


def test_receipt_for_different_action_cannot_prove_transition() -> None:
    identity = _identity("CASE-LIFE-1")
    other = _identity("CASE-LIFE-2")
    receipt = ExternalActionReceipt.build(
        receipt_id="RECEIPT-OTHER-1",
        identity=other,
        attempt_id="ATTEMPT-2",
        outcome=ReceiptOutcome.CONFIRMED_SUCCESS,
        evidence_ref="EVIDENCE-RECEIPT-2",
    )
    with pytest.raises(CaseProductHardeningError, match="does not match expected action identity"):
        verify_receipt_for_transition(receipt, identity)


def test_confirmed_matching_receipt_can_satisfy_receipt_transition_guard() -> None:
    identity = _identity()
    receipt = ExternalActionReceipt.build(
        receipt_id="RECEIPT-SUCCESS-1",
        identity=identity,
        attempt_id="ATTEMPT-3",
        outcome=ReceiptOutcome.CONFIRMED_SUCCESS,
        evidence_ref="EVIDENCE-RECEIPT-3",
    )
    verify_receipt_for_transition(receipt, identity)


def test_authority_approval_is_exact_case_artifact_action_and_time_bound() -> None:
    identity = _identity()
    now = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)
    approval = AuthorityApproval(
        approval_id="APPROVAL-1",
        actor_ref="ACTOR-1",
        authority_basis="SYNTHETIC-AUTHORITY",
        scope="FILE",
        case_id=identity.case_id,
        artifact_id=identity.artifact_id,
        artifact_version=identity.artifact_version,
        artifact_digest=identity.artifact_digest,
        action_type=identity.action_type,
        granted_at=now,
        expires_at=now + timedelta(hours=1),
    )
    assert approval.authorizes(identity, at=now + timedelta(minutes=30))
    assert not approval.authorizes(_identity("CASE-LIFE-2"), at=now + timedelta(minutes=30))
    assert not approval.authorizes(identity, at=now + timedelta(hours=2))
