"""H4 contract assurance and adversarial coverage for Operation Contract v1."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from core.operations import HandlerOutcome, OperationRuntime
from factory.quality.case_regression_suite import load_suite
from tests.operation_v1_support import HEAD, PRIVACY_SCOPE, operation_request, success_handler


def test_all_operation_v1_modules_are_registered_in_canonical_batch() -> None:
    repo_root = Path(__file__).parents[2]
    suite = load_suite(repo_root / "docs" / "CASE_REGRESSION_SUITE.md", repo_root=repo_root)
    registered = {case.pytest_node.split("::", 1)[0] for case in suite.batch_cases}
    operation_modules = {
        path.relative_to(repo_root).as_posix()
        for path in (repo_root / "tests").glob("test_operation_*_v1.py")
    }

    assert operation_modules
    assert operation_modules <= registered


def test_idempotency_conflict_never_calls_conflicting_handler() -> None:
    runtime = OperationRuntime()
    key = "idem:h4:conflict-no-side-effect"
    runtime.execute(
        operation_request(idempotency_key=key),
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=success_handler,
    )
    calls = 0

    def conflicting_handler(payload: Mapping[str, object], context: object) -> HandlerOutcome:
        nonlocal calls
        calls += 1
        return success_handler(payload, context)

    execution = runtime.execute(
        operation_request(
            idempotency_key=key,
            input_payload={"path": "synthetic-conflict.txt"},
        ),
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=conflicting_handler,
    )

    assert execution["envelope"]["output"]["status"] == "blocked"
    assert execution["envelope"]["errors"]["items"][0]["code"] == "IDEMPOTENCY_CONFLICT"
    assert calls == 0


def test_handler_exception_is_sanitized_failure_and_exact_replayed() -> None:
    runtime = OperationRuntime()
    envelope = operation_request(idempotency_key="idem:h4:handler-exception")

    def exploding_handler(payload: Mapping[str, object], context: object) -> HandlerOutcome:
        raise RuntimeError("synthetic-sensitive-internal-detail")

    first = runtime.execute(
        envelope,
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=exploding_handler,
    )
    error = first["envelope"]["errors"]["items"][0]
    assert first["envelope"]["output"]["status"] == "failure"
    assert error["code"] == "UNHANDLED_HANDLER_ERROR"
    assert "synthetic-sensitive-internal-detail" not in error["message"]

    replay_handler_calls = 0

    def replay_handler(payload: Mapping[str, object], context: object) -> HandlerOutcome:
        nonlocal replay_handler_calls
        replay_handler_calls += 1
        return success_handler(payload, context)

    second = runtime.execute(
        envelope,
        current_head="d" * 40,
        privacy_scope=PRIVACY_SCOPE,
        handler=replay_handler,
    )

    assert second == first
    assert replay_handler_calls == 0


def test_malformed_handler_status_fails_closed_without_success() -> None:
    def malformed_handler(payload: Mapping[str, object], context: object) -> HandlerOutcome:
        return HandlerOutcome(status="unknown", summary="synthetic invalid status")

    execution = OperationRuntime().execute(
        operation_request(idempotency_key="idem:h4:malformed-handler"),
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=malformed_handler,
    )

    assert execution["envelope"]["output"]["status"] == "failure"
    assert execution["envelope"]["effects"]["actual"] == []
    assert execution["envelope"]["errors"]["items"][0]["code"] == "HANDLER_CONTRACT_ERROR"


def test_stale_head_block_is_exact_replayed_after_head_recovers() -> None:
    runtime = OperationRuntime()
    envelope = operation_request(idempotency_key="idem:h4:stale-replay")
    calls = 0

    def handler(payload: Mapping[str, object], context: object) -> HandlerOutcome:
        nonlocal calls
        calls += 1
        return success_handler(payload, context)

    first = runtime.execute(
        envelope,
        current_head="d" * 40,
        privacy_scope=PRIVACY_SCOPE,
        handler=handler,
    )
    second = runtime.execute(
        envelope,
        current_head=HEAD,
        privacy_scope=PRIVACY_SCOPE,
        handler=handler,
    )

    assert first["envelope"]["output"]["status"] == "blocked"
    assert first["envelope"]["errors"]["items"][0]["code"] == "STALE_HEAD"
    assert second == first
    assert calls == 0
