"""LUKART LEGAL OS read-only ROS -> WORK assessment adapter (shadow only).

Uses the existing ROS operation envelope/runtime; does not import WORK, draft,
write case data, grant HUMAN approval, release, or export private source bytes.
A trusted host must provide two independent scoped callbacks.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from .primitives_v1 import exact_keys, require_id, require_map, require_sha
from .runtime_v1 import OperationRuntime
from .types_v1 import HandlerOutcome, OperationContractError, OperationStatus
from .validation_v1 import validate_operation_envelope

ASSESS = "ros.work.generator.assess.v1"
SUPPORTED_CANDIDATE_TYPES = frozenset({
    "PL-PRE-PAYMENT-1",
    "PL-PRE-COMPLAINT-1",
    "PL-PRE-REPLY-1",
})
_INPUT_FIELDS = {"tenant_id", "work_case_id", "candidate_sha", "type_id"}
_SNAPSHOT_FIELDS = {
    "tenant_id", "case_id", "candidate_sha", "type_id",
    "work_state_ref", "work_digest",
}
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")

AuthorityResolver = Callable[[str, str, str, str], object | None]
WorkSnapshotReader = Callable[[object, str, str, str, str], Mapping[str, object]]


def assess_legal_os_readonly(
    envelope: Mapping[str, object],
    *,
    current_head: str,
    privacy_scope: str,
    authority_resolver: AuthorityResolver | None = None,
    work_reader: WorkSnapshotReader | None = None,
    runtime: OperationRuntime | None = None,
) -> dict[str, Any]:
    """Read scoped WORK state identity, never accept client legal/release PASS.

    An OperationStatus.SUCCESS only states that an authorized *read* returned
    an exact-bound WORK provenance reference. It is not product readiness.
    """
    validate_operation_envelope(envelope, response=False)
    request = require_map(envelope["request"], "request")
    if request["operation"] != ASSESS:
        raise OperationContractError("LEGAL_OS_OPERATION_UNSUPPORTED")
    constraints = require_map(envelope["constraints"], "constraints")
    if constraints["allowed_side_effects"] != []:
        raise OperationContractError("LEGAL_OS_READ_ONLY_EFFECT_REQUIRED")
    if constraints["evidence_required"] != []:
        raise OperationContractError("LEGAL_OS_UNSUPPORTED_EVIDENCE_REQUIREMENT")
    if require_map(envelope["effects"], "effects")["declared"] != []:
        raise OperationContractError("LEGAL_OS_READ_ONLY_EFFECT_REQUIRED")

    payload = require_map(request["input"], "request.input")
    exact_keys(payload, _INPUT_FIELDS, "legal_os.assess.input")
    tenant = require_id(payload["tenant_id"], "tenant_id")
    work_case = require_id(payload["work_case_id"], "work_case_id")
    candidate = require_sha(payload["candidate_sha"], "candidate_sha")
    type_id = require_id(payload["type_id"], "type_id")
    if type_id not in SUPPORTED_CANDIDATE_TYPES:
        raise OperationContractError("LEGAL_OS_TYPE_UNSUPPORTED")
    context = require_map(envelope["context"], "context")
    if context["case_id"] != work_case:
        raise OperationContractError("LEGAL_OS_CASE_SCOPE_MISMATCH")
    preconditions = require_map(envelope["preconditions"], "preconditions")
    authority_ref = str(preconditions["authority_ref"])

    def handler(_: Mapping[str, object], _context: object) -> HandlerOutcome:
        if authority_resolver is None or work_reader is None:
            return HandlerOutcome(
                OperationStatus.BLOCKED,
                "trusted WORK read capability or adapter unavailable",
            )
        capability = authority_resolver(authority_ref, tenant, work_case, privacy_scope)
        if capability is None:
            return HandlerOutcome(
                OperationStatus.BLOCKED,
                "scoped WORK read capability was not admitted",
            )
        native = require_map(
            work_reader(capability, tenant, work_case, candidate, type_id),
            "native_work_snapshot",
        )
        exact_keys(native, _SNAPSHOT_FIELDS, "native_work_snapshot")
        if (
            native["tenant_id"] != tenant
            or native["case_id"] != work_case
            or native["candidate_sha"] != candidate
            or native["type_id"] != type_id
        ):
            return HandlerOutcome(
                OperationStatus.BLOCKED,
                "native WORK scope or exact revision mismatch",
            )
        ref = require_id(native["work_state_ref"], "native_work_state_ref")
        digest = native["work_digest"]
        if not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest):
            raise OperationContractError("LEGAL_OS_NATIVE_DIGEST_INVALID")
        return HandlerOutcome(
            OperationStatus.SUCCESS,
            "scoped WORK state reference read; legal admission and release NOT inferred",
            evidence=({"kind": "work_snapshot", "ref": ref, "digest": digest},),
        )

    return (runtime or OperationRuntime()).execute(
        envelope,
        current_head=current_head,
        privacy_scope=privacy_scope,
        handler=handler,
    )
