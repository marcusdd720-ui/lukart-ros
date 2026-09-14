from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.case_ledger import CanonicalCaseLedger, CaseId, ContentAddress, ObjectId
from core.case_product_hardening_v1 import (
    AuthorityApproval,
    CaseAuthorityGrant,
    CaseProductHardeningError,
    ExternalActionIdentity,
    ExternalActionReceipt,
    ReceiptOutcome,
    record_receipt_and_file_case,
)
from core.p3.contracts import RuntimeIdentity
from knowledge.models.case import Case


def _identity() -> ExternalActionIdentity:
    return ExternalActionIdentity(
        case_id=CaseId("CASE-TEMPORAL-AUTH-001"),
        artifact_id=ObjectId("artifact-001"),
        artifact_version="v1",
        artifact_digest=ContentAddress.for_value({"artifact": "v1"}),
        logical_action_id="file-001",
        action_type="FILE",
        channel="SYNTHETIC_PROVIDER",
        payload_digest=ContentAddress.for_value({"payload": "v1"}),
    )


def _approval(
    identity: ExternalActionIdentity,
    *,
    granted_at: datetime,
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> AuthorityApproval:
    return AuthorityApproval(
        approval_id="approval-001",
        actor_ref="synthetic-user",
        authority_basis="synthetic-authority",
        scope="exact-artifact-and-action",
        case_id=identity.case_id,
        artifact_id=identity.artifact_id,
        artifact_version=identity.artifact_version,
        artifact_digest=identity.artifact_digest,
        action_type=identity.action_type,
        granted_at=granted_at,
        expires_at=expires_at,
        revoked_at=revoked_at,
    )


def _runtime() -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="a" * 40,
        schema_version="test.v1",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
    )


def test_authority_approval_is_not_valid_before_grant() -> None:
    identity = _identity()
    action_time = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
    approval = _approval(identity, granted_at=action_time + timedelta(minutes=1))

    assert not approval.authorizes(identity, at=action_time)


def test_historical_authority_replay_respects_revocation_time() -> None:
    identity = _identity()
    granted_at = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
    revoked_at = granted_at + timedelta(minutes=10)
    approval = _approval(
        identity,
        granted_at=granted_at,
        revoked_at=revoked_at,
    )

    assert approval.authorizes(identity, at=granted_at + timedelta(minutes=5))
    assert not approval.authorizes(identity, at=revoked_at)

    grant = CaseAuthorityGrant(
        grant_id="grant-001",
        case_id=identity.case_id,
        actor_ref="synthetic-user",
        authority_ref="synthetic-authority",
        allowed_actions=frozenset({"CASE_CLOSED"}),
        granted_at=granted_at,
        revoked_at=revoked_at,
    )
    assert grant.authorizes(
        case_id=identity.case_id,
        action="CASE_CLOSED",
        actor_ref="synthetic-user",
        authority_ref="synthetic-authority",
        at=granted_at + timedelta(minutes=5),
    )
    assert not grant.authorizes(
        case_id=identity.case_id,
        action="CASE_CLOSED",
        actor_ref="synthetic-user",
        authority_ref="synthetic-authority",
        at=revoked_at,
    )


def test_invalid_temporal_authority_windows_fail_closed() -> None:
    identity = _identity()
    granted_at = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)

    with pytest.raises(CaseProductHardeningError):
        _approval(
            identity,
            granted_at=granted_at,
            expires_at=granted_at - timedelta(seconds=1),
        )

    with pytest.raises(CaseProductHardeningError):
        CaseAuthorityGrant(
            grant_id="grant-invalid",
            case_id=identity.case_id,
            actor_ref="synthetic-user",
            authority_ref="synthetic-authority",
            allowed_actions=frozenset({"CASE_CLOSED"}),
            granted_at=granted_at,
            revoked_at=granted_at - timedelta(seconds=1),
        )


def test_filing_rejects_approval_granted_after_external_action(tmp_path) -> None:
    identity = _identity()
    action_time = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
    receipt = ExternalActionReceipt.build(
        receipt_id="receipt-001",
        identity=identity,
        attempt_id="attempt-001",
        outcome=ReceiptOutcome.CONFIRMED_SUCCESS,
        evidence_ref="synthetic-receipt",
        external_timestamp=action_time,
        recorded_at=action_time + timedelta(minutes=2),
    )
    approval = _approval(
        identity,
        granted_at=action_time + timedelta(minutes=1),
    )
    case = Case(id=identity.case_id.value, title="Synthetic temporal authority")

    with CanonicalCaseLedger(tmp_path / "ledger.sqlite") as ledger:
        with pytest.raises(CaseProductHardeningError):
            record_receipt_and_file_case(
                case,
                ledger,
                identity=identity,
                receipt=receipt,
                approval=approval,
                runtime_identity=_runtime(),
                expected_head=None,
                policy_version="temporal-authority.v1",
                correlation_id="corr-temporal-001",
                causation_id="cause-temporal-001",
            )
        assert ledger.events(identity.case_id) == ()
