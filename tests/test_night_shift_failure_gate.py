from pathlib import Path

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.failure_gate import (
    FailureInjectionEvidence,
    FailureInjectionReport,
    FailureOutcome,
    failure_suite_profile_digest,
    load_failure_report,
    load_failure_suite_max_age_seconds,
    load_required_failure_scenarios,
)
from core.p3.contracts import content_digest

POLICY = Path("docs/execution_profiles/NIGHT_SHIFT_POLICY_V2.yaml")
PROFILE = Path("docs/execution_profiles/NIGHT_SHIFT_FAILURE_INJECTION_V2.yaml")
REFERENCE = Path("docs/execution_profiles/NIGHT_SHIFT_FAILURE_EVIDENCE_V1.yaml")
SUBJECT_SHA = "d" * 40
STATE_DIGEST = "e" * 64
TASK_DIGEST = "f" * 64
POLICY_DIGEST = "a" * 64
SUITE_DIGEST = "b" * 64
NOW = 20


def _item(
    scenario: str,
    outcome: FailureOutcome = FailureOutcome.RECOVERED,
) -> FailureInjectionEvidence:
    return FailureInjectionEvidence(
        scenario=scenario,
        outcome=outcome,
        evidence_ref=f"test:{scenario}",
        evidence_digest=content_digest(
            {"scenario": scenario, "outcome": outcome.value}
        ),
    )


def _complete() -> FailureInjectionReport:
    required = load_required_failure_scenarios(POLICY)
    return FailureInjectionReport(
        subject_sha=SUBJECT_SHA,
        state_snapshot_digest=STATE_DIGEST,
        task_capsule_digest=TASK_DIGEST,
        policy_digest=POLICY_DIGEST,
        suite_profile_digest=SUITE_DIGEST,
        generated_at_epoch=10,
        expires_at_epoch=100,
        evidence=tuple(_item(item) for item in required),
    )


def _require(
    report: FailureInjectionReport,
    *,
    report_digest: str | None = None,
    subject_sha: str = SUBJECT_SHA,
    state_digest: str = STATE_DIGEST,
    task_digest: str = TASK_DIGEST,
    policy_digest: str = POLICY_DIGEST,
    suite_digest: str = SUITE_DIGEST,
    now_epoch: int = NOW,
) -> None:
    report.require_passed(
        required_scenarios=load_required_failure_scenarios(POLICY),
        expected_subject_sha=subject_sha,
        expected_state_snapshot_digest=state_digest,
        expected_task_capsule_digest=task_digest,
        expected_policy_digest=policy_digest,
        expected_suite_profile_digest=suite_digest,
        now_epoch=now_epoch,
        expected_report_digest=(
            report.digest() if report_digest is None else report_digest
        ),
    )


def test_policy_exposes_all_architecture_v2_failure_scenarios() -> None:
    required = load_required_failure_scenarios(POLICY)
    assert required == tuple(
        sorted(
            (
                "concurrent_branch_advance",
                "corrupted_receipt",
                "delayed_ci",
                "disk_pressure",
                "duplicate_event_delivery",
                "network_loss_during_push",
                "reviewer_timeout",
                "scheduler_restart_after_dispatch",
                "stale_worker_resumption",
                "worker_termination_during_edit",
                "worker_termination_during_validation",
            )
        )
    )


def test_complete_failure_report_passes() -> None:
    _require(_complete())


def test_missing_failure_scenario_fails_closed() -> None:
    report = _complete()
    incomplete = FailureInjectionReport(
        report.subject_sha,
        report.state_snapshot_digest,
        report.task_capsule_digest,
        report.policy_digest,
        report.suite_profile_digest,
        report.generated_at_epoch,
        report.expires_at_epoch,
        report.evidence[:-1],
    )
    with pytest.raises(NightShiftContractError, match="evidence incomplete"):
        _require(incomplete)


def test_unsafe_failure_scenario_fails_closed() -> None:
    report = _complete()
    evidence = list(report.evidence)
    evidence[0] = _item(evidence[0].scenario, FailureOutcome.UNSAFE)
    unsafe = FailureInjectionReport(
        report.subject_sha,
        report.state_snapshot_digest,
        report.task_capsule_digest,
        report.policy_digest,
        report.suite_profile_digest,
        report.generated_at_epoch,
        report.expires_at_epoch,
        tuple(evidence),
    )
    with pytest.raises(NightShiftContractError, match="scenario unsafe"):
        _require(unsafe)


def test_duplicate_failure_scenario_fails_closed() -> None:
    first = _item("duplicate_event_delivery")
    with pytest.raises(NightShiftContractError, match="duplicate"):
        FailureInjectionReport(
            SUBJECT_SHA,
            STATE_DIGEST,
            TASK_DIGEST,
            POLICY_DIGEST,
            SUITE_DIGEST,
            10,
            100,
            (first, first),
        )


def test_expired_failure_report_fails_closed() -> None:
    with pytest.raises(NightShiftContractError, match="report expired"):
        _require(_complete(), now_epoch=100)


def test_wrong_policy_or_profile_fails_closed() -> None:
    report = _complete()
    with pytest.raises(NightShiftContractError, match="different policy"):
        _require(report, policy_digest="c" * 64)
    with pytest.raises(NightShiftContractError, match="different suite profile"):
        _require(report, suite_digest="c" * 64)


def test_wrong_subject_sha_fails_closed() -> None:
    with pytest.raises(NightShiftContractError, match="different subject SHA"):
        _require(_complete(), subject_sha="c" * 40)


def test_wrong_state_snapshot_fails_closed() -> None:
    with pytest.raises(NightShiftContractError, match="different state snapshot"):
        _require(_complete(), state_digest="c" * 64)


def test_wrong_task_capsule_fails_closed() -> None:
    with pytest.raises(NightShiftContractError, match="different task capsule"):
        _require(_complete(), task_digest="c" * 64)


def test_wrong_report_digest_fails_closed() -> None:
    with pytest.raises(NightShiftContractError, match="digest does not match"):
        _require(_complete(), report_digest="c" * 64)


def test_profile_declares_positive_report_ttl() -> None:
    assert load_failure_suite_max_age_seconds(PROFILE) == 3600
    assert len(failure_suite_profile_digest(PROFILE)) == 64


def test_reference_manifest_loads_all_11_scenarios() -> None:
    report = load_failure_report(
        REFERENCE,
        subject_sha=SUBJECT_SHA,
        state_snapshot_digest=STATE_DIGEST,
        task_capsule_digest=TASK_DIGEST,
        policy_digest=POLICY_DIGEST,
        suite_profile_digest=SUITE_DIGEST,
        generated_at_epoch=10,
        expires_at_epoch=100,
    )
    _require(report)
