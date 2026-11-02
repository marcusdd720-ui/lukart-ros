"""ROS -> WORK adapter boundary v1 (fail-closed).

Maps LUKART Operation Contract v1 envelopes to native WORK operator requests.
Does NOT import lukart_work at runtime; dispatches over a neutral HTTP boundary
(local operator_host) and returns a neutral ROS result envelope.

Gates:
- ros.work.generator.execute.v1 is blocked by default unless the trusted host
  explicitly admits the operation through its own HUMAN/authorization flow.
- ros.work.generator.read-package.v1 remains blocked until HG-09 and PB03
  checkpoint review are satisfied.

Invariants:
- ROS authority_ref is NEVER forwarded as WORK authorization truth.
- ROS expected_head is an orchestration precondition only.
- WORK expected_case_sequence/CAS remains authoritative.
- Different request digest with the same idempotency key blocks.
- Unknown operation, scope mismatch, or missing authority resolution blocks.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from core.night_shift.contracts import NightShiftContractError
from core.operations.contract_v1 import (
    OperationContractError,
    content_digest,
    validate_operation_envelope,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_OPERATIONS = frozenset(
    {
        "ros.work.generator.assess.v1",
        "ros.work.generator.execute.v1",
        "ros.work.generator.read-package.v1",
    }
)

# Mapping from ROS operation to WORK route + contract + default WORK operation.
# Only assess is implemented as a read-only query; execute/read-package remain
# blocked at the adapter boundary until their gates close.
OPERATION_MAP = {
    "ros.work.generator.assess.v1": {
        "work_route": "query_core",
        "work_contract": "urn:lukart:work:CoreQuery:1.0.0",
        "work_operation": "GetCaseHead",
    },
    "ros.work.generator.execute.v1": {
        "work_route": "execute_core",
        "work_contract": "urn:lukart:work:CoreRequest:1.0.0",
        "work_operation": None,  # caller must supply via input.work_operation
    },
    "ros.work.generator.read-package.v1": {
        "work_route": "query_finalization",
        "work_contract": "urn:lukart:work:FinalizationQuery:1.0.0",
        "work_operation": "ReadFinalArtifact",
    },
}

MAX_WORK_REQUEST_BYTES = 1024 * 1024


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class AuthorityResolution:
    """Trusted-host mapping from ROS authority_ref to a WORK bearer token."""
    authority_ref: str
    token: str
    admitted_operations: tuple[str, ...]
    tenant_id: str
    case_id: str


@dataclass(frozen=True, slots=True)
class RosWorkRequest:
    """Validated, mapped ROS envelope ready for WORK dispatch."""
    operation_id: str
    work_route: str
    work_contract: str
    work_operation: str
    tenant_id: str
    case_id: str
    token: str
    idempotency_key: str
    request_digest: str
    expected_case_sequence: int
    payload: Mapping[str, Any]
    admitted: bool


@dataclass(frozen=True, slots=True)
class RosWorkResult:
    """Neutral ROS result envelope derived from native WORK result."""
    status: str
    summary: str
    artifacts: tuple[str, ...] = ()
    evidence: tuple[Mapping[str, object], ...] = ()
    errors: tuple[Mapping[str, object], ...] = ()
    work_command_id: str | None = None
    work_event_ids: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class RosWorkAdapterError(NightShiftContractError):
    """Fail-closed adapter boundary violation."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class AdapterConfig:
    """Trusted host boundary configuration.

    trusted_host_url must point to a local operator_host instance bound to
    127.0.0.1. The adapter never connects to a remote or untrusted host.
    """
    trusted_host_url: str = "http://127.0.0.1:8765"
    authority_map_path: Path | None = field(
        default=None,
        metadata={"description": "JSON file mapping authority_ref -> AuthorityResolution"},
    )

    def __post_init__(self) -> None:
        if not self.trusted_host_url.startswith("http://127.0.0.1"):
            raise RosWorkAdapterError("trusted host must be local 127.0.0.1")


# ---------------------------------------------------------------------------
# Authority resolution
# ---------------------------------------------------------------------------

