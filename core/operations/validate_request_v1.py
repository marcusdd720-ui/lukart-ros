"""Request-side validation for LUKART Operation Contract v1."""

from __future__ import annotations

from collections.abc import Mapping

from .primitives_v1 import exact_keys, require_id, require_list, require_map, require_sha
from .types_v1 import SCHEMA_ID, SCHEMA_VERSION, OperationContractError


def validate_request_sections(envelope: Mapping[str, object]) -> None:
    request = require_map(envelope["request"], "request")
    exact_keys(request, {"schema_id", "version", "operation_id", "operation", "input"}, "request")
    if request["schema_id"] != SCHEMA_ID:
        raise OperationContractError(f"unsupported schema_id: {request['schema_id']}")
    if request["version"] != SCHEMA_VERSION:
        raise OperationContractError(f"unsupported version: {request['version']}")
    require_id(request["operation_id"], "request.operation_id")
    require_id(request["operation"], "request.operation")
    require_map(request["input"], "request.input")

    context = require_map(envelope["context"], "context")
    exact_keys(context, {"repository", "branch", "worktree", "case_id", "runtime"}, "context")
    for key in context:
        require_id(context[key], f"context.{key}")

    preconditions = require_map(envelope["preconditions"], "preconditions")
    exact_keys(
        preconditions,
        {"authority_ref", "lock_ref", "expected_head"},
        "preconditions",
    )
    require_id(preconditions["authority_ref"], "preconditions.authority_ref")
    require_id(preconditions["lock_ref"], "preconditions.lock_ref")
    require_sha(preconditions["expected_head"], "preconditions.expected_head")

    constraints = require_map(envelope["constraints"], "constraints")
    exact_keys(
        constraints,
        {"timeout_ms", "allowed_side_effects", "privacy_scope", "evidence_required"},
        "constraints",
    )
    timeout = constraints["timeout_ms"]
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 300_000:
        raise OperationContractError("constraints.timeout_ms must be 1..300000")
    allowed = require_list(
        constraints["allowed_side_effects"],
        "constraints.allowed_side_effects",
    )
    require_id(constraints["privacy_scope"], "constraints.privacy_scope")
    require_list(constraints["evidence_required"], "constraints.evidence_required")

    idempotency = require_map(envelope["idempotency"], "idempotency")
    exact_keys(idempotency, {"key", "replay", "duplicate_handling"}, "idempotency")
    require_id(idempotency["key"], "idempotency.key")
    if idempotency["replay"] != "exact" or idempotency["duplicate_handling"] != "replay-or-block":
        raise OperationContractError("unsupported idempotency semantics")

    effects = require_map(envelope["effects"], "effects")
    exact_keys(effects, {"declared", "actual"}, "effects")
    if require_list(effects["declared"], "effects.declared") != allowed:
        raise OperationContractError("declared effects mismatch")
    require_list(effects["actual"], "effects.actual")
