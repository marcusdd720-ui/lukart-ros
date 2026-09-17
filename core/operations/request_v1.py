"""Request builder for LUKART Operation Contract v1."""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

from .types_v1 import SCHEMA_ID, SCHEMA_VERSION


def build_operation_request(
    *,
    operation_id: str,
    operation: str,
    input_payload: Mapping[str, object],
    repository: str,
    branch: str,
    worktree: str,
    case_id: str,
    runtime: str,
    authority_ref: str,
    lock_ref: str,
    expected_head: str,
    timeout_ms: int,
    allowed_side_effects: Sequence[str],
    privacy_scope: str,
    evidence_required: Sequence[str],
    idempotency_key: str,
    data_classification: str = "synthetic",
) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "request": {
            "schema_id": SCHEMA_ID,
            "version": SCHEMA_VERSION,
            "operation_id": operation_id,
            "operation": operation,
            "input": copy.deepcopy(dict(input_payload)),
        },
        "context": {
            "repository": repository,
            "branch": branch,
            "worktree": worktree,
            "case_id": case_id,
            "runtime": runtime,
        },
        "preconditions": {
            "authority_ref": authority_ref,
            "lock_ref": lock_ref,
            "expected_head": expected_head,
        },
        "constraints": {
            "timeout_ms": timeout_ms,
            "allowed_side_effects": list(allowed_side_effects),
            "privacy_scope": privacy_scope,
            "evidence_required": list(evidence_required),
        },
        "idempotency": {
            "key": idempotency_key,
            "replay": "exact",
            "duplicate_handling": "replay-or-block",
        },
        "effects": {"declared": list(allowed_side_effects), "actual": []},
        "output": {"status": None, "summary": "", "artifacts": []},
        "evidence": {"items": []},
        "errors": {"items": []},
        "privacy": {
            "scope": privacy_scope,
            "data_classification": data_classification,
            "cross_scope_allowed": False,
        },
    }
    from .validation_v1 import validate_operation_envelope

    validate_operation_envelope(envelope, response=False)
    return envelope
