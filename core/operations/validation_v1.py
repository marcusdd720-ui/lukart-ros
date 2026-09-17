"""Canonical envelope validation for LUKART Operation Contract v1."""

from __future__ import annotations

from collections.abc import Mapping

from .primitives_v1 import check_bounded
from .types_v1 import MAX_BYTES, TOP_LEVEL, OperationContractError, canonical_json
from .validate_request_v1 import validate_request_sections
from .validate_result_v1 import validate_result_sections


def validate_operation_envelope(envelope: Mapping[str, object], *, response: bool) -> None:
    if set(envelope) != TOP_LEVEL:
        raise OperationContractError("operation envelope sections are not canonical")
    check_bounded(envelope)
    if len(canonical_json(envelope).encode()) > MAX_BYTES:
        raise OperationContractError("operation envelope is oversized")
    validate_request_sections(envelope)
    validate_result_sections(envelope, response=response)
