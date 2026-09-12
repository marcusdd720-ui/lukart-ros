from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from core.case_ledger.contracts import CaseId
from core.cirp.contracts import (
    AssessmentStatus,
    CIRPContractError,
    CIRPRunIdentity,
    DeadlineAssessment,
    DeadlineSafety,
    DeadlineStatus,
    DocumentAssessment,
    DocumentKind,
    EvidenceCategory,
    EvidenceImportance,
    EvidenceRequirement,
    EvidenceRequirementStatus,
    FilingPlan,
    FilingTopologyDecision,
    FilingTopologyStatus,
    LegalSourceRef,
    LegalSourceVerificationStatus,
    MeritsStrength,
    PreflightCheck,
    PreflightFinalStatus,
    PreflightResult,
    PreflightSeverity,
    PreflightStatus,
    ProceduralAssessment,
    ProceduralRulePack,
    ProceduralStage,
    RemedyAdmissibility,
    RemedyOption,
    RulePackStatus,
    ServiceAssessment,
    ServiceStatus,
    StrategyDecision,
    StrategyDecisionStatus,
    StrategyOption,
    VerificationLevel,
    canonical_contract_json,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
NOW = datetime(2026, 9, 12, 8, 45, tzinfo=UTC)


def legal_source() -> LegalSourceRef:
    return LegalSourceRef(
        source_id="source:synthetic:v1",
        jurisdiction="PL",
        authority_type="synthetic_fixture",
        formal_citation="Synthetic procedural source 1",
        source_uri="synthetic://procedural/source-1",
        source_digest=DIGEST_A,
        effective_from=date(2026, 1, 1),
        effective_until=None,
        retrieved_at=NOW,
        verification_status=LegalSourceVerificationStatus.VERIFIED,
    )


def test_run_identity_requires_material_input_and_is_deterministic() -> None:
    run = CIRPRunIdentity(
        case_id=CaseId("CASE-SYNTHETIC-001"),
        input_evidence_ids=("sha256:evidence-1",),
        input_event_ids=(),
        rule_pack_ids=("PL-SYNTHETIC@1",),
        rule_pack_digest=DIGEST_A,
        policy_identity="policy@1",
        runtime_identity="runtime@1",
        model_identity=None,
        evaluation_time=NOW,
        configuration_digest=DIGEST_B,
    )
    assert run.digest() == run.digest()
    assert canonical_contract_json(run) == canonical_contract_json(run)

    with pytest.raises(CIRPContractError, match="requires evidence or event input"):
        CIRPRunIdentity(
            case_id=CaseId("CASE-SYNTHETIC-001"),
            input_evidence_ids=(),
            input_event_ids=(),
            rule_pack_ids=(),
            rule_pack_digest=DIGEST_A,
            policy_identity="policy@1",
            runtime_identity="runtime@1",
            evaluation_time=NOW,
            configuration_digest=DIGEST_B,
        )


def test_run_identity_rejects_naive_evaluation_time() -> None:
    with pytest.raises(CIRPContractError, match="timezone-aware"):
        CIRPRunIdentity(
            case_id=CaseId("CASE-SYNTHETIC-001"),
            input_evidence_ids=("evidence:1",),
            input_event_ids=(),
            rule_pack_ids=(),
            rule_pack_digest=DIGEST_A,
            policy_identity="policy@1",
            runtime_identity="runtime@1",
            evaluation_time=datetime(2026, 9, 12, 8, 45),
            configuration_digest=DIGEST_B,
        )


def test_verified_document_cannot_be_unknown_or_evidence_free() -> None:
    kwargs = dict(
        document_id="DOC-001",
        source_evidence_id="evidence:doc-1",
        issuer="Synthetic Authority",
        recipient="Synthetic Party",
        document_date=date(2026, 9, 1),
        case_reference="SYNTHETIC-001",
        subject="Synthetic notice",
        operative_content=("Synthetic content",),
        requested_actions=(),
        stated_deadlines=(),
        open_questions=(),
    )
    with pytest.raises(CIRPContractError, match="cannot be UNKNOWN"):
        DocumentAssessment(
            **kwargs,
            document_kind=DocumentKind.UNKNOWN,
            classification_status=AssessmentStatus.VERIFIED,
            evidence_refs=("evidence:doc-1",),
        )
    with pytest.raises(CIRPContractError, match="requires evidence_refs"):
        DocumentAssessment(
            **kwargs,
            document_kind=DocumentKind.NOTICE,
            classification_status=AssessmentStatus.VERIFIED,
            evidence_refs=(),
        )


def test_verified_procedural_assessment_requires_known_stage_and_evidence() -> None:
    with pytest.raises(CIRPContractError, match="cannot be UNKNOWN"):
        ProceduralAssessment(
            jurisdiction="PL",
            procedure_family="SYNTHETIC",
            procedural_stage=ProceduralStage.UNKNOWN,
            issuing_authority=None,
            competent_authority=None,
            review_authority=None,
            filing_authority=None,
            filing_via=None,
            procedural_subject="Synthetic subject",
            available_action_required=None,
            status=AssessmentStatus.VERIFIED,
            supporting_rules=(),
            evidence_refs=("evidence:1",),
            unresolved=(),
        )


def test_service_conflict_remains_unsettled() -> None:
    assessment = ServiceAssessment(
        service_required=True,
        service_method="registered delivery",
        service_date=None,
        service_time=None,
        evidence_refs=("evidence:receipt-a", "evidence:receipt-b"),
        source_status=ServiceStatus.CONFLICTING,
        conflicting_dates=(date(2026, 9, 10), date(2026, 9, 11)),
        assessment_status=ServiceStatus.CONFLICTING,
    )
    assert assessment.assessment_status is ServiceStatus.CONFLICTING

    with pytest.raises(CIRPContractError, match="requires >=2 dates"):
        ServiceAssessment(
            service_required=True,
            service_method=None,
            service_date=None,
            service_time=None,
            evidence_refs=("evidence:receipt-a",),
            source_status=ServiceStatus.CONFLICTING,
            conflicting_dates=(date(2026, 9, 10),),
            assessment_status=ServiceStatus.CONFLICTING,
        )


def test_verified_service_requires_evidence() -> None:
    with pytest.raises(CIRPContractError, match="requires date and evidence"):
        ServiceAssessment(
            service_required=True,
            service_method="electronic",
            service_date=date(2026, 9, 10),
            service_time=None,
            evidence_refs=(),
            source_status=ServiceStatus.USER_REPORTED,
            conflicting_dates=(),
            assessment_status=ServiceStatus.VERIFIED,
        )


def test_legal_source_effective_range_and_verified_digest() -> None:
    source = legal_source()
    assert source.effective_on(date(2026, 9, 12))

    with pytest.raises(CIRPContractError, match="requires source_digest"):
        LegalSourceRef(
            source_id="source:synthetic:v2",
            jurisdiction="PL",
            authority_type="synthetic_fixture",
            formal_citation="Synthetic source",
            source_uri="synthetic://source",
            source_digest=None,
            effective_from=date(2026, 1, 1),
            effective_until=None,
            retrieved_at=NOW,
            verification_status=LegalSourceVerificationStatus.VERIFIED,
        )


def test_rule_pack_binds_source_set_digest() -> None:
    source = legal_source()
    pack = ProceduralRulePack.build(
        pack_id="PL-SYNTHETIC",
        version="1",
        jurisdiction="PL",
        procedure_family="SYNTHETIC",
        effective_from=date(2026, 1, 1),
        effective_until=None,
        source_set=(source,),
        deadline_rules=("deadline.synthetic.1",),
        status=RulePackStatus.ACTIVE,
    )
    assert pack.source_set_digest

    with pytest.raises(CIRPContractError, match="source_set_digest mismatch"):
        ProceduralRulePack(
            pack_id=pack.pack_id,
            version=pack.version,
            jurisdiction=pack.jurisdiction,
            procedure_family=pack.procedure_family,
            effective_from=pack.effective_from,
            effective_until=pack.effective_until,
            source_set=pack.source_set,
            source_set_digest=DIGEST_B,
            deadline_rules=pack.deadline_rules,
            remedy_rules=(),
            routing_rules=(),
            formal_requirement_rules=(),
            calendar_rules=(),
            status=RulePackStatus.ACTIVE,
        )


def verified_deadline(**overrides: object) -> DeadlineAssessment:
    values: dict[str, object] = {
        "deadline_id": "deadline:1",
        "trigger_type": "SERVICE",
        "trigger_date": date(2026, 9, 10),
        "trigger_evidence": "evidence:receipt",
        "rule_pack_id": "PL-SYNTHETIC@1",
        "rule_id": "deadline.synthetic.1",
        "rule_version": "1",
        "legal_source_refs": ("source:synthetic:v1",),
        "effective_law_date": date(2026, 9, 10),
        "duration_value": 14,
        "duration_unit": "DAYS",
        "calculation_method": "SYNTHETIC",
        "calendar_profile": "PL-SYNTHETIC",
        "timezone": "Europe/Warsaw",
        "legal_deadline": date(2026, 9, 24),
        "safe_internal_deadline": date(2026, 9, 21),
        "status": DeadlineStatus.VERIFIED,
        "blocking_questions": (),
    }
    values.update(overrides)
    return DeadlineAssessment(**values)  # type: ignore[arg-type]


def test_verified_deadline_requires_trigger_rule_and_sources() -> None:
    assert verified_deadline().status is DeadlineStatus.VERIFIED
    with pytest.raises(CIRPContractError, match="trigger_evidence"):
        verified_deadline(trigger_evidence=None)
    with pytest.raises(CIRPContractError, match="legal_source_refs"):
        verified_deadline(legal_source_refs=())


def test_safe_deadline_cannot_exceed_legal_deadline() -> None:
    with pytest.raises(CIRPContractError, match="cannot exceed"):
        verified_deadline(safe_internal_deadline=date(2026, 9, 25))


def test_unknown_or_missing_deadline_requires_explicit_question() -> None:
    with pytest.raises(CIRPContractError, match="requires blocking_questions"):
        DeadlineAssessment(
            deadline_id="deadline:unknown",
            trigger_type="SERVICE",
            trigger_date=None,
            trigger_evidence=None,
            rule_pack_id=None,
            rule_id=None,
            rule_version=None,
            legal_source_refs=(),
            effective_law_date=None,
            duration_value=None,
            duration_unit=None,
            calculation_method=None,
            calendar_profile=None,
            timezone=None,
            legal_deadline=None,
            safe_internal_deadline=None,
            status=DeadlineStatus.MISSING_INPUT,
            blocking_questions=(),
        )


def test_verified_remedy_requires_rule_identity_and_no_blocker() -> None:
    with pytest.raises(CIRPContractError, match="requires applicable_rule_ids"):
        RemedyOption(
            remedy_id="remedy:1",
            remedy_type="SYNTHETIC_RESPONSE",
            target_authority="Authority A",
            filing_authority="Authority B",
            filing_via="Authority C",
            applicable_rule_ids=(),
            deadline_id="deadline:1",
            formal_requirements=(),
            required_evidence=(),
            preserves_options=(),
            waives_options=(),
            admissibility_status=RemedyAdmissibility.VERIFIED_AVAILABLE,
            blockers=(),
        )


def test_evidence_requirement_present_and_missing_are_fail_closed() -> None:
    present = EvidenceRequirement(
        requirement_id="evidence-requirement:1",
        description="Synthetic proof of service",
        category=EvidenceCategory.DEADLINE_CRITICAL,
        importance=EvidenceImportance.CRITICAL,
        required_for=("deadline:1",),
        expected_evidence_kind="PROOF_OF_SERVICE",
        status=EvidenceRequirementStatus.PRESENT,
        evidence_refs=("evidence:receipt",),
    )
    assert present.evidence_refs

    with pytest.raises(CIRPContractError, match="MISSING.*cannot contain"):
        EvidenceRequirement(
            requirement_id="evidence-requirement:2",
            description="Missing evidence",
            category=EvidenceCategory.MERITS_CRITICAL,
            importance=EvidenceImportance.CRITICAL,
            required_for=("strategy:1",),
            expected_evidence_kind="SYNTHETIC",
            status=EvidenceRequirementStatus.MISSING,
            evidence_refs=("evidence:should-not-be-here",),
        )


def strategy_option(strategy_id: str) -> StrategyOption:
    return StrategyOption(
        strategy_id=strategy_id,
        objective="Preserve procedural options",
        remedy_ids=("remedy:1",),
        proposed_actions=("Prepare synthetic response",),
        required_evidence=("evidence:receipt",),
        deadline_safety=DeadlineSafety.SAFE,
        admissibility=VerificationLevel.VERIFIED,
        merits_strength=MeritsStrength.MODERATE,
        preserves_options=("future-review",),
        closes_options=(),
        risks=("synthetic-risk",),
        advantages=("synthetic-advantage",),
        disadvantages=("synthetic-disadvantage",),
        unresolved=(),
    )


def test_recommended_strategy_requires_decisive_evidence_and_rules() -> None:
    assert strategy_option("strategy:1").digest()
    with pytest.raises(CIRPContractError, match="decisive evidence and rules"):
        StrategyDecision(
            selected_strategy_id="strategy:1",
            decision_status=StrategyDecisionStatus.RECOMMENDED,
            rationale="Synthetic rationale",
            rejected_strategy_ids=(),
            rejection_reasons={},
            decisive_evidence=(),
            decisive_rules=("rule:1",),
            unresolved_risks=(),
        )


def test_rejected_strategy_requires_reason() -> None:
    with pytest.raises(CIRPContractError, match="missing reasons"):
        StrategyDecision(
            selected_strategy_id="strategy:1",
            decision_status=StrategyDecisionStatus.RECOMMENDED,
            rationale="Synthetic rationale",
            rejected_strategy_ids=("strategy:2",),
            rejection_reasons={},
            decisive_evidence=("evidence:1",),
            decisive_rules=("rule:1",),
            unresolved_risks=(),
        )


def test_non_recommended_decision_cannot_select_strategy() -> None:
    with pytest.raises(CIRPContractError, match="cannot select"):
        StrategyDecision(
            selected_strategy_id="strategy:1",
            decision_status=StrategyDecisionStatus.NEEDS_EVIDENCE,
            rationale="Need more evidence",
            rejected_strategy_ids=(),
            rejection_reasons={},
            decisive_evidence=(),
            decisive_rules=(),
            unresolved_risks=("missing evidence",),
        )


def test_single_filing_safe_requires_one_and_no_blockers() -> None:
    decision = FilingTopologyDecision(
        status=FilingTopologyStatus.SINGLE_FILING_SAFE,
        filing_count=1,
        combined_remedies=("remedy:1", "remedy:2"),
        separated_remedies=(),
        rationale="Synthetic compatible route",
        blockers=(),
    )
    assert decision.filing_count == 1

    with pytest.raises(CIRPContractError, match="one filing and no blockers"):
        FilingTopologyDecision(
            status=FilingTopologyStatus.SINGLE_FILING_SAFE,
            filing_count=1,
            combined_remedies=("remedy:1",),
            separated_remedies=(),
            rationale="Synthetic",
            blockers=("route conflict",),
        )


def test_no_filing_required_must_be_empty() -> None:
    with pytest.raises(CIRPContractError, match="zero filing work"):
        FilingTopologyDecision(
            status=FilingTopologyStatus.NO_FILING_REQUIRED,
            filing_count=0,
            combined_remedies=("remedy:1",),
            separated_remedies=(),
            rationale="No filing",
            blockers=(),
        )


def test_filing_plan_requires_requests_remedy_and_rule() -> None:
    with pytest.raises(CIRPContractError, match="at least one request"):
        FilingPlan(
            filing_id="filing:1",
            filing_type="SYNTHETIC",
            target_authority="Review Authority",
            filing_authority="Filing Authority",
            filing_via="Intermediary Authority",
            objective="Synthetic objective",
            requests=(),
            allegations_or_grounds=(),
            remedy_ids=("remedy:1",),
            rule_refs=("rule:1",),
            evidence_refs=("evidence:1",),
            attachment_requirements=(),
            signature_requirements=(),
            copy_requirements=(),
            deadline_id="deadline:1",
            delivery_method="synthetic-channel",
            topology_status=FilingTopologyStatus.SINGLE_FILING_SAFE,
        )


def test_filing_ready_requires_all_critical_checks_pass() -> None:
    pass_check = PreflightCheck(
        check_id="deadline-verified",
        severity=PreflightSeverity.CRITICAL,
        status=PreflightStatus.PASS,
        reason="Synthetic deadline verified",
        evidence_refs=("evidence:1",),
    )
    result = PreflightResult(
        filing_id="filing:1",
        checks=(pass_check,),
        blockers=(),
        warnings=(),
        final_status=PreflightFinalStatus.FILING_READY,
    )
    assert result.final_status is PreflightFinalStatus.FILING_READY

    unknown_check = PreflightCheck(
        check_id="route-verified",
        severity=PreflightSeverity.CRITICAL,
        status=PreflightStatus.UNKNOWN,
        reason="Synthetic route unresolved",
        evidence_refs=(),
    )
    with pytest.raises(CIRPContractError, match="all critical checks PASS"):
        PreflightResult(
            filing_id="filing:1",
            checks=(pass_check, unknown_check),
            blockers=(),
            warnings=(),
            final_status=PreflightFinalStatus.FILING_READY,
        )


def test_contracts_are_canonical_and_content_sensitive() -> None:
    left = strategy_option("strategy:1")
    right = strategy_option("strategy:2")
    assert left.digest() != right.digest()
    assert '"schema":"lukart.cirp.strategy-option.v1"' in canonical_contract_json(left)
