from __future__ import annotations

from agents.certification import (
    AgentCertificationStatus,
    AgentCertificationThresholds,
    AgentCertifier,
    contract_sha256,
)
from agents.certification_program import (
    AgentCertificationProgram,
    CertificationProgramEvidence,
    CertificationProgramStatus,
    router_certification_update,
)
from agents.reference_fact import REFERENCE_FACT_AGENT_ID, ReferenceFactAgent
from validation.extraction_quality import ExtractionMetrics
from validation.independent_evaluation import ReviewOutcome


def _metrics(*, passing: bool) -> ExtractionMetrics:
    score = 1.0 if passing else 0.5
    return ExtractionMetrics(
        true_positive=10 if passing else 1,
        false_positive=0 if passing else 1,
        false_negative=0 if passing else 1,
        precision=score,
        recall=score,
        f1=score,
        critical_true_positive=5 if passing else 1,
        critical_false_positive=0,
        critical_false_negative=0 if passing else 2,
        critical_recall=score,
        critical_precision=score,
        critical_fact_loss=0 if passing else 2,
        case_number_false_positive_rate=0.0,
        provenance_completeness=1.0,
    )


def _certifier(*, require_independent_review: bool = True) -> AgentCertifier:
    return AgentCertifier(
        AgentCertificationThresholds(
            min_precision=0.95,
            min_recall=0.90,
            min_f1=0.92,
            min_critical_recall=0.95,
        ),
        require_independent_review=require_independent_review,
    )


def _evidence(
    *,
    e2e_passed: bool = True,
    contract_digest: str | None = None,
    independent_review_required: bool = True,
) -> CertificationProgramEvidence:
    agent = ReferenceFactAgent()
    return CertificationProgramEvidence(
        validated_sha="a" * 40,
        expected_contract_sha256=contract_digest or contract_sha256(agent.contract),
        engineering_validated=True,
        e2e_suite_passed=e2e_passed,
        e2e_report_sha256="b" * 64,
        independent_review_required=independent_review_required,
    )


def _analytical_report(
    *,
    passing: bool,
    review: ReviewOutcome,
    require_independent_review: bool = True,
):  # type: ignore[no-untyped-def]
    agent = ReferenceFactAgent()
    return _certifier(require_independent_review=require_independent_review).evaluate(
        agent.contract,
        _metrics(passing=passing),
        corpus_version="1.0.0",
        split_name="validation",
        external_review=review,
    )


def test_rejected_analytical_agent_cannot_be_elevated_by_e2e_pass() -> None:
    analytical = _analytical_report(passing=False, review=ReviewOutcome.PASS)

    report = AgentCertificationProgram().evaluate(analytical, _evidence())

    assert report.status is CertificationProgramStatus.REJECTED
    assert "ANALYTICAL_CERTIFICATION_REJECTED" in report.failures
    assert router_certification_update(REFERENCE_FACT_AGENT_ID, report) == {}


def test_external_review_is_mandatory_for_program_certification() -> None:
    analytical = _analytical_report(passing=True, review=ReviewOutcome.PENDING)

    report = AgentCertificationProgram().evaluate(analytical, _evidence())

    assert report.status is CertificationProgramStatus.PENDING_EXTERNAL_REVIEW
    assert report.independent_review_required is True
    assert report.failures == ()
    assert router_certification_update(REFERENCE_FACT_AGENT_ID, report) == {}


def test_independent_mode_rejects_not_performed_as_certification_proof() -> None:
    analytical = _analytical_report(
        passing=True,
        review=ReviewOutcome.NOT_PERFORMED,
    )

    report = AgentCertificationProgram().evaluate(analytical, _evidence())

    assert analytical.status is AgentCertificationStatus.PENDING_EXTERNAL_REVIEW
    assert report.status is CertificationProgramStatus.PENDING_EXTERNAL_REVIEW
    assert report.external_review is ReviewOutcome.NOT_PERFORMED
    assert router_certification_update(REFERENCE_FACT_AGENT_ID, report) == {}


def test_solo_mode_can_certify_without_fabricating_external_review_pass() -> None:
    analytical = _analytical_report(
        passing=True,
        review=ReviewOutcome.NOT_PERFORMED,
        require_independent_review=False,
    )
    report = AgentCertificationProgram().evaluate(
        analytical,
        _evidence(independent_review_required=False),
    )
    eligibility = router_certification_update(REFERENCE_FACT_AGENT_ID, report)

    expected_key = (
        str(REFERENCE_FACT_AGENT_ID),
        ReferenceFactAgent().contract.version,
    )
    assert analytical.status is AgentCertificationStatus.CERTIFIED
    assert analytical.external_review is ReviewOutcome.NOT_PERFORMED
    assert report.status is CertificationProgramStatus.CERTIFIED
    assert report.external_review is ReviewOutcome.NOT_PERFORMED
    assert report.independent_review_required is False
    assert eligibility == {expected_key: AgentCertificationStatus.CERTIFIED}


def test_full_evidence_can_produce_program_certification_and_router_eligibility() -> None:
    analytical = _analytical_report(passing=True, review=ReviewOutcome.PASS)

    report = AgentCertificationProgram().evaluate(analytical, _evidence())
    eligibility = router_certification_update(REFERENCE_FACT_AGENT_ID, report)
    expected_key = (
        str(REFERENCE_FACT_AGENT_ID),
        ReferenceFactAgent().contract.version,
    )

    assert report.status is CertificationProgramStatus.CERTIFIED
    assert report.independent_review_required is True
    assert report.failures == ()
    assert len(report.digest()) == 64
    assert eligibility == {expected_key: AgentCertificationStatus.CERTIFIED}


def test_contract_or_e2e_failure_blocks_program_certification() -> None:
    analytical = _analytical_report(passing=True, review=ReviewOutcome.PASS)

    wrong_contract = AgentCertificationProgram().evaluate(
        analytical,
        _evidence(contract_digest="c" * 64),
    )
    failed_e2e = AgentCertificationProgram().evaluate(
        analytical,
        _evidence(e2e_passed=False),
    )

    assert wrong_contract.status is CertificationProgramStatus.REJECTED
    assert "CONTRACT_DIGEST_MISMATCH" in wrong_contract.failures
    assert failed_e2e.status is CertificationProgramStatus.REJECTED
    assert "E2E_SUITE_REQUIRED" in failed_e2e.failures
    assert router_certification_update(REFERENCE_FACT_AGENT_ID, wrong_contract) == {}
    assert router_certification_update(REFERENCE_FACT_AGENT_ID, failed_e2e) == {}
