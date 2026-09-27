from dataclasses import replace

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.receipts import ExecutionReceipt


def _receipt() -> ExecutionReceipt:
    h = "a" * 64
    return ExecutionReceipt(
        task_id="task-1",
        policy_digest=h,
        state_snapshot_digest=h,
        task_capsule_digest=h,
        authority_envelope_digest=h,
        authority_reservation_digest=h,
        environment_digest=h,
        input_sha=h,
        output_sha="b" * 64,
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
            policy_digest=base.policy_digest,
            state_snapshot_digest=base.state_snapshot_digest,
            task_capsule_digest=base.task_capsule_digest,
            authority_envelope_digest=base.authority_envelope_digest,
            authority_reservation_digest=base.authority_reservation_digest,
            environment_digest=base.environment_digest,
            input_sha=base.input_sha,
            output_sha=base.output_sha,
            diff_digest=base.diff_digest,
            final_state=base.final_state,
            evidence_refs=(),
        )
