"""Concurrency and deterministic replay tests for Operation Contract v1."""

from __future__ import annotations

import copy
import threading
import time
from collections.abc import Mapping
from typing import Any

from core.operations import HandlerOutcome, OperationRuntime, canonical_json, content_digest
from tests.operation_v1_support import HEAD, PRIVACY_SCOPE, operation_request, success_handler


def test_concurrent_identical_invocation_executes_handler_once() -> None:
    runtime = OperationRuntime()
    envelope = operation_request(idempotency_key="idem:h3:concurrent")
    calls = 0
    barrier = threading.Barrier(2)
    results: list[dict[str, Any]] = []

    def handler(payload: Mapping[str, object], context: object) -> HandlerOutcome:
        nonlocal calls
        calls += 1
        time.sleep(0.03)
        return success_handler(payload, context)

    def invoke() -> None:
        barrier.wait()
        results.append(
            runtime.execute(
                envelope,
                current_head=HEAD,
                privacy_scope=PRIVACY_SCOPE,
                handler=handler,
            )
        )

    threads = [threading.Thread(target=invoke) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert calls == 1
    assert len(results) == 2
    assert results[0] == results[1]


def test_replay_and_serialization_are_deterministic() -> None:
    left = operation_request(idempotency_key="idem:h3:deterministic")
    right = copy.deepcopy(left)
    assert canonical_json(left) == canonical_json(right)
    assert content_digest(left) == content_digest(right)

    runtime = OperationRuntime()
    first = runtime.execute(
        left,
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=success_handler,
    )
    second = runtime.execute(
        right,
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=success_handler,
    )
    assert canonical_json(first) == canonical_json(second)
