"""Runtime, CAS, privacy and exact-replay tests for Operation Contract v1."""

from __future__ import annotations

from collections.abc import Mapping

from core.operations import HandlerOutcome, OperationRuntime, content_digest
from tests.operation_v1_support import HEAD, PRIVACY_SCOPE, operation_request, success_handler


def test_happy_path_and_receipt_are_evidence_bound() -> None:
    execution = OperationRuntime().execute(
        operation_request(),
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=success_handler,
    )
    envelope = execution["envelope"]
    assert envelope["output"]["status"] == "success"
    assert envelope["effects"]["actual"] == ["commit"]
    assert execution["receipt"]["result_digest"] == content_digest(envelope)


def test_stale_head_blocks_without_calling_handler() -> None:
    calls = 0

    def handler(payload: Mapping[str, object], context: object) -> HandlerOutcome:
        nonlocal calls
        calls += 1
        return success_handler(payload, context)

    execution = OperationRuntime().execute(
        operation_request(),
        current_head="d" * 40,
        privacy_scope=PRIVACY_SCOPE,
        handler=handler,
    )
    assert execution["envelope"]["output"]["status"] == "blocked"
    assert execution["envelope"]["errors"]["items"][0]["code"] == "STALE_HEAD"
    assert calls == 0


def test_identical_retry_replays_exact_execution_once() -> None:
    runtime = OperationRuntime()
    calls = 0
    envelope = operation_request()

    def handler(payload: Mapping[str, object], context: object) -> HandlerOutcome:
        nonlocal calls
        calls += 1
        return success_handler(payload, context)

    first = runtime.execute(
        envelope,
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=handler,
    )
    second = runtime.execute(
        envelope,
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=handler,
    )
    assert first == second
    assert calls == 1


def test_identical_retry_replays_after_repository_head_changes() -> None:
    runtime = OperationRuntime()
    calls = 0
    envelope = operation_request()

    def handler(payload: Mapping[str, object], context: object) -> HandlerOutcome:
        nonlocal calls
        calls += 1
        return success_handler(payload, context)

    first = runtime.execute(
        envelope,
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=handler,
    )
    second = runtime.execute(
        envelope,
        current_head="d" * 40,
        privacy_scope=PRIVACY_SCOPE,
        handler=handler,
    )
    assert second == first
    assert second["envelope"]["output"]["status"] == "success"
    assert calls == 1


def test_duplicate_key_with_different_digest_is_blocked() -> None:
    runtime = OperationRuntime()
    runtime.execute(
        operation_request(),
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=success_handler,
    )
    execution = runtime.execute(
        operation_request(input_payload={"path": "different.txt"}),
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=success_handler,
    )
    assert execution["envelope"]["output"]["status"] == "blocked"
    assert execution["envelope"]["errors"]["items"][0]["code"] == "IDEMPOTENCY_CONFLICT"


def test_privacy_mismatch_blocks_before_handler() -> None:
    called = False

    def handler(payload: Mapping[str, object], context: object) -> HandlerOutcome:
        nonlocal called
        called = True
        return success_handler(payload, context)

    execution = OperationRuntime().execute(
        operation_request(),
        current_head=HEAD,
        privacy_scope="case:other",
        handler=handler,
    )
    assert execution["envelope"]["output"]["status"] == "blocked"
    assert execution["envelope"]["errors"]["items"][0]["code"] == "PRIVACY_SCOPE_MISMATCH"
    assert called is False
