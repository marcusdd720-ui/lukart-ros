from types import SimpleNamespace

from core.cirp.contracts import (
    PreflightFinalStatus,
    PreflightSeverity,
    PreflightStatus,
)
from core.cirp.preflight import FilingExecutionState, HardcorePreflight


class _PreflightHarness(HardcorePreflight):
    def __init__(self, terminal_status: PreflightStatus) -> None:
        self._terminal_status = terminal_status

    def _identity_check(self, plan):
        return self._check("identity", PreflightStatus.PASS, "ok")

    @staticmethod
    def _selected_remedies(plan, remedy_map):
        return (), None

    def _route_check(self, plan, selected):
        return self._check("route", PreflightStatus.PASS, "ok")

    def _deadline_check(self, plan, selected, deadline_map):
        return self._check("deadline", PreflightStatus.PASS, "ok")

    def _semantic_requests_check(self, plan):
        return self._check("requests", PreflightStatus.PASS, "ok")

    def _rule_basis_check(self, plan, selected):
        return self._check("rules", PreflightStatus.PASS, "ok")

    def _evidence_check(self, plan, selected, available_evidence):
        return self._check("evidence", PreflightStatus.PASS, "ok")

    def _formal_check(self, selected, execution):
        return self._check("formal", PreflightStatus.PASS, "ok")

    def _attachment_check(self, plan, execution):
        return self._check("attachments", PreflightStatus.PASS, "ok")

    def _signature_check(self, plan, execution):
        return self._check("signature", PreflightStatus.PASS, "ok")

    def _copies_check(self, plan, execution):
        return self._check("copies", PreflightStatus.PASS, "ok")

    def _topology_check(self, plan):
        return self._check("topology", PreflightStatus.PASS, "ok")

    def _unknowns_check(self, execution):
        return self._check("terminal", self._terminal_status, "synthetic critical state")


def _evaluate(status: PreflightStatus):
    plan = SimpleNamespace(filing_id="FILING-TEST-1", filing_type="APPEAL", remedy_ids=())
    execution = FilingExecutionState(filing_id="FILING-TEST-1")
    return _PreflightHarness(status).evaluate(
        plan=plan,
        remedies=(),
        deadlines=(),
        available_evidence_ids=(),
        execution=execution,
    )


def test_critical_fail_cannot_be_filing_ready() -> None:
    result = _evaluate(PreflightStatus.FAIL)
    assert result.final_status is PreflightFinalStatus.NOT_READY
    assert result.blockers
    assert any(check.severity is PreflightSeverity.CRITICAL for check in result.checks)


def test_critical_unknown_requires_abstain_not_filing_ready() -> None:
    result = _evaluate(PreflightStatus.UNKNOWN)
    assert result.final_status is PreflightFinalStatus.ABSTAIN
    assert result.blockers


def test_only_all_critical_pass_can_be_filing_ready() -> None:
    result = _evaluate(PreflightStatus.PASS)
    assert result.final_status is PreflightFinalStatus.FILING_READY
    assert result.blockers == ()
