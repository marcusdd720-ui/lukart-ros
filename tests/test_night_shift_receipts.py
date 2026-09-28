from dataclasses import replace

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.receipts import ExecutionReceipt, require_receipt_digest


def _receipt() -> ExecutionReceipt:
    h = "a" * 64
    return ExecutionReceipt(
        task_id="task-1",
        workflow_id="wf-1",
        lease_id="lease-1",
        fencing_token=1,
        policy_digest=h,
        decision_digest=h,
        state_snapshot_digest=h,
        task_capsule_digest=h,
        authority_envelope_digest=h,
        authority_reservation_digest=h,
        environment_digest=h,
        verification_digest=h,
        input_sha="d" * 40,
        output_sha="e" * 40,
        diff_digest="c" * 64,
        final_state="CLOSED_PASS",
        evidence_refs=("ci:123", "review:pass"),
    )


def test_receipt_is_content_addressed_and_order_stable() -> None:
    first = _receipt()
    second = replace(first, evidence_refs=("review:pass", "ci:123"))
    assert first.digest() == second.digest()


def test_receipt_requires_evidence() -> None:
    base = _receipt()
    with pytest.raises(NightShiftContractError):
        ExecutionReceipt(
            task_id=base.task_id,
            workflow_id=base.workflow_id,
            lease_id=base.lease_id,
            fencing_token=base.fencing_token,
            policy_digest=base.policy_digest,
            decision_digest=base.decision_digest,
            state_snapshot_digest=base.state_snapshot_digest,
            task_capsule_digest=base.task_capsule_digest,
            authority_envelope_digest=base.authority_envelope_digest,
            authority_reservation_digest=base.authority_reservation_digest,
            environment_digest=base.environment_digest,
            verification_digest=base.verification_digest,
            input_sha=base.input_sha,
            output_sha=base.output_sha,
            diff_digest=base.diff_digest,
            final_state=base.final_state,
            evidence_refs=(),
        )


def test_receipt_accepts_git_sha256_oids_too() -> None:
    base = _receipt()
    receipt = replace(
        base,
        input_sha="d" * 64,
        output_sha="e" * 64,
    )
    assert len(receipt.input_sha) == 64
    assert len(receipt.output_sha) == 64


def test_receipt_rejects_non_reportable_state() -> None:
    base = _receipt()
    with pytest.raises(NightShiftContractError, match="reportable terminal/control"):
        replace(base, final_state="RUNNING")


def test_receipt_requires_positive_fencing_token() -> None:
    base = _receipt()
    with pytest.raises(NightShiftContractError, match="fencing_token"):
        replace(base, fencing_token=0)


def test_corrupted_receipt_digest_is_rejected() -> None:
    receipt = _receipt()
    expected = receipt.digest()
    corrupted = replace(receipt, evidence_refs=("ci:tampered",))
    with pytest.raises(NightShiftContractError, match="digest mismatch"):
        require_receipt_digest(corrupted, expected_digest=expected)
