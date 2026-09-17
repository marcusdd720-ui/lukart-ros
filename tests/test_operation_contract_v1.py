"""Schema and request-boundary conformance for Operation Contract v1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.operations import (
    SCHEMA_ID,
    OperationContractError,
    OperationRuntime,
    validate_operation_envelope,
)
from tests.operation_v1_support import HEAD, PRIVACY_SCOPE, operation_request, success_handler


def test_invalid_schema_fails_closed() -> None:
    envelope = operation_request()
    envelope["request"]["schema_id"] = "lukart.operation-contract.invalid"
    with pytest.raises(OperationContractError, match="unsupported schema_id"):
        validate_operation_envelope(envelope, response=False)


def test_unsupported_version_fails_closed() -> None:
    envelope = operation_request()
    envelope["request"]["version"] = "2.0"
    with pytest.raises(OperationContractError, match="unsupported version"):
        validate_operation_envelope(envelope, response=False)


def test_missing_authority_is_rejected_before_execution() -> None:
    envelope = operation_request()
    del envelope["preconditions"]["authority_ref"]
    with pytest.raises(OperationContractError, match="preconditions keys invalid"):
        OperationRuntime().execute(
            envelope,
            current_head=HEAD,
            privacy_scope=PRIVACY_SCOPE,
            handler=success_handler,
        )


def test_raw_secret_fields_are_rejected() -> None:
    with pytest.raises(OperationContractError, match="forbidden raw-secret field"):
        operation_request(input_payload={"token": "synthetic-secret-value"})


def test_schema_id_is_canonical() -> None:
    assert SCHEMA_ID == "lukart.operation-contract.v1"


def test_machine_readable_schema_matches_runtime_contract() -> None:
    schema_path = Path(__file__).parents[1] / "schemas" / "lukart_operation_contract_v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["properties"]["request"]["properties"]["schema_id"]["const"] == SCHEMA_ID
    assert set(schema["required"]) == {
        "request",
        "context",
        "preconditions",
        "constraints",
        "idempotency",
        "effects",
        "output",
        "evidence",
        "errors",
        "privacy",
    }
    statuses = schema["properties"]["output"]["properties"]["status"]["enum"]
    assert statuses == [None, "success", "failure", "partial", "skipped", "blocked"]


def test_request_rejects_prefilled_result_fields() -> None:
    envelope = operation_request()
    envelope["effects"]["actual"] = ["commit"]
    with pytest.raises(OperationContractError, match="request result fields must be empty"):
        validate_operation_envelope(envelope, response=False)


def test_identifiers_reject_noncanonical_whitespace() -> None:
    with pytest.raises(OperationContractError, match="surrounding whitespace"):
        operation_request(operation_id=" op-h3-001 ")


def test_uppercase_sha_is_not_silently_canonicalized() -> None:
    with pytest.raises(OperationContractError, match="lowercase 40-character SHA"):
        operation_request(expected_head="A" * 40)


def test_non_finite_input_number_is_rejected() -> None:
    with pytest.raises(OperationContractError, match="non-finite number"):
        operation_request(input_payload={"value": float("nan")})


def test_common_secret_suffix_is_rejected() -> None:
    with pytest.raises(OperationContractError, match="forbidden raw-secret field"):
        operation_request(input_payload={"access_token": "synthetic-secret-value"})
