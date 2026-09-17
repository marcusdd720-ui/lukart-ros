"""Result-side validation for LUKART Operation Contract v1."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .evidence_v1 import normalize_error, normalize_evidence
from .primitives_v1 import exact_keys, require_id, require_list, require_map
from .types_v1 import MAX_ITEMS, OperationContractError, OperationStatus


def _items(envelope: Mapping[str, object], section: str) -> Sequence[object]:
    obj = require_map(envelope[section], section)
    exact_keys(obj, {"items"}, section)
    items = obj["items"]
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
        raise OperationContractError(f"{section}.items is invalid")
    if len(items) > MAX_ITEMS:
        raise OperationContractError(f"{section}.items is invalid")
    normalizer = normalize_evidence if section == "evidence" else normalize_error
    for item in items:
        normalizer(require_map(item, f"{section}.item"))
    return items


def _validate_success_semantics(envelope: Mapping[str, object]) -> None:
    effects = require_map(envelope["effects"], "effects")
    declared = set(require_list(effects["declared"], "effects.declared"))
    actual = set(require_list(effects["actual"], "effects.actual"))
    if actual - declared:
        raise OperationContractError("successful result contains undeclared effects")

    constraints = require_map(envelope["constraints"], "constraints")
    required = set(require_list(constraints["evidence_required"], "constraints.evidence_required"))
    evidence = _items(envelope, "evidence")
    normalized = [normalize_evidence(require_map(item, "evidence.item")) for item in evidence]
    kinds = {str(item["kind"]) for item in normalized}
    if required - kinds:
        raise OperationContractError("successful result is missing required evidence")
    if "commit" in actual and not any(
        item.get("kind") == "commit" and isinstance(item.get("sha"), str)
        for item in normalized
    ):
        raise OperationContractError("successful commit result is missing exact SHA evidence")


def validate_result_sections(envelope: Mapping[str, object], *, response: bool) -> None:
    output = require_map(envelope["output"], "output")
    exact_keys(output, {"status", "summary", "artifacts"}, "output")
    statuses = {status.value for status in OperationStatus}
    if response:
        if output["status"] not in statuses:
            raise OperationContractError("invalid output.status")
        summary = output["summary"]
        if not isinstance(summary, str) or not summary.strip() or len(summary) > 1_024:
            raise OperationContractError("output.summary is invalid")
    elif output["status"] is not None or output["summary"] != "":
        raise OperationContractError("request output must be empty")
    artifacts = require_list(output["artifacts"], "output.artifacts")

    evidence = _items(envelope, "evidence")
    errors = _items(envelope, "errors")

    effects = require_map(envelope["effects"], "effects")
    actual = require_list(effects["actual"], "effects.actual")
    if not response and (actual or artifacts or evidence or errors):
        raise OperationContractError("request result fields must be empty")
    if response and actual and output["status"] not in {
        OperationStatus.SUCCESS.value,
        OperationStatus.PARTIAL.value,
    }:
        raise OperationContractError("result with effects must be success or partial")
    if response and output["status"] == OperationStatus.SUCCESS.value:
        if errors:
            raise OperationContractError("successful result cannot contain errors")
        _validate_success_semantics(envelope)

    constraints = require_map(envelope["constraints"], "constraints")
    privacy = require_map(envelope["privacy"], "privacy")
    exact_keys(privacy, {"scope", "data_classification", "cross_scope_allowed"}, "privacy")
    scope = require_id(privacy["scope"], "privacy.scope")
    require_id(privacy["data_classification"], "privacy.data_classification")
    if privacy["cross_scope_allowed"] is not False or scope != constraints["privacy_scope"]:
        raise OperationContractError("privacy scope invariant failed")
