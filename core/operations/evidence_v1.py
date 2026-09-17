"""Bounded evidence and error normalization."""

from __future__ import annotations

import re
from collections.abc import Mapping

from .primitives_v1 import exact_keys, require_id, require_sha, require_string
from .types_v1 import OperationContractError


def normalize_error(item: Mapping[str, object]) -> dict[str, object]:
    exact_keys(item, {"code", "category", "retryable", "message"}, "error")
    retryable = item["retryable"]
    if not isinstance(retryable, bool):
        raise OperationContractError("error.retryable must be boolean")
    return {
        "code": require_id(item["code"], "error.code"),
        "category": require_id(item["category"], "error.category"),
        "retryable": retryable,
        "message": require_string(item["message"], "error.message", 512),
    }


def error(code: str, category: str, retryable: bool, message: str) -> dict[str, object]:
    return normalize_error(
        {"code": code, "category": category, "retryable": retryable, "message": message}
    )


def normalize_evidence(item: Mapping[str, object]) -> dict[str, object]:
    if set(item) - {"kind", "ref", "sha", "digest"}:
        raise OperationContractError("evidence item has unsupported keys")
    out: dict[str, object] = {
        "kind": require_id(item.get("kind"), "evidence.kind"),
        "ref": require_id(item.get("ref"), "evidence.ref"),
    }
    if item.get("sha") is not None:
        out["sha"] = require_sha(item["sha"], "evidence.sha")
    if item.get("digest") is not None:
        digest = require_string(item["digest"], "evidence.digest", 64)
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise OperationContractError("evidence.digest must be SHA-256")
        out["digest"] = digest
    return out