def _load_authority_map(config: AdapterConfig) -> dict[str, AuthorityResolution]:
    if config.authority_map_path is None:
        return {}
    raw = json.loads(Path(config.authority_map_path).read_text(encoding="utf-8"))
    items: dict[str, AuthorityResolution] = {}
    for authority_ref, entry in raw.items():
        admitted = tuple(entry.get("admitted_operations", []))
        items[authority_ref] = AuthorityResolution(
            authority_ref=str(authority_ref),
            token=str(entry["token"]),
            admitted_operations=admitted,
            tenant_id=str(entry["tenant_id"]),
            case_id=str(entry["case_id"]),
        )
    return items


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------

def _digest_work_result(result: Mapping[str, Any]) -> str:
    return content_digest(result)


def _map_work_response(
    work_response: Mapping[str, Any],
    request_digest: str,
) -> RosWorkResult:
    """Derive a neutral ROS result envelope from a native WORK response."""
    if isinstance(work_response, dict) and work_response.get("state") == "APPLIED":
        status = "success"
        summary = "native WORK command applied"
        refs = work_response.get("refs", ())
        artifacts = tuple(str(ref) for ref in refs) if refs else ()
        event_ids = tuple(str(eid) for eid in work_response.get("event_ids", ()))
        return RosWorkResult(
            status=status,
            summary=summary,
            artifacts=artifacts,
            evidence=(),
            errors=(),
            work_command_id=str(work_response.get("command_id", "")),
            work_event_ids=event_ids,
        )
    if isinstance(work_response, dict) and work_response.get("code"):
        code = str(work_response["code"])
        status = "blocked" if code in ("GATE_DENIED", "FORBIDDEN", "SCHEMA_INVALID") else "failure"
        summary = f"WORK returned {code}"
        return RosWorkResult(
            status=status,
            summary=summary,
            errors=(
                {
                    "code": code,
                    "category": "work",
                    "retryable": False,
                    "message": summary,
                },
            ),
        )
    # Only the native GetCaseHead query is admitted for ROS assess in v1.
    # An arbitrary result_type (or a partial CASE_HEAD result) must not
    # become a success verdict across this security-sensitive boundary.
    if (
        isinstance(work_response, dict)
        and work_response.get("result_type") == "CASE_HEAD"
        and isinstance(work_response.get("tenant_id"), str)
        and bool(work_response["tenant_id"])
        and isinstance(work_response.get("case_id"), str)
        and bool(work_response["case_id"])
        and type(work_response.get("case_sequence")) is int
        and work_response["case_sequence"] >= 0
    ):
        result_type = "CASE_HEAD"
        return RosWorkResult(
            status="success",
            summary=f"native WORK query {result_type}",
            artifacts=(),
            evidence=(),
            errors=(),
            work_command_id=None,
            work_event_ids=(),
        )
    return RosWorkResult(
        status="failure",
        summary="unexpected WORK response shape",
        errors=(
            {
                "code": "UNKNOWN",
                "category": "adapter",
                "retryable": False,
                "message": "unexpected WORK response shape",
            },
        ),
    )


# ---------------------------------------------------------------------------
# Core adapter
# ---------------------------------------------------------------------------

