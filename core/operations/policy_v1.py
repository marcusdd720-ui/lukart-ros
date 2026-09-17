"""Post-handler safety policy for LUKART Operation Contract v1."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .evidence_v1 import error, normalize_error, normalize_evidence
from .primitives_v1 import require_list, require_map, require_string
from .result_v1 import build_execution, build_result
from .types_v1 import HandlerOutcome, OperationContractError, OperationStatus


def finalize_outcome(
    request: Mapping[str, object],
    outcome: HandlerOutcome,
    *,
    expired: bool,
) -> dict[str, Any]:
    try:
        status = OperationStatus(str(outcome.status))
    except ValueError as exc:
        raise OperationContractError("handler returned unsupported status") from exc

    summary = require_string(outcome.summary, "handler.summary", 1_024)
    effects = require_list(outcome.effects, "handler.effects")
    artifacts = require_list(outcome.artifacts, "handler.artifacts")
    evidence = tuple(normalize_evidence(item) for item in outcome.evidence)
    errors = tuple(normalize_error(item) for item in outcome.errors)

    constraints = require_map(request["constraints"], "constraints")
    allowed = set(
        require_list(constraints["allowed_side_effects"], "constraints.allowed_side_effects")
    )
    if set(effects) - allowed:
        status = OperationStatus.PARTIAL if effects else OperationStatus.FAILURE
        errors += (
            error("UNDECLARED_SIDE_EFFECT", "effects", False, "undeclared effect reported"),
        )

    kinds = {str(item["kind"]) for item in evidence}
    required = set(require_list(constraints["evidence_required"], "constraints.evidence_required"))
    missing = required - kinds
    commit_evidence = any(
        item.get("kind") == "commit" and isinstance(item.get("sha"), str)
        for item in evidence
    )
    if "commit" in effects and not commit_evidence:
        missing.add("commit:exact-sha")
    if missing:
        status = OperationStatus.PARTIAL if effects else OperationStatus.FAILURE
        errors += error("EVIDENCE_MISSING", "evidence", True, "required evidence is missing"),

    if expired:
        status = OperationStatus.PARTIAL if effects else OperationStatus.FAILURE
        errors += error("TIMEOUT", "timeout", True, "operation exceeded declared timeout"),

    if effects and status in {
        OperationStatus.FAILURE,
        OperationStatus.BLOCKED,
        OperationStatus.SKIPPED,
    }:
        status = OperationStatus.PARTIAL
    if status is OperationStatus.SUCCESS and errors:
        status = OperationStatus.PARTIAL if effects else OperationStatus.FAILURE

    result = build_result(
        request,
        status=status,
        summary=summary,
        effects=effects,
        artifacts=artifacts,
        evidence=evidence,
        errors=errors,
    )
    return build_execution(request, result)
