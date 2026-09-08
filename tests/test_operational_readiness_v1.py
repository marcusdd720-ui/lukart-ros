from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.enterprise.operational_readiness_v1 import (
    OperationalReadinessPolicyV1,
    OperationalReadinessReportV1,
    OperationalReadinessV1Error,
    ReadinessOutcome,
    SLISpecV1,
    TelemetryEventName,
    TelemetryEventV1,
    detect_incident,
    evaluate_sli,
    run_operational_readiness_drill,
)

SHA = "1" * 40
OTHER_SHA = "2" * 40


def _runbook() -> str:
    return Path("docs/POST_V1_OPERATIONS.md").read_text(encoding="utf-8")


def test_reference_policy_is_fixed_content_addressed_contract() -> None:
    first = OperationalReadinessPolicyV1.reference()
    second = OperationalReadinessPolicyV1.reference()

    assert first == second
    assert first.policy_digest == second.policy_digest
    assert len(first.sli_specs) == 7
    assert len(first.incident_rules) == 6
    assert all(spec.max_failures == 0 for spec in first.sli_specs)


def test_error_budget_breach_is_fail_not_partial_pass() -> None:
    spec = SLISpecV1(
        "synthetic-sli",
        total_samples=10,
        required_successes=9,
        max_failures=1,
    )

    result = evaluate_sli(spec, successes=8, failures=2)

    assert result.outcome is ReadinessOutcome.FAIL
    assert result.error_budget_consumed == 2
    assert result.error_budget_remaining == 0


def test_incident_detection_fails_closed_for_unknown_signal() -> None:
    with pytest.raises(OperationalReadinessV1Error, match="unknown or ambiguous"):
        detect_incident("unknown-signal")


def test_telemetry_contract_rejects_untyped_event() -> None:
    with pytest.raises(OperationalReadinessV1Error, match="unknown telemetry"):
        TelemetryEventV1(
            event="raw-case-payload",  # type: ignore[arg-type]
            component="bad-telemetry",
            outcome=ReadinessOutcome.PASS,
            code_sha=SHA,
            evidence_digest="a" * 64,
        )


def test_exact_sha_mismatch_fails_before_operational_drill(tmp_path: Path) -> None:
    with pytest.raises(OperationalReadinessV1Error, match="does not match"):
        run_operational_readiness_drill(
            code_sha=SHA,
            expected_code_sha=OTHER_SHA,
            workspace=tmp_path,
            runbook_text=_runbook(),
        )


def test_noncanonical_sha_fails_closed(tmp_path: Path) -> None:
    bad_sha = "A" * 40
    with pytest.raises(OperationalReadinessV1Error, match="canonical lowercase"):
        run_operational_readiness_drill(
            code_sha=bad_sha,
            expected_code_sha=bad_sha,
            workspace=tmp_path,
            runbook_text=_runbook(),
        )


def test_exact_sha_operational_drill_is_deterministic(tmp_path: Path) -> None:
    first = run_operational_readiness_drill(
        code_sha=SHA,
        expected_code_sha=SHA,
        workspace=tmp_path / "first",
        runbook_text=_runbook(),
    )
    second = run_operational_readiness_drill(
        code_sha=SHA,
        expected_code_sha=SHA,
        workspace=tmp_path / "second",
        runbook_text=_runbook(),
    )

    assert first.outcome is ReadinessOutcome.PASS
    assert first.report_digest == second.report_digest
    assert first.canonical_dict() == second.canonical_dict()
    assert all(item.outcome is ReadinessOutcome.PASS for item in first.sli_results)
    assert len(first.telemetry) == 7


def test_missing_runbook_control_exhausts_zero_error_budget(tmp_path: Path) -> None:
    runbook = _runbook().replace("## Runbook validation\n", "")

    report = run_operational_readiness_drill(
        code_sha=SHA,
        expected_code_sha=SHA,
        workspace=tmp_path,
        runbook_text=runbook,
    )

    by_id = {item.spec.sli_id: item for item in report.sli_results}
    assert report.outcome is ReadinessOutcome.FAIL
    assert by_id["runbook_contract_coverage_ratio"].failures == 1
    assert by_id["runbook_contract_coverage_ratio"].outcome is ReadinessOutcome.FAIL


def test_report_rejects_telemetry_bound_to_different_sha(tmp_path: Path) -> None:
    report = run_operational_readiness_drill(
        code_sha=SHA,
        expected_code_sha=SHA,
        workspace=tmp_path,
        runbook_text=_runbook(),
    )
    altered_event = replace(report.telemetry[0], code_sha=OTHER_SHA)

    with pytest.raises(OperationalReadinessV1Error, match="telemetry is not bound"):
        OperationalReadinessReportV1(
            code_sha=report.code_sha,
            policy_digest=report.policy_digest,
            fiv02_report_digest=report.fiv02_report_digest,
            runbook_digest=report.runbook_digest,
            sli_results=report.sli_results,
            telemetry=(altered_event, *report.telemetry[1:]),
            incident_rule_digests=report.incident_rule_digests,
            outcome=report.outcome,
        )


def test_telemetry_has_no_arbitrary_payload_surface() -> None:
    fields = TelemetryEventV1.__dataclass_fields__

    assert set(fields) == {
        "event",
        "component",
        "outcome",
        "code_sha",
        "evidence_digest",
        "schema",
    }
    assert TelemetryEventName.RECOVERY_DRILL.value == "recovery_drill"
