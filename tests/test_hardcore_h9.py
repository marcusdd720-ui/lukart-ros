from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from core.enterprise.audit import (
    AuditCorrelation,
    build_audit_payload,
    build_operational_audit_bundle,
    build_telemetry_attributes,
    verify_operational_audit_bundle,
)
from core.enterprise.contracts import EnterpriseContractError
from core.enterprise.durability import SQLiteProvenanceStore
from core.enterprise.observability import RedactingTelemetrySink


def _correlation() -> AuditCorrelation:
    return AuditCorrelation(
        run_id="run-h9-001",
        case_id="CASE-H9-CONTROL",
        provider_id="provider-control",
        provider_version="1.0.0",
        workflow_id="enterprise-hardening",
        workflow_ref=".github/workflows/enterprise-hardening.yml@refs/heads/main",
        candidate_sha="a" * 40,
        config_digest="b" * 64,
    )


def _bundle(tmp_path: Path) -> dict[str, object]:
    correlation = _correlation()
    with SQLiteProvenanceStore(tmp_path / "audit.db") as store:
        records = store.append_batch(
            (
                (
                    "CASE-H9-CONTROL",
                    "CONTROL_START",
                    build_audit_payload(correlation, {"phase": "start"}),
                ),
                (
                    "CASE-H9-CONTROL",
                    "CONTROL_VALIDATE",
                    build_audit_payload(correlation, {"phase": "validate"}),
                ),
                (
                    "CASE-H9-CONTROL",
                    "CONTROL_COMPLETE",
                    build_audit_payload(correlation, {"phase": "complete"}),
                ),
            )
        )

    sink = RedactingTelemetrySink()
    for phase in ("start", "validate", "complete"):
        sink.emit(
            f"h9.{phase}",
            build_telemetry_attributes(correlation, {"phase": phase}),
            correlation_id=correlation.correlation_id,
        )
    return build_operational_audit_bundle(correlation, records, sink.events())


def test_h9_bundle_reconstructs_correlated_control_path(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    digest = verify_operational_audit_bundle(bundle)

    assert digest == bundle["bundle_digest"]
    assert bundle["schema"] == "lukart.operational-audit-bundle.v1"
    assert bundle["provenance_record_count"] == 3
    assert bundle["telemetry_event_count"] == 3
    assert bundle["cryptographic_authenticity_claimed"] is False


def test_h9_tampered_durable_payload_fails_closed(tmp_path: Path) -> None:
    bundle = copy.deepcopy(_bundle(tmp_path))
    records = bundle["provenance_records"]
    assert isinstance(records, list)
    first = records[0]
    assert isinstance(first, dict)
    payload = first["payload"]
    assert isinstance(payload, dict)
    details = payload["details"]
    assert isinstance(details, dict)
    details["phase"] = "tampered"

    with pytest.raises(EnterpriseContractError):
        verify_operational_audit_bundle(bundle)


def test_h9_missing_telemetry_event_fails_closed(tmp_path: Path) -> None:
    bundle = copy.deepcopy(_bundle(tmp_path))
    events = bundle["telemetry_events"]
    assert isinstance(events, list)
    events.pop(1)

    with pytest.raises(EnterpriseContractError):
        verify_operational_audit_bundle(bundle)


def test_h9_unknown_bundle_schema_fails_closed(tmp_path: Path) -> None:
    bundle = copy.deepcopy(_bundle(tmp_path))
    bundle["schema"] = "lukart.operational-audit-bundle.v999"

    with pytest.raises(EnterpriseContractError, match="unsupported"):
        verify_operational_audit_bundle(bundle)


def test_h9_pii_and_secret_values_are_redacted_before_persistence() -> None:
    correlation = _correlation()
    payload = build_audit_payload(
        correlation,
        {
            "operator_email": "operator@example.com",
            "api_token": "raw-secret-token",
            "case_note": "contact 12345678901 before export",
        },
    )
    serialized = json.dumps(payload, sort_keys=True)

    assert "operator@example.com" not in serialized
    assert "raw-secret-token" not in serialized
    assert "12345678901" not in serialized
    assert "[REDACTED]" in serialized
    assert "[REDACTED_NUMBER]" in serialized


def test_h9_cross_case_telemetry_correlation_is_rejected(tmp_path: Path) -> None:
    correlation = _correlation()
    with SQLiteProvenanceStore(tmp_path / "audit.db") as store:
        records = store.append_batch(
            (("CASE-H9-CONTROL", "CONTROL", build_audit_payload(correlation, {})),)
        )

    attributes = build_telemetry_attributes(correlation, {"phase": "control"})
    attributes["case_id"] = "CASE-OTHER"
    sink = RedactingTelemetrySink()
    sink.emit("h9.control", attributes, correlation_id=correlation.correlation_id)

    with pytest.raises(EnterpriseContractError, match="case_id"):
        build_operational_audit_bundle(correlation, records, sink.events())


def test_h9_expected_bundle_digest_is_external_integrity_anchor(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)

    with pytest.raises(EnterpriseContractError, match="expected digest"):
        verify_operational_audit_bundle(bundle, expected_bundle_digest="c" * 64)
