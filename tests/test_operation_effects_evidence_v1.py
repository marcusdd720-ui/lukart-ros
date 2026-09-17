"""Effect declaration and evidence adversarial tests for Operation Contract v1."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from core.operations import (
    HandlerOutcome,
    OperationContractError,
    OperationRuntime,
    OperationStatus,
    validate_operation_envelope,
)
from tests.operation_v1_support import COMMIT, HEAD, PRIVACY_SCOPE, operation_request


def test_missing_required_evidence_prevents_success() -> None:
    def handler(payload: Mapping[str, object], context: object) -> HandlerOutcome:
        return HandlerOutcome(
            status=OperationStatus.SUCCESS,
            summary="reported effect without evidence",
            effects=("commit",),
        )

    execution = OperationRuntime().execute(
        operation_request(idempotency_key="idem:h3:no-evidence"),
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=handler,
    )
    assert execution["envelope"]["output"]["status"] == "partial"
    assert "EVIDENCE_MISSING" in {
        item["code"] for item in execution["envelope"]["errors"]["items"]
    }


def test_undeclared_side_effect_can_never_be_success() -> None:
    def handler(payload: Mapping[str, object], context: object) -> HandlerOutcome:
        return HandlerOutcome(
            status=OperationStatus.SUCCESS,
            summary="unexpected effect",
            effects=("commit",),
            evidence=({"kind": "commit", "ref": "git:synthetic", "sha": COMMIT},),
        )

    execution = OperationRuntime().execute(
        operation_request(
            allowed_side_effects=(),
            evidence_required=(),
            idempotency_key="idem:h3:hidden-effect",
        ),
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=handler,
    )
    assert execution["envelope"]["output"]["status"] != "success"
    assert "UNDECLARED_SIDE_EFFECT" in {
        item["code"] for item in execution["envelope"]["errors"]["items"]
    }


def test_commit_effect_requires_exact_sha_evidence() -> None:
    def handler(payload: Mapping[str, object], context: object) -> HandlerOutcome:
        return HandlerOutcome(
            status=OperationStatus.SUCCESS,
            summary="commit ref without sha",
            effects=("commit",),
            evidence=({"kind": "commit", "ref": "git:synthetic"},),
        )

    execution = OperationRuntime().execute(
        operation_request(idempotency_key="idem:h3:exact-sha"),
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=handler,
    )
    assert execution["envelope"]["output"]["status"] == "partial"
    assert execution["envelope"]["errors"]["items"][0]["code"] == "EVIDENCE_MISSING"


def test_direct_response_validation_rejects_false_success_without_evidence() -> None:
    envelope = operation_request(idempotency_key="idem:h3:false-success")
    envelope["effects"]["actual"] = ["commit"]
    envelope["output"] = {
        "status": "success",
        "summary": "unproved synthetic success",
        "artifacts": [],
    }
    with pytest.raises(OperationContractError, match="missing required evidence"):
        validate_operation_envelope(envelope, response=True)
