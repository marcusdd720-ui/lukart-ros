"""Handler invocation boundary for LUKART Operation Contract v1."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol, TypeVar

from .evidence_v1 import error
from .policy_v1 import finalize_outcome
from .primitives_v1 import require_map
from .result_v1 import build_execution, build_result
from .types_v1 import HandlerOutcome, OperationContractError, OperationStatus


class DeadlineContext(Protocol):
    @property
    def expired(self) -> bool:
        ...


ContextT = TypeVar("ContextT", bound=DeadlineContext)


def invoke_handler(
    request: Mapping[str, object],
    context: ContextT,
    handler: Callable[[Mapping[str, object], ContextT], HandlerOutcome],
) -> dict[str, Any]:
    try:
        section = require_map(request["request"], "request")
        payload = require_map(section["input"], "request.input")
        outcome = handler(payload, context)
        return finalize_outcome(request, outcome, expired=bool(context.expired))
    except OperationContractError:
        # Host callbacks and handler logic are untrusted: never echo raw
        # exception text (it may carry private source or credential material)
        # into the execution envelope. Keep the structured error code only.
        result = build_result(
            request,
            status=OperationStatus.FAILURE,
            summary="handler contract error; detail suppressed",
            errors=(
                error(
                    "HANDLER_CONTRACT_ERROR",
                    "contract",
                    False,
                    "handler contract error; detail suppressed",
                ),
            ),
        )
    except Exception:
        result = build_result(
            request,
            status=OperationStatus.FAILURE,
            summary="operation handler failed",
            errors=(
                error(
                    "UNHANDLED_HANDLER_ERROR",
                    "runtime",
                    False,
                    "operation handler raised an exception",
                ),
            ),
        )
    return build_execution(request, result)
