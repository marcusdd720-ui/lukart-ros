from pathlib import Path

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.failure_gate import (
    FailureInjectionEvidence,
    FailureInjectionReport,
    load_required_failure_scenarios,
)

POLICY = Path("docs/execution_profiles/NIGHT_SHIFT_POLICY_V2.yaml")


def _complete() -> FailureInjectionReport:
    required = load_required_failure_scenarios(POLICY)
    return FailureInjectionReport(
        tuple(
            FailureInjectionEvidence(item, True, f"test:{item}")
            for item in required
        )
    )


def test_policy_exposes_all_required_failure_scenarios() -> None:
    required = load_required_failure_scenarios(POLICY)
    assert required == tuple(sorted((
        "concurrent_branch_advance",
        "corrupted_receipt",
        "disk_pressure",
        "duplicate_event",
        "network_loss_during_push",
        "reviewer_timeout",
        "scheduler_restart",
        "stale_worker_resume",
        "worker_termination",
    )))


def test_complete_failure_report_passes() -> None:
    required = load_required_failure_scenarios(POLICY)
    _complete().require_passed(required_scenarios=required)


def test_missing_failure_scenario_fails_closed() -> None:
    required = load_required_failure_scenarios(POLICY)
    report = FailureInjectionReport(
        tuple(
            FailureInjectionEvidence(item, True, f"test:{item}")
            for item in required[:-1]
        )
    )
    with pytest.raises(NightShiftContractError, match="evidence incomplete"):
        report.require_passed(required_scenarios=required)


def test_failed_failure_scenario_fails_closed() -> None:
    required = load_required_failure_scenarios(POLICY)
    report = _complete()
    evidence = list(report.evidence)
    evidence[0] = FailureInjectionEvidence(
        evidence[0].scenario, False, "test:failed"
    )
    with pytest.raises(NightShiftContractError, match="scenario failed"):
        FailureInjectionReport(tuple(evidence)).require_passed(
            required_scenarios=required
        )


def test_duplicate_failure_scenario_fails_closed() -> None:
    required = load_required_failure_scenarios(POLICY)
    first = FailureInjectionEvidence(required[0], True, "test:a")
    report = FailureInjectionReport((first, first))
    with pytest.raises(NightShiftContractError, match="duplicate"):
        report.require_passed(required_scenarios=required)
