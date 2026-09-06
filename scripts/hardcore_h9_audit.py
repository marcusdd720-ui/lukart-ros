from __future__ import annotations

import argparse
import copy
import json
import subprocess
import tempfile
from pathlib import Path

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
from core.p3.contracts import content_digest, require_hex_digest

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "enterprise_v1.json"


def _git_head() -> str:
    completed = subprocess.run(
        ("git", "-C", str(ROOT), "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _require_policy(document: dict[str, object]) -> dict[str, object]:
    h9 = document.get("h9_tamper_evident_audit")
    if not isinstance(h9, dict):
        raise RuntimeError("H9 tamper-evident audit policy is missing")
    required: dict[str, object] = {
        "schema": "lukart.hardcore.h9-audit.v1",
        "bundle_schema": "lukart.operational-audit-bundle.v1",
        "provenance_hash_chain_required": True,
        "telemetry_hash_chain_required": True,
        "pii_redaction_before_bundle": True,
        "unknown_schema": "FAIL",
        "tamper_or_gap": "FAIL",
        "cryptographic_authenticity_claimed": False,
    }
    for key, expected in required.items():
        if h9.get(key) != expected:
            raise RuntimeError(f"H9 policy mismatch for {key}: {h9.get(key)!r} != {expected!r}")
    expected_fields = [
        "run_id",
        "case_id",
        "provider_id",
        "provider_version",
        "workflow_id",
        "workflow_ref",
        "candidate_sha",
        "config_digest",
    ]
    if h9.get("correlation_fields") != expected_fields:
        raise RuntimeError("H9 correlation field contract mismatch")
    for key in ("max_provenance_records", "max_telemetry_events"):
        value = h9.get(key)
        if not isinstance(value, int) or value < 1:
            raise RuntimeError(f"H9 {key} must be a positive integer")
    return h9


def _adversarial_controls(bundle: dict[str, object]) -> dict[str, bool]:
    tampered = copy.deepcopy(bundle)
    records = tampered["provenance_records"]
    if not isinstance(records, list) or not records:
        raise RuntimeError("H9 control bundle provenance manifest is invalid")
    first = records[0]
    if not isinstance(first, dict):
        raise RuntimeError("H9 control bundle provenance entry is invalid")
    payload = first.get("payload")
    if not isinstance(payload, dict):
        raise RuntimeError("H9 control bundle payload is invalid")
    details = payload.get("details")
    if not isinstance(details, dict):
        raise RuntimeError("H9 control bundle details are invalid")
    details["phase"] = "tampered"
    tamper_rejected = False
    try:
        verify_operational_audit_bundle(tampered)
    except EnterpriseContractError:
        tamper_rejected = True

    missing = copy.deepcopy(bundle)
    events = missing["telemetry_events"]
    if not isinstance(events, list) or len(events) < 2:
        raise RuntimeError("H9 control bundle telemetry manifest is invalid")
    events.pop(1)
    gap_rejected = False
    try:
        verify_operational_audit_bundle(missing)
    except EnterpriseContractError:
        gap_rejected = True

    incompatible = copy.deepcopy(bundle)
    incompatible["schema"] = "lukart.operational-audit-bundle.v999"
    schema_rejected = False
    try:
        verify_operational_audit_bundle(incompatible)
    except EnterpriseContractError:
        schema_rejected = True

    controls = {
        "tamper_rejected": tamper_rejected,
        "gap_rejected": gap_rejected,
        "unknown_schema_rejected": schema_rejected,
    }
    if not all(controls.values()):
        raise RuntimeError(f"H9 adversarial audit controls failed: {controls}")
    return controls


def build_h9_evidence(
    candidate_sha: str,
    *,
    run_id: str,
    case_id: str,
    provider_id: str,
    provider_version: str,
    workflow_id: str,
    workflow_ref: str,
) -> dict[str, object]:
    candidate = require_hex_digest(candidate_sha, field_name="candidate_sha", lengths=(40,))
    head = require_hex_digest(_git_head(), field_name="head_sha", lengths=(40,))
    if candidate != head:
        raise RuntimeError(f"exact-SHA mismatch: checked-out HEAD {head} != candidate {candidate}")

    document = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise RuntimeError("Enterprise policy document must be an object")
    h9 = _require_policy(document)
    config_digest = content_digest(document)
    correlation = AuditCorrelation(
        run_id=run_id,
        case_id=case_id,
        provider_id=provider_id,
        provider_version=provider_version,
        workflow_id=workflow_id,
        workflow_ref=workflow_ref,
        candidate_sha=candidate,
        config_digest=config_digest,
    )
    sample_email = "operator" + "@" + "example.invalid"
    sample_secret = "raw-secret-token"

    with tempfile.TemporaryDirectory(prefix="lukart-h9-") as temp_dir:
        db_path = Path(temp_dir) / "audit.db"
        with SQLiteProvenanceStore(db_path) as store:
            records = store.append_batch(
                (
                    (
                        case_id,
                        "CONTROL_START",
                        build_audit_payload(
                            correlation,
                            {
                                "phase": "start",
                                "operator_email": sample_email,
                                "api_token": sample_secret,
                            },
                        ),
                    ),
                    (
                        case_id,
                        "CONTROL_VALIDATE",
                        build_audit_payload(correlation, {"phase": "validate"}),
                    ),
                    (
                        case_id,
                        "CONTROL_COMPLETE",
                        build_audit_payload(correlation, {"phase": "complete"}),
                    ),
                )
            )

        sink = RedactingTelemetrySink()
        for phase in ("start", "validate", "complete"):
            sink.emit(
                f"h9.{phase}",
                build_telemetry_attributes(
                    correlation,
                    {
                        "phase": phase,
                        "operator_email": sample_email,
                        "api_token": sample_secret,
                    },
                ),
                correlation_id=correlation.correlation_id,
            )

        max_records = h9["max_provenance_records"]
        max_events = h9["max_telemetry_events"]
        if not isinstance(max_records, int) or not isinstance(max_events, int):
            raise RuntimeError("H9 policy bounds are invalid")
        bundle = build_operational_audit_bundle(
            correlation,
            records,
            sink.events(),
            max_provenance_records=max_records,
            max_telemetry_events=max_events,
        )

    serialized = json.dumps(bundle, sort_keys=True)
    if sample_email in serialized or sample_secret in serialized:
        raise RuntimeError("H9 PII/secret redaction failed before evidence bundling")
    bundle_digest = verify_operational_audit_bundle(bundle)
    controls = _adversarial_controls(bundle)
    evidence: dict[str, object] = {
        "schema": "lukart.hardcore.h9-audit-evidence.v1",
        "candidate_sha": candidate,
        "checked_out_head_sha": head,
        "config_digest": config_digest,
        "policy_digest": content_digest(h9),
        "operational_audit_bundle": bundle,
        "operational_audit_bundle_digest": bundle_digest,
        "adversarial_controls": controls,
        "state": "CONTROL_PASS",
        "cryptographic_authenticity_claimed": False,
    }
    evidence["evidence_digest"] = content_digest(evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate H9 tamper-evident audit and operational evidence closure"
    )
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--run-id", default="local-h9-validation")
    parser.add_argument("--case-id", default="H9-ENGINEERING-CONTROL")
    parser.add_argument("--provider-id", default="local-validator")
    parser.add_argument("--provider-version", default="1.0.0")
    parser.add_argument("--workflow-id", default="enterprise-hardening")
    parser.add_argument(
        "--workflow-ref",
        default=".github/workflows/enterprise-hardening.yml",
    )
    parser.add_argument(
        "--output",
        default="build/hardcore/h9-tamper-evident-audit.json",
    )
    args = parser.parse_args()

    evidence = build_h9_evidence(
        args.candidate_sha,
        run_id=args.run_id,
        case_id=args.case_id,
        provider_id=args.provider_id,
        provider_version=args.provider_version,
        workflow_id=args.workflow_id,
        workflow_ref=args.workflow_ref,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("H9_TAMPER_EVIDENT_AUDIT=PASS")
    print(f"H9_CANDIDATE_SHA={evidence['candidate_sha']}")
    print(f"H9_BUNDLE_DIGEST={evidence['operational_audit_bundle_digest']}")
    print(f"H9_EVIDENCE_DIGEST={evidence['evidence_digest']}")
    print(f"H9_EVIDENCE_PATH={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
