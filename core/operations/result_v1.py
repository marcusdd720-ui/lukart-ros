"""Result and receipt builders for LUKART Operation Contract v1."""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

from .primitives_v1 import require_list, require_map, require_string
from .types_v1 import OperationContractError, OperationStatus, content_digest
from .validation_v1 import validate_operation_envelope


def build_result(
    request: Mapping[str, object],
    *,
    status: OperationStatus,
    summary: str,
    effects: Sequence[str] = (),
    artifacts: Sequence[str] = (),
    evidence: Sequence[Mapping[str, object]] = (),
    errors: Sequence[Mapping[str, object]] = (),
) -> dict[str, Any]:
    result: dict[str, Any] = copy.deepcopy(dict(request))
    declared = require_map(request["effects"], "effects")["declared"]
    result["effects"] = {
        "declared": list(require_list(declared, "effects.declared")),
        "actual": list(effects),
    }
    result["output"] = {
        "status": status.value,
        "summary": require_string(summary, "output.summary", 1_024),
        "artifacts": list(artifacts),
    }
    result["evidence"] = {"items": [dict(item) for item in evidence]}
    result["errors"] = {"items": [dict(item) for item in errors]}
    validate_operation_envelope(result, response=True)
    return result


def build_execution(
    request: Mapping[str, object],
    result: Mapping[str, object],
) -> dict[str, Any]:
    output = require_map(result["output"], "output")
    evidence = require_map(result["evidence"], "evidence")["items"]
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes, bytearray)):
        raise OperationContractError("evidence.items must be an array")
    return {
        "envelope": copy.deepcopy(dict(result)),
        "receipt": {
            "schema_id": "lukart.operation-receipt.v1",
            "request_digest": content_digest(request),
            "result_digest": content_digest(result),
            "status": output["status"],
            "artifact_refs": list(require_list(output["artifacts"], "output.artifacts")),
            "evidence_refs": [
                require_map(item, "evidence item")["ref"] for item in evidence
            ],
        },
    }
