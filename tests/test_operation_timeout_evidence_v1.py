"""Timeout and evidence adversarial tests for Operation Contract v1."""

from __future__ import annotations

import time
from collections.abc import Mapping

from core.operations import HandlerOutcome, OperationRuntime, OperationStatus
from tests.operation_v1_support import (
    COMMIT,
    HEAD,
    PRIVACY_SCOPE,
    operation_request,
    success_handler,
)


def test_timeout_can_never_report_success() -> None:
    envelope = operation_request(
        timeout_ms=1,
        allowed_side_effects=(),
        evidence_required=(),
        idempotency_key="idem:h3:timeout",
    )

    def handler(payload: Mapping[str, object], context: object) -> HandlerOutcome:
        time.sleep(0.01)
        return HandlerOutcome(status=OperationStatus.SUCCESS, summary="late")

    execution = OperationRuntime().execute(
        envelope,
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=handler,
    )
    assert execution["envelope"]["output"]["status"] == "failure"
    assert "TIMEOUT" in {item["code"] for item in execution["envelope"]["errors"]["items"]}


def test_timeout_after_reported_effect_is_partial() -> None:
    envelope = operation_request(timeout_ms=1, idempotency_key="idem:h3:partial-timeout")

    def handler(payload: Mapping[str, object], context: object) -> HandlerOutcome:
        time.sleep(0.01)
        return success_handler(payload, context)

    execution = OperationRuntime().execute(
        envelope,
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=handler,
    )
    assert execution["envelope"]["output"]["status"] == "partial"


def test_explicit_partial_status_is_preserved() -> None:
    envelope = operation_request(idempotency_key="idem:h3:partial")

    def handler(payload: Mapping[str, object], context: object) -> HandlerOutcome:
        return HandlerOutcome(
            status=OperationStatus.PARTIAL,
            summary="effect happened but follow-up failed",
            effects=("commit",),
            evidence=({"kind": "commit", "ref": "git:synthetic", "sha": COMMIT},),
            errors=(
                {
                    "code": "FOLLOW_UP_FAILED",
                    "category": "runtime",
                    "retryable": True,
                    "message": "synthetic follow-up failed",
                },
            ),
        )

    execution = OperationRuntime().execute(
        envelope,
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=handler,
    )
    assert execution["envelope"]["output"]["status"] == "partial"

