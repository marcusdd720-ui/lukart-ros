"""Reference executor for LUKART Operation Contract v1."""

from __future__ import annotations

import copy
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .evidence_v1 import error
from .invoke_v1 import invoke_handler
from .ledger_v1 import IdempotencyLedger
from .primitives_v1 import require_id, require_map, require_sha
from .result_v1 import build_execution, build_result
from .types_v1 import HandlerOutcome, OperationContractError, OperationStatus, content_digest
from .validation_v1 import validate_operation_envelope


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    deadline_monotonic: float
    current_head: str
    privacy_scope: str

    @property
    def expired(self) -> bool:
        return time.monotonic() >= self.deadline_monotonic

    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline_monotonic - time.monotonic())


Handler = Callable[[Mapping[str, object], ExecutionContext], HandlerOutcome]


def _blocked(
    request: Mapping[str, object],
    code: str,
    message: str,
    retryable: bool,
) -> dict[str, Any]:
    result = build_result(
        request,
        status=OperationStatus.BLOCKED,
        summary=message,
        errors=(error(code, "precondition", retryable, message),),
    )
    return build_execution(request, result)


class OperationRuntime:
    """Digest-bound exact replay with at most one handler run per idempotency key."""

    def __init__(self) -> None:
        self._ledger = IdempotencyLedger()

    def execute(
        self,
        envelope: Mapping[str, object],
        *,
        current_head: str,
        privacy_scope: str,
        handler: Handler,
    ) -> dict[str, Any]:
        request: dict[str, Any] = copy.deepcopy(dict(envelope))
        validate_operation_envelope(request, response=False)
        current_head = require_sha(current_head, "current_head")
        privacy_scope = require_id(privacy_scope, "privacy_scope")

        preconditions = require_map(request["preconditions"], "preconditions")
        if require_map(request["privacy"], "privacy")["scope"] != privacy_scope:
            return _blocked(
                request,
                "PRIVACY_SCOPE_MISMATCH",
                "privacy scope mismatch",
                False,
            )

        idempotency = require_map(request["idempotency"], "idempotency")
        key = require_id(idempotency["key"], "idempotency.key")
        digest = content_digest(request)
        timeout = require_map(request["constraints"], "constraints")["timeout_ms"]
        if not isinstance(timeout, int) or isinstance(timeout, bool):
            raise OperationContractError("timeout must be integer")
        deadline = time.monotonic() + timeout / 1_000.0

        action, stored = self._ledger.reserve(key, digest, deadline)
        if action == "conflict":
            return _blocked(
                request,
                "IDEMPOTENCY_CONFLICT",
                "idempotency key bound to another request",
                False,
            )
        if action == "timeout":
            return _blocked(
                request,
                "IDEMPOTENCY_IN_FLIGHT_TIMEOUT",
                "matching operation remains in flight",
                True,
            )
        if action == "replay":
            if stored is None:
                raise OperationContractError("idempotency replay is missing")
            return stored

        if preconditions["expected_head"] != current_head:
            execution = _blocked(request, "STALE_HEAD", "expected head mismatch", True)
            self._ledger.complete(key, execution)
            return execution

        context = ExecutionContext(deadline, current_head, privacy_scope)
        execution = invoke_handler(request, context, handler)
        self._ledger.complete(key, execution)
        return execution