class RosWorkAdapterV1:
    """Fail-closed ROS -> WORK adapter boundary."""

    def __init__(self, config: AdapterConfig) -> None:
        self.config = config
        self._authority_map: dict[str, AuthorityResolution] = {}

    def _load_authorities(self) -> None:
        if not self._authority_map:
            self._authority_map = _load_authority_map(self.config)

    def validate_envelope(self, envelope: Mapping[str, object]) -> None:
        """Validate ROS operation envelope against the canonical contract."""
        try:
            validate_operation_envelope(envelope, response=False)
        except OperationContractError as exc:
            raise RosWorkAdapterError(f"invalid ROS envelope: {exc}") from exc

    def map_request(self, envelope: Mapping[str, object]) -> RosWorkRequest:
        """Translate a validated ROS envelope into a WORK request."""
        self._load_authorities()

        request = cast(Mapping[str, Any], envelope["request"])
        context = cast(Mapping[str, Any], envelope["context"])
        preconditions = cast(Mapping[str, Any], envelope["preconditions"])
        idempotency = cast(Mapping[str, Any], envelope["idempotency"])
        constraints = cast(Mapping[str, Any], envelope["constraints"])

        operation_id = str(request["operation_id"])
        operation = str(request["operation"])

        if operation_id not in ALLOWED_OPERATIONS:
            raise RosWorkAdapterError(f"operation not allowed: {operation_id}")
        if operation != operation_id:
            raise RosWorkAdapterError("request.operation must equal request.operation_id")

        mapping = cast(dict[str, object], OPERATION_MAP[operation_id])
        work_route = str(mapping["work_route"])
        work_contract = str(mapping["work_contract"])
        work_operation = (
            str(mapping["work_operation"])
            if mapping.get("work_operation")
            else str(request["input"].get("work_operation", ""))
        )

        if not work_operation:
            raise RosWorkAdapterError("execute.v1 requires input.work_operation")

        authority_ref = str(preconditions["authority_ref"])
        resolution = self._authority_map.get(authority_ref)
        if resolution is None:
            raise RosWorkAdapterError(f"authority_ref not admitted: {authority_ref}")

        if operation_id not in resolution.admitted_operations:
            raise RosWorkAdapterError(
                f"authority_ref not admitted for operation: {authority_ref} -> {operation_id}"
            )

        # Scope must map exactly.
        ros_case_id = str(context["case_id"])
        if resolution.case_id != ros_case_id or not resolution.tenant_id:
            raise RosWorkAdapterError("tenant/case scope mismatch")

        # Idempotency + digest binding.
        idempotency_key = str(idempotency["key"])
        request_digest = content_digest(
            {
                "operation_id": operation_id,
                "operation": operation,
                "context": dict(context),
                "preconditions": dict(preconditions),
                "input": dict(request["input"]),
                "constraints": dict(constraints),
                "idempotency": dict(idempotency),
            }
        )

        # WORK expected_case_sequence is authoritative for domain writes.
        # For read-only assess we default to 0; for mutations the caller must
        # supply the exact sequence via input.expected_case_sequence.
        expected_case_sequence = int(constraints.get("expected_case_sequence", 0))

        payload = dict(request["input"])
        payload.setdefault("contract", work_contract)
        payload.setdefault("operation", work_operation)
        payload.setdefault("meta", {
            "command_id": idempotency_key,
            "tenant_id": resolution.tenant_id,
            "case_id": resolution.case_id,
            "idempotency_key": idempotency_key,
            "expected_case_sequence": expected_case_sequence,
            "correlation_id": request_digest,
        })
        payload.setdefault("rationale", f"ROS adapter dispatch: {operation_id}")

        return RosWorkRequest(
            operation_id=operation_id,
            work_route=work_route,
            work_contract=work_contract,
            work_operation=work_operation,
            tenant_id=resolution.tenant_id,
            case_id=resolution.case_id,
            token=resolution.token,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            expected_case_sequence=expected_case_sequence,
            payload=payload,
            admitted=True,
        )

    def dispatch(self, mapped: RosWorkRequest) -> RosWorkResult:
        """Send the mapped request to the trusted WORK host."""
        url = f"{self.config.trusted_host_url}/api/{mapped.work_route}"
        body = json.dumps(mapped.payload, allow_nan=False).encode("utf-8")
        if len(body) > MAX_WORK_REQUEST_BYTES:
            raise RosWorkAdapterError("WORK request exceeds size limit")

        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {mapped.token}",
            },
            method="POST",
        )
        try:
            timeout_s = int(mapped.payload.get("timeout_ms", 30000)) / 1000
            with urllib.request.urlopen(req, timeout=timeout_s) as response:
                raw = response.read()
                work_response = json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RosWorkAdapterError(f"WORK HTTP error: {exc.code} {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RosWorkAdapterError(f"WORK unreachable: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise RosWorkAdapterError(f"WORK response not JSON: {exc}") from exc

        return _map_work_response(work_response, mapped.request_digest)

    def execute(self, envelope: Mapping[str, object]) -> RosWorkResult:
        """Validate, map, dispatch, and derive a neutral ROS result."""
        self.validate_envelope(envelope)
        mapped = self.map_request(envelope)
        work_result = self.dispatch(mapped)
        return work_result
