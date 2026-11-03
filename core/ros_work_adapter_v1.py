"""ROS -> WORK adapter boundary v1 (fail-closed).

Maps LUKART Operation Contract v1 envelopes to native WORK operator requests.
Does NOT import lukart_work at runtime; dispatches over a neutral HTTP boundary
(local operator_host) and returns a neutral ROS result envelope.

Gates:
- Only read-only GetCaseHead assessment is enabled in this pilot.
- Native execute and final-package reads remain blocked until WORK-native,
  independently verified scoped capabilities are admitted; a local authority
  map cannot activate either operation.
- Final-package reads additionally require HUMAN actor and PB03 acceptance.

Invariants:
- ROS authority_ref is NEVER forwarded as WORK authorization truth.
- The authority map resolves a native WORK bearer token; it does not grant
  WORK capabilities or independently authorize an operation.
- Trusted WORK URLs are exact loopback origins; ambient proxies and HTTP redirects are disabled.
- ROS expected_head is an orchestration precondition only.
- WORK expected_case_sequence/CAS remains authoritative.
- CASE_HEAD responses must match the exact resolved tenant and case.
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
from urllib.parse import urlsplit
from uuid import UUID

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
MAX_WORK_TIMEOUT_MS = 300_000

# Pinned to WORK@7a924f37696cdf74666c08f924f1941edb4fc030:
# schemas/CaseHeadResult.schema.json (blob aa97dd4ef4865948fe7c393c224b0bacdca421a2).
_CASE_HEAD_REF_KINDS = frozenset(
    {
        "Case",
        "Party",
        "Institution",
        "Proceeding",
        "Filing",
        "Fact",
        "Evidence",
        "Issue",
        "LegalSource",
        "LegalRule",
        "Claim",
        "Defence",
        "Argument",
        "CounterArgument",
        "Request",
        "Deadline",
        "Risk",
        "Citation",
        "DocumentPlan",
        "Section",
        "Draft",
        "ValidationFinding",
        "Decision",
    }
)


def _is_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value.lower()
    except ValueError:
        return False


def _is_case_head_ref(value: object) -> bool:
    return (
        type(value) is dict
        and set(value) == {"kind", "id", "revision"}
        and value.get("kind") in _CASE_HEAD_REF_KINDS
        and _is_uuid(value.get("id"))
        and type(value.get("revision")) is int
        and value["revision"] >= 1
    )


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Never forward a bearer token through an HTTP redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


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
    timeout_ms: int
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
        try:
            parsed = urlsplit(self.trusted_host_url)
            port = parsed.port
        except (TypeError, ValueError) as exc:
            raise RosWorkAdapterError("trusted host URL is invalid") from exc
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or port is None
            or not 1 <= port <= 65535
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.netloc != f"127.0.0.1:{port}"
        ):
            raise RosWorkAdapterError("trusted host must be an exact local 127.0.0.1 origin")


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
    *,
    expected_operation_id: str,
    expected_tenant_id: str,
    expected_case_id: str,
) -> RosWorkResult:
    """Map only the response contract admitted for this exact operation and scope."""
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
        type(work_response) is dict
        and set(work_response)
        == {"result_type", "tenant_id", "case_id", "case_sequence", "heads"}
        and work_response.get("result_type") == "CASE_HEAD"
        and expected_operation_id == "ros.work.generator.assess.v1"
        and _is_uuid(expected_tenant_id)
        and _is_uuid(expected_case_id)
        and work_response.get("tenant_id") == expected_tenant_id
        and work_response.get("case_id") == expected_case_id
        and type(work_response.get("case_sequence")) is int
        and work_response["case_sequence"] >= 1
        and type(work_response.get("heads")) is list
        and all(_is_case_head_ref(head) for head in work_response["heads"])
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

        # Only read-only case-head assessment is enabled in this pilot. A local
        # authority map cannot activate native execute or final-package reads.
        if operation_id != "ros.work.generator.assess.v1":
            raise RosWorkAdapterError(
                "operation disabled until native WORK capability is independently admitted"
            )

        authority_ref = str(preconditions["authority_ref"])
        resolution = self._authority_map.get(authority_ref)
        if resolution is None:
            raise RosWorkAdapterError(f"authority_ref not admitted: {authority_ref}")

        if operation_id not in resolution.admitted_operations:
            raise RosWorkAdapterError(
                f"authority_ref not admitted for operation: {authority_ref} -> {operation_id}"
            )

        # Scope must map exactly and satisfy the native WORK UUID contract.
        ros_case_id = str(context["case_id"])
        if not _is_uuid(resolution.tenant_id) or not _is_uuid(resolution.case_id):
            raise RosWorkAdapterError("authority resolution has invalid native WORK UUID scope")
        if resolution.case_id != ros_case_id:
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

        timeout_ms = constraints.get("timeout_ms")
        if type(timeout_ms) is not int or not 1 <= timeout_ms <= MAX_WORK_TIMEOUT_MS:
            raise RosWorkAdapterError("constraints.timeout_ms must be 1..300000")

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
        if operation_id == "ros.work.generator.assess.v1":
            # Native CoreQuery is not a command envelope: scope is top-level,
            # and command meta/rationale are forbidden by the WORK schema.
            if request["input"]:
                raise RosWorkAdapterError("assess.v1 accepts no caller WORK payload")
            payload = {
                "contract": work_contract,
                "operation": work_operation,
                "tenant_id": resolution.tenant_id,
                "case_id": resolution.case_id,
            }


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
            timeout_ms=timeout_ms,
            payload=payload,
            admitted=True,
        )

    def _validate_dispatch_request(self, mapped: RosWorkRequest) -> None:
        """Revalidate public request objects at the native HTTP boundary."""
        if not isinstance(mapped, RosWorkRequest):
            raise RosWorkAdapterError("mapped request has an invalid type")
        if mapped.admitted is not True:
            raise RosWorkAdapterError("mapped request is not admitted")
        if (
            mapped.operation_id != "ros.work.generator.assess.v1"
            or mapped.work_route != "query_core"
            or mapped.work_contract != "urn:lukart:work:CoreQuery:1.0.0"
            or mapped.work_operation != "GetCaseHead"
        ):
            raise RosWorkAdapterError(
                "operation disabled until native WORK capability is independently admitted"
            )
        if (
            not all(
                isinstance(value, str) and value
                for value in (
                    mapped.tenant_id,
                    mapped.case_id,
                    mapped.token,
                    mapped.idempotency_key,
                    mapped.request_digest,
                )
            )
            or not _is_uuid(mapped.tenant_id)
            or not _is_uuid(mapped.case_id)
            or type(mapped.expected_case_sequence) is not int
            or mapped.expected_case_sequence < 0
            or type(mapped.timeout_ms) is not int
            or not 1 <= mapped.timeout_ms <= MAX_WORK_TIMEOUT_MS
        ):
            raise RosWorkAdapterError("mapped request is incomplete")
        expected_payload = {
            "contract": "urn:lukart:work:CoreQuery:1.0.0",
            "operation": "GetCaseHead",
            "tenant_id": mapped.tenant_id,
            "case_id": mapped.case_id,
        }
        if type(mapped.payload) is not dict or mapped.payload != expected_payload:
            raise RosWorkAdapterError(
                "mapped request does not match the admitted native CoreQuery"
            )

        self._load_authorities()
        if not any(
            resolution.token == mapped.token
            and resolution.tenant_id == mapped.tenant_id
            and resolution.case_id == mapped.case_id
            and "ros.work.generator.assess.v1" in resolution.admitted_operations
            for resolution in self._authority_map.values()
        ):
            raise RosWorkAdapterError(
                "mapped request is not backed by an admitted authority resolution"
            )

    def dispatch(self, mapped: RosWorkRequest) -> RosWorkResult:
        """Send only the admitted native CoreQuery request to the trusted WORK host."""
        self._validate_dispatch_request(mapped)
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
            timeout_s = mapped.timeout_ms / 1000.0
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}),
                _NoRedirectHandler(),
            )
            with opener.open(req, timeout=timeout_s) as response:
                raw = response.read()
                work_response = json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RosWorkAdapterError(f"WORK HTTP error: {exc.code} {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RosWorkAdapterError(f"WORK unreachable: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise RosWorkAdapterError(f"WORK response not JSON: {exc}") from exc

        return _map_work_response(
            work_response,
            mapped.request_digest,
            expected_operation_id=mapped.operation_id,
            expected_tenant_id=mapped.tenant_id,
            expected_case_id=mapped.case_id,
        )

    def execute(self, envelope: Mapping[str, object]) -> RosWorkResult:
        """Validate, map, dispatch, and derive a neutral ROS result."""
        self.validate_envelope(envelope)
        mapped = self.map_request(envelope)
        work_result = self.dispatch(mapped)
        return work_result
