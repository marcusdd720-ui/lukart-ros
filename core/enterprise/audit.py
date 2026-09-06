"""H9 tamper-evident operational audit bundle over canonical E6/E7 authorities."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core.p3.contracts import content_digest, require_hex_digest

from .contracts import EnterpriseContractError
from .durability import DurableRecord
from .observability import TelemetryEvent, redact_value

_AUDIT_SCHEMA = "lukart.operational-audit-bundle.v1"
_AUDIT_GENESIS = "0" * 64
_CORRELATION_FIELDS = (
    "run_id",
    "case_id",
    "provider_id",
    "provider_version",
    "workflow_id",
    "workflow_ref",
    "candidate_sha",
    "config_digest",
)


@dataclass(frozen=True, slots=True)
class AuditCorrelation:
    run_id: str
    case_id: str
    provider_id: str
    provider_version: str
    workflow_id: str
    workflow_ref: str
    candidate_sha: str
    config_digest: str

    def __post_init__(self) -> None:
        text_fields = (
            self.run_id,
            self.case_id,
            self.provider_id,
            self.provider_version,
            self.workflow_id,
            self.workflow_ref,
        )
        if any(not value.strip() for value in text_fields):
            raise EnterpriseContractError("audit correlation fields are required")
        require_hex_digest(self.candidate_sha, field_name="audit_candidate_sha", lengths=(40,))
        require_hex_digest(self.config_digest, field_name="audit_config_digest")

    def canonical_dict(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "provider_id": self.provider_id,
            "provider_version": self.provider_version,
            "workflow_id": self.workflow_id,
            "workflow_ref": self.workflow_ref,
            "candidate_sha": self.candidate_sha,
            "config_digest": self.config_digest,
        }

    @property
    def correlation_id(self) -> str:
        return content_digest(self.canonical_dict())


def _bounded_redacted_details(
    details: Mapping[str, object],
    *,
    max_attributes: int,
    max_value_length: int,
) -> dict[str, str]:
    if max_attributes < 1 or max_value_length < 16:
        raise EnterpriseContractError("invalid audit redaction bounds")
    if len(details) > max_attributes:
        raise EnterpriseContractError("audit detail cardinality limit exceeded")
    return {
        str(key): redact_value(str(key), value, max_length=max_value_length)
        for key, value in sorted(details.items(), key=lambda item: str(item[0]))
    }


def build_audit_payload(
    correlation: AuditCorrelation,
    details: Mapping[str, object],
    *,
    max_attributes: int = 32,
    max_value_length: int = 256,
) -> dict[str, object]:
    """Build least-data durable payload with PII/secret redaction before persistence."""

    return {
        "audit_correlation": correlation.canonical_dict(),
        "details": _bounded_redacted_details(
            details,
            max_attributes=max_attributes,
            max_value_length=max_value_length,
        ),
    }


def build_telemetry_attributes(
    correlation: AuditCorrelation,
    details: Mapping[str, object],
    *,
    max_attributes: int = 24,
    max_value_length: int = 256,
) -> dict[str, object]:
    """Build bounded telemetry attributes correlated to the same operational identity."""

    redacted = _bounded_redacted_details(
        details,
        max_attributes=max_attributes,
        max_value_length=max_value_length,
    )
    attributes: dict[str, object] = {}
    attributes.update(correlation.canonical_dict())
    attributes.update({f"detail.{key}": value for key, value in redacted.items()})
    return attributes


def _require_correlation_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise EnterpriseContractError("audit correlation payload is missing or invalid")
    return value


def _verify_record(
    record: DurableRecord,
    *,
    expected_sequence: int,
    previous_digest: str,
    correlation: AuditCorrelation,
) -> None:
    if record.sequence != expected_sequence:
        raise EnterpriseContractError("audit provenance sequence gap")
    if record.previous_digest != previous_digest:
        raise EnterpriseContractError("audit provenance chain mismatch")
    if record.payload_digest != content_digest(record.payload):
        raise EnterpriseContractError("audit provenance payload digest mismatch")
    if record.record_digest != content_digest(record.canonical_body()):
        raise EnterpriseContractError("audit provenance record digest mismatch")
    payload_correlation = _require_correlation_mapping(record.payload.get("audit_correlation"))
    if dict(payload_correlation) != correlation.canonical_dict():
        raise EnterpriseContractError("audit provenance correlation mismatch")


def _record_manifest(record: DurableRecord) -> dict[str, object]:
    return {
        "sequence": record.sequence,
        "stream_id": record.stream_id,
        "event_type": record.event_type,
        "payload": dict(record.payload),
        "payload_digest": record.payload_digest,
        "previous_digest": record.previous_digest,
        "record_digest": record.record_digest,
    }


def _telemetry_manifest(
    events: Sequence[TelemetryEvent],
    correlation: AuditCorrelation,
) -> tuple[list[dict[str, object]], str]:
    manifest: list[dict[str, object]] = []
    previous = _AUDIT_GENESIS
    expected_trace_id = content_digest({"correlation_id": correlation.correlation_id})[:32]
    expected_attributes = correlation.canonical_dict()
    for sequence, event in enumerate(events):
        if event.trace_id != expected_trace_id:
            raise EnterpriseContractError("audit telemetry trace correlation mismatch")
        for key, expected in expected_attributes.items():
            if event.attributes.get(key) != expected:
                raise EnterpriseContractError(f"audit telemetry correlation mismatch for {key}")
        event_digest = event.digest()
        chain_body = {
            "sequence": sequence,
            "event_digest": event_digest,
            "previous_digest": previous,
        }
        chain_digest = content_digest(chain_body)
        manifest.append(
            {
                "sequence": sequence,
                "name": event.name,
                "trace_id": event.trace_id,
                "attributes": dict(sorted(event.attributes.items())),
                "event_digest": event_digest,
                "previous_digest": previous,
                "chain_digest": chain_digest,
            }
        )
        previous = chain_digest
    return manifest, previous


def build_operational_audit_bundle(
    correlation: AuditCorrelation,
    records: Sequence[DurableRecord],
    telemetry_events: Sequence[TelemetryEvent],
    *,
    max_provenance_records: int = 10_000,
    max_telemetry_events: int = 10_000,
) -> dict[str, object]:
    """Build a bounded versioned bundle; integrity is claimed, authenticity is not."""

    if max_provenance_records < 1 or max_telemetry_events < 1:
        raise EnterpriseContractError("audit bundle bounds must be positive")
    if not records:
        raise EnterpriseContractError("audit bundle requires provenance records")
    if not telemetry_events:
        raise EnterpriseContractError("audit bundle requires telemetry events")
    if len(records) > max_provenance_records:
        raise EnterpriseContractError("audit provenance record budget exceeded")
    if len(telemetry_events) > max_telemetry_events:
        raise EnterpriseContractError("audit telemetry event budget exceeded")

    previous = _AUDIT_GENESIS
    provenance_manifest: list[dict[str, object]] = []
    for expected_sequence, record in enumerate(records):
        _verify_record(
            record,
            expected_sequence=expected_sequence,
            previous_digest=previous,
            correlation=correlation,
        )
        provenance_manifest.append(_record_manifest(record))
        previous = record.record_digest

    telemetry_manifest, telemetry_head = _telemetry_manifest(telemetry_events, correlation)
    body: dict[str, object] = {
        "schema": _AUDIT_SCHEMA,
        "correlation": correlation.canonical_dict(),
        "correlation_id": correlation.correlation_id,
        "provenance_record_count": len(provenance_manifest),
        "provenance_head_digest": previous,
        "provenance_state_digest": content_digest(provenance_manifest),
        "provenance_records": provenance_manifest,
        "telemetry_event_count": len(telemetry_manifest),
        "telemetry_chain_head": telemetry_head,
        "telemetry_state_digest": content_digest(telemetry_manifest),
        "telemetry_events": telemetry_manifest,
        "integrity_model": "digest-bound-hash-chains",
        "cryptographic_authenticity_claimed": False,
    }
    body["bundle_digest"] = content_digest(body)
    verify_operational_audit_bundle(body)
    return body


def _parse_correlation(value: object) -> AuditCorrelation:
    mapping = _require_correlation_mapping(value)
    missing = [field for field in _CORRELATION_FIELDS if not isinstance(mapping.get(field), str)]
    if missing:
        raise EnterpriseContractError(f"audit correlation fields missing: {missing}")
    return AuditCorrelation(
        run_id=str(mapping["run_id"]),
        case_id=str(mapping["case_id"]),
        provider_id=str(mapping["provider_id"]),
        provider_version=str(mapping["provider_version"]),
        workflow_id=str(mapping["workflow_id"]),
        workflow_ref=str(mapping["workflow_ref"]),
        candidate_sha=str(mapping["candidate_sha"]),
        config_digest=str(mapping["config_digest"]),
    )


def verify_operational_audit_bundle(
    bundle: Mapping[str, object],
    *,
    expected_bundle_digest: str | None = None,
) -> str:
    """Fail closed on schema drift, gaps, correlation mismatch or digest tampering."""

    if bundle.get("schema") != _AUDIT_SCHEMA:
        raise EnterpriseContractError("unsupported operational audit bundle schema")
    correlation = _parse_correlation(bundle.get("correlation"))
    if bundle.get("correlation_id") != correlation.correlation_id:
        raise EnterpriseContractError("audit correlation digest mismatch")

    stored_digest = bundle.get("bundle_digest")
    if not isinstance(stored_digest, str):
        raise EnterpriseContractError("audit bundle digest is missing")
    require_hex_digest(stored_digest, field_name="audit_bundle_digest")
    unsigned = {key: value for key, value in bundle.items() if key != "bundle_digest"}
    if content_digest(unsigned) != stored_digest:
        raise EnterpriseContractError("audit bundle digest mismatch")
    if expected_bundle_digest is not None and stored_digest != expected_bundle_digest:
        raise EnterpriseContractError("audit bundle does not match expected digest")

    raw_records = bundle.get("provenance_records")
    if not isinstance(raw_records, list):
        raise EnterpriseContractError("audit provenance manifest is invalid")
    if bundle.get("provenance_record_count") != len(raw_records):
        raise EnterpriseContractError("audit provenance count gap")
    previous = _AUDIT_GENESIS
    for expected_sequence, raw_record in enumerate(raw_records):
        if not isinstance(raw_record, Mapping):
            raise EnterpriseContractError("audit provenance entry is invalid")
        if raw_record.get("sequence") != expected_sequence:
            raise EnterpriseContractError("audit provenance sequence gap")
        if raw_record.get("previous_digest") != previous:
            raise EnterpriseContractError("audit provenance chain mismatch")
        payload = raw_record.get("payload")
        if not isinstance(payload, Mapping):
            raise EnterpriseContractError("audit provenance payload is invalid")
        payload_digest = content_digest(dict(payload))
        if raw_record.get("payload_digest") != payload_digest:
            raise EnterpriseContractError("audit provenance payload digest mismatch")
        canonical_body = {
            "sequence": raw_record.get("sequence"),
            "stream_id": raw_record.get("stream_id"),
            "event_type": raw_record.get("event_type"),
            "payload": dict(payload),
            "payload_digest": raw_record.get("payload_digest"),
            "previous_digest": raw_record.get("previous_digest"),
        }
        record_digest = content_digest(canonical_body)
        if raw_record.get("record_digest") != record_digest:
            raise EnterpriseContractError("audit provenance record digest mismatch")
        payload_correlation = _require_correlation_mapping(payload.get("audit_correlation"))
        if dict(payload_correlation) != correlation.canonical_dict():
            raise EnterpriseContractError("audit provenance correlation mismatch")
        previous = record_digest
    if bundle.get("provenance_head_digest") != previous:
        raise EnterpriseContractError("audit provenance head mismatch")
    if bundle.get("provenance_state_digest") != content_digest(raw_records):
        raise EnterpriseContractError("audit provenance state digest mismatch")

    raw_events = bundle.get("telemetry_events")
    if not isinstance(raw_events, list):
        raise EnterpriseContractError("audit telemetry manifest is invalid")
    if bundle.get("telemetry_event_count") != len(raw_events):
        raise EnterpriseContractError("audit telemetry count gap")
    expected_trace = content_digest({"correlation_id": correlation.correlation_id})[:32]
    previous = _AUDIT_GENESIS
    expected_attributes = correlation.canonical_dict()
    for expected_sequence, raw_event in enumerate(raw_events):
        if not isinstance(raw_event, Mapping):
            raise EnterpriseContractError("audit telemetry entry is invalid")
        if raw_event.get("sequence") != expected_sequence:
            raise EnterpriseContractError("audit telemetry sequence gap")
        if raw_event.get("previous_digest") != previous:
            raise EnterpriseContractError("audit telemetry chain mismatch")
        attributes = raw_event.get("attributes")
        if not isinstance(attributes, Mapping):
            raise EnterpriseContractError("audit telemetry attributes are invalid")
        for key, expected in expected_attributes.items():
            if attributes.get(key) != expected:
                raise EnterpriseContractError(f"audit telemetry correlation mismatch for {key}")
        if raw_event.get("trace_id") != expected_trace:
            raise EnterpriseContractError("audit telemetry trace correlation mismatch")
        event_digest = content_digest(
            {
                "name": raw_event.get("name"),
                "trace_id": raw_event.get("trace_id"),
                "attributes": dict(sorted((str(k), str(v)) for k, v in attributes.items())),
            }
        )
        if raw_event.get("event_digest") != event_digest:
            raise EnterpriseContractError("audit telemetry event digest mismatch")
        chain_digest = content_digest(
            {
                "sequence": expected_sequence,
                "event_digest": event_digest,
                "previous_digest": previous,
            }
        )
        if raw_event.get("chain_digest") != chain_digest:
            raise EnterpriseContractError("audit telemetry chain digest mismatch")
        previous = chain_digest
    if bundle.get("telemetry_chain_head") != previous:
        raise EnterpriseContractError("audit telemetry head mismatch")
    if bundle.get("telemetry_state_digest") != content_digest(raw_events):
        raise EnterpriseContractError("audit telemetry state digest mismatch")
    if bundle.get("cryptographic_authenticity_claimed") is not False:
        raise EnterpriseContractError("audit bundle must not overclaim cryptographic authenticity")
    return stored_digest
