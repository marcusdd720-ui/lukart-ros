from __future__ import annotations

from agents.certification import (
    AgentCertificationThresholds,
    AgentCertifier,
    contract_sha256,
)
from agents.certification_program import (
    AgentCertificationProgram,
    CertificationProgramEvidence,
    CertificationProgramStatus,
)
from agents.reference_fact import ReferenceFactAgent
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


def _certifier() -> AgentCertifier:
    return AgentCertifier(
        AgentCertificationThresholds(
            min_precision=0.95,
            min_recall=0.90,
            min_f1=0.92,
            min_critical_recall=0.95,
        )
    )


def _evidence(*, e2e_passed: bool = True, contract_digest: str | None = None):  # type: ignore[no-untyped-def]
    agent = ReferenceFactAgent()
    return CertificationProgramEvidence(
        validated_sha="a" * 40,
        expected_contract_sha256=contract_digest or contract_sha256(agent.contract),
        engineering_validated=True,
        e2e_suite_passed=e2e_passed,
        e2e_report_sha256="b" * 64,
    )


def test_rejected_analytical_agent_cannot_be_elevated_by_e2e_pass() -> None:
    agent = ReferenceFactAgent()
    analytical = _certifier().evaluate(
        agent.contract,
        _metrics(passing=False),
        corpus_version="1.0.0",
        split_name="validation",
        external_review=ReviewOutcome.PASS,
    )

    report = AgentCertificationProgram().evaluate(analytical, _evidence())

    assert report.status is CertificationProgramStatus.REJECTED
    assert "ANALYTICAL_CERTIFICATION_REJECTED" in report.failures


def test_external_review_is_mandatory_for_program_certification() -> None:
    agent = ReferenceFactAgent()
    analytical = _certifier().evaluate(
        agent.contract,
        _metrics(passing=True),
        corpus_version="1.0.0",
        split_name="validation",
        external_review=ReviewOutcome.PENDING,
    )

    report = AgentCertificationProgram().evaluate(analytical, _evidence())

    assert report.status is CertificationProgramStatus.PENDING_EXTERNAL_REVIEW
    assert report.failures == ()


def test_full_evidence_can_produce_program_certification() -> None:
    agent = ReferenceFactAgent()
    analytical = _certifier().evaluate(
        agent.contract,
        _metrics(passing=True),
        corpus_version="1.0.0",
        split_name="validation",
        external_review=ReviewOutcome.PASS,
    )

    report = AgentCertificationProgram().evaluate(analytical, _evidence())

    assert report.status is CertificationProgramStatus.CERTIFIED
    assert report.failures == ()
    assert len(report.digest()) == 64


def test_contract_or_e2e_failure_blocks_program_certification() -> None:
    agent = ReferenceFactAgent()
    analytical = _certifier().evaluate(
        agent.contract,
        _metrics(passing=True),
        corpus_version="1.0.0",
        split_name="validation",
        external_review=ReviewOutcome.PASS,
    )

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
