"""Synthetic fixtures for Operation Contract v1 conformance tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.operations import HandlerOutcome, OperationStatus, build_operation_request

HEAD = "a" * 40
COMMIT = "b" * 40
PRIVACY_SCOPE = "case:test-h3"


def operation_request(**overrides: object) -> dict[str, Any]:
    values: dict[str, object] = {
        "operation_id": "op-h3-001",
        "operation": "repo.write",
        "input_payload": {"path": "synthetic.txt", "content_digest": "c" * 64},
        "repository": "synthetic/lukart-h3",
        "branch": "case-testy/h3",
        "worktree": "cloud",
        "case_id": "CASE-TESTY-H3",
        "runtime": "pytest",
        "authority_ref": "auth:synthetic",
        "lock_ref": "lock:synthetic",
        "expected_head": HEAD,
        "timeout_ms": 5_000,
        "allowed_side_effects": ("commit",),
        "privacy_scope": PRIVACY_SCOPE,
        "evidence_required": ("commit",),
        "idempotency_key": "idem:h3:001",
    }
    values.update(overrides)
    return build_operation_request(**values)  # type: ignore[arg-type]


def success_handler(
    payload: Mapping[str, object],
    context: object,
) -> HandlerOutcome:
    return HandlerOutcome(
        status=OperationStatus.SUCCESS,
        summary="synthetic commit recorded",
        effects=("commit",),
        artifacts=("artifact:synthetic",),
        evidence=({"kind": "commit", "ref": "git:synthetic", "sha": COMMIT},),
    )
