from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from core.case_ledger.contracts import CaseId
from core.cirp.contracts import (
    AssessmentStatus,
    CIRPContractError,
    CIRPRunIdentity,
    DeadlineSafety,
    DeadlineStatus,
    DocumentAssessment,
    DocumentKind,
    EvidenceCategory,
    EvidenceImportance,
    EvidenceRequirement,
    EvidenceRequirementStatus,
    LegalSourceRef,
    LegalSourceVerificationStatus,
    MeritsStrength,
    ProceduralAssessment,
    ProceduralRulePack,
    ProceduralStage,
    RemedyAdmissibility,
    RulePackStatus,
    ServiceAssessment,
    ServiceStatus,
    StrategyDecisionStatus,
    StrategyOption,
    VerificationLevel,
)
from core.cirp.deadline import (
    DeadlineCalendarProfile,
    DeadlineDurationUnit,
    DeadlineRollConvention,
    DeadlineStartRule,
    DeadlineTriggerStatus,
    ExecutableDeadlineRule,
)
from core.cirp.engine import (
    CIRPRunRequest,
    CanonicalCIRPRuntime,
    DeadlineEvaluationRequest,
    RemedyEvaluationRequest,
    canonical_rule_pack_set_digest,
)
from core.cirp.filing import FilingSpec
from core.cirp.preflight import FilingExecutionState
from core.cirp.remedy import ExecutableRemedyRule, RemedyApplicabilityStatus
from core.cirp.report import CIRPReportStatus
from core.p3.contracts import content_digest

NOW = datetime(2026, 9, 12, 11, 0, tzinfo=UTC)
LAW_DATE = date(2026, 9, 12)
SERVICE_DATE = date(2026, 9, 11)
DOC_EVIDENCE = "evidence:p01:document"
SERVICE_EVIDENCE = "evidence:p01:service"
MATERIAL_EVIDENCE = "evidence:p01:material"
PACK_ID = "PL-P01-SYNTHETIC@1"
DEADLINE_ID = "deadline:p01:response"
REMEDY_ID = "remedy:p01:response"
REQUIREMENT_ID = "requirement:p01:material"
STRATEGY_ID = "strategy:p01:respond"
FILING_ID = "filing:p01:response"


def source() -> LegalSourceRef:
    return LegalSourceRef(
        source_id="source:p01:synthetic",
        jurisdiction="PL",
        authority_type="synthetic_fixture",
        formal_citation="Synthetic P01 source",
        source_uri="synthetic://p01/source",
        source_digest="a" * 64,
        effective_from=date(2026, 1, 1),
        effective_until=None,
        retrieved_at=NOW,
        verification_status=LegalSourceVerificationStatus.VERIFIED,
    )


def calendar() -> DeadlineCalendarProfile:
    return DeadlineCalendarProfile(
        profile_id="PL-P01-CALENDAR@1",
        timezone="Europe/Warsaw",
        weekend_days=(5, 6),
        legal_source_ids=("source:p01:synthetic",),
    )


def deadline_rule(
    selected_calendar: DeadlineCalendarProfile,
) -> ExecutableDeadlineRule:
    return ExecutableDeadlineRule.build(
        rule_id="PL-P01-DEADLINE",
        version="1",
        trigger_type="SERVICE_DATE",
        duration_value=7,
        duration_unit=DeadlineDurationUnit.CALENDAR_DAYS,
        start_rule=DeadlineStartRule.EXCLUDE_TRIGGER,
        roll_convention=DeadlineRollConvention.NEXT_BUSINESS_DAY,
        calendar_profile=selected_calendar,
        legal_source_ids=("source:p01:synthetic",),
        effective_from=date(2026, 1, 1),
    )


def remedy_rule() -> ExecutableRemedyRule:
    return ExecutableRemedyRule(
        rule_id="PL-P01-REMEDY",
        version="1",
        remedy_type="SYNTHETIC_RESPONSE",
        target_authority="synthetic-target",
        filing_authority="synthetic-filing-authority",
        filing_via="synthetic-route",
        formal_requirements=("formal:p01:signature",),
        required_evidence_ids=(REQUIREMENT_ID,),
        preserves_options=("option:p01:review",),
        waives_options=(),
        legal_source_ids=("source:p01:synthetic",),
        deadline_required=True,
        effective_from=date(2026, 1, 1),
    )


def rule_pack(
    selected_deadline_rule: ExecutableDeadlineRule,
    selected_remedy_rule: ExecutableRemedyRule,
) -> ProceduralRulePack:
    return ProceduralRulePack.build(
        pack_id=PACK_ID,
        version="1",
        jurisdiction="PL",
        procedure_family="synthetic_p01",
        effective_from=date(2026, 1, 1),
        effective_until=None,
        source_set=(source(),),
        deadline_rules=(selected_deadline_rule.pack_token,),
        remedy_rules=(selected_remedy_rule.pack_token,),
        status=RulePackStatus.ACTIVE,
    )


def document() -> DocumentAssessment:
    return DocumentAssessment(
        document_id="document:p01:notice",
        source_evidence_id=DOC_EVIDENCE,
        document_kind=DocumentKind.NOTICE,
        issuer="Synthetic Authority",
        recipient="Synthetic Party",
        document_date=date(2026, 9, 10),
        case_reference="SYNTHETIC-P01",
        subject="Synthetic response notice",
        operative_content=("Synthetic response is requested.",),
        requested_actions=("Submit synthetic response.",),
        stated_deadlines=("Seven calendar days from service.",),
        classification_status=AssessmentStatus.VERIFIED,
        evidence_refs=(DOC_EVIDENCE,),
        open_questions=(),
    )


def procedural(selected_remedy_rule: ExecutableRemedyRule) -> ProceduralAssessment:
    return ProceduralAssessment(
        jurisdiction="PL",
        procedure_family="synthetic_p01",
        procedural_stage=ProceduralStage.RESPONSE_REQUIRED,
        issuing_authority="Synthetic Authority",
        competent_authority="Synthetic Target",
        review_authority=None,
        filing_authority="synthetic-filing-authority",
        filing_via="synthetic-route",
        procedural_subject="Synthetic response",
        available_action_required=True,
        status=AssessmentStatus.VERIFIED,
        supporting_rules=(selected_remedy_rule.pack_token,),
        evidence_refs=(DOC_EVIDENCE,),
        unresolved=(),
    )


def verified_service() -> ServiceAssessment:
    return ServiceAssessment(
        service_required=True,
        service_method="synthetic-electronic",
        service_date=SERVICE_DATE,
        service_time=None,
        evidence_refs=(SERVICE_EVIDENCE,),
        source_status=ServiceStatus.VERIFIED,
        conflicting_dates=(),
        assessment_status=ServiceStatus.VERIFIED,
    )


def conflicting_service() -> ServiceAssessment:
    return ServiceAssessment(
        service_required=True,
        service_method="synthetic-electronic",
        service_date=None,
        service_time=None,
        evidence_refs=(SERVICE_EVIDENCE, "evidence:p01:service-conflict"),
        source_status=ServiceStatus.CONFLICTING,
        conflicting_dates=(date(2026, 9, 10), SERVICE_DATE),
        assessment_status=ServiceStatus.CONFLICTING,
    )


def requirement(
    *,
    status: EvidenceRequirementStatus = EvidenceRequirementStatus.PRESENT,
) -> EvidenceRequirement:
    refs = (MATERIAL_EVIDENCE,) if status is EvidenceRequirementStatus.PRESENT else ()
    return EvidenceRequirement(
        requirement_id=REQUIREMENT_ID,
        description="Synthetic material evidence",
        category=EvidenceCategory.ADMISSIBILITY_CRITICAL,
        importance=EvidenceImportance.CRITICAL,
        required_for=("PL-P01-REMEDY@1",),
        expected_evidence_kind="SYNTHETIC_DOCUMENT",
        status=status,
        evidence_refs=refs,
    )


def strategy(
    *,
    strategy_id: str = STRATEGY_ID,
) -> StrategyOption:
    return StrategyOption(
        strategy_id=strategy_id,
        objective="Preserve synthetic response rights",
        remedy_ids=(REMEDY_ID,),
        proposed_actions=("Prepare the synthetic response.",),
        required_evidence=(MATERIAL_EVIDENCE,),
        deadline_safety=DeadlineSafety.SAFE,
        admissibility=VerificationLevel.VERIFIED,
        merits_strength=MeritsStrength.MODERATE,
        preserves_options=("option:p01:review",),
        closes_options=(),
        risks=(),
        advantages=("Preserves synthetic response rights.",),
        disadvantages=(),
        unresolved=(),
    )


def filing_spec(selected_remedy_rule: ExecutableRemedyRule) -> FilingSpec:
    return FilingSpec(
        filing_id=FILING_ID,
        filing_type="SYNTHETIC_RESPONSE",
        remedy_ids=(REMEDY_ID,),
        requests=("Accept synthetic response.",),
        allegations_or_grounds=("Verified synthetic ground.",),
        evidence_refs=(MATERIAL_EVIDENCE,),
        rule_refs=(selected_remedy_rule.pack_token,),
        attachment_requirements=("attachment:p01",),
        signature_requirements=("signature:p01",),
        copy_requirements=("copy:p01",),
        delivery_method="SYNTHETIC_ELECTRONIC",
    )


def execution() -> FilingExecutionState:
    return FilingExecutionState(
        filing_id=FILING_ID,
        provided_attachments=("attachment:p01",),
        satisfied_formal_requirements=("formal:p01:signature",),
        signature_ready=True,
        copies_ready=True,
    )


def request(
    *,
    service: ServiceAssessment | None = None,
    trigger_status: DeadlineTriggerStatus = DeadlineTriggerStatus.VERIFIED,
    trigger_date: date | None = SERVICE_DATE,
    trigger_evidence: str | None = SERVICE_EVIDENCE,
    deadline_rule_key: str | None = None,
    evidence_requirement: EvidenceRequirement | None = None,
    strategies: tuple[StrategyOption, ...] | None = None,
    include_filing: bool = True,
    include_execution: bool = True,
    available_evidence_ids: tuple[str, ...] | None = None,
) -> CIRPRunRequest:
    selected_calendar = calendar()
    selected_deadline_rule = deadline_rule(selected_calendar)
    selected_remedy_rule = remedy_rule()
    selected_pack = rule_pack(selected_deadline_rule, selected_remedy_rule)
    selected_service = service or verified_service()
    selected_requirement = evidence_requirement or requirement()
    selected_strategies = strategies or (strategy(),)
    available = available_evidence_ids or (
        DOC_EVIDENCE,
        SERVICE_EVIDENCE,
        MATERIAL_EVIDENCE,
    )
    run_evidence = list(
        dict.fromkeys(
            (
                DOC_EVIDENCE,
                SERVICE_EVIDENCE,
                MATERIAL_EVIDENCE,
                *selected_service.evidence_refs,
            )
        )
    )
    identity = CIRPRunIdentity(
        case_id=CaseId("case:synthetic:p01"),
        input_evidence_ids=tuple(run_evidence),
        input_event_ids=("event:synthetic:p01-intake",),
        rule_pack_ids=(PACK_ID,),
        rule_pack_digest=canonical_rule_pack_set_digest((selected_pack,)),
        policy_identity="policy:p01:synthetic:v1",
        runtime_identity="runtime:cirp-p01:canonical:v1",
        model_identity=None,
        evaluation_time=NOW,
        configuration_digest=content_digest({"configuration": "p01-synthetic-v1"}),
    )
    return CIRPRunRequest(
        run_id="cirp-run:p01:synthetic",
        run_identity=identity,
        document_assessment=document(),
        procedural_assessment=procedural(selected_remedy_rule),
        service_assessment=selected_service,
        rule_packs=(selected_pack,),
        deadline_rules=(selected_deadline_rule,),
        deadline_calendars=(selected_calendar,),
        remedy_rules=(selected_remedy_rule,),
        deadline_evaluations=(
            DeadlineEvaluationRequest(
                rule_pack_id=PACK_ID,
                deadline_id=DEADLINE_ID,
                rule_key=deadline_rule_key or selected_deadline_rule.key,
                trigger_type="SERVICE_DATE",
                trigger_date=trigger_date,
                trigger_evidence=trigger_evidence,
                trigger_status=trigger_status,
                effective_law_date=LAW_DATE,
                safe_buffer_business_days=1,
            ),
        ),
        remedy_evaluations=(
            RemedyEvaluationRequest(
                rule_pack_id=PACK_ID,
                remedy_id=REMEDY_ID,
                rule_key=selected_remedy_rule.key,
                applicability_status=RemedyApplicabilityStatus.VERIFIED,
                effective_law_date=LAW_DATE,
                deadline_id=DEADLINE_ID,
            ),
        ),
        evidence_requirements=(selected_requirement,),
        strategy_options=selected_strategies,
        available_evidence_ids=available,
        decisive_evidence=(MATERIAL_EVIDENCE,) if MATERIAL_EVIDENCE in available else (),
        decisive_rules=(selected_remedy_rule.pack_token,),
        filing_specs=(filing_spec(selected_remedy_rule),) if include_filing else (),
        execution_states=(execution(),) if include_execution else (),
    )


def test_canonical_runtime_reaches_ready_and_is_replay_deterministic() -> None:
    runtime = CanonicalCIRPRuntime()

    first = runtime.run(request())
    second = runtime.run(request())

    assert first.deadlines[0].status is DeadlineStatus.VERIFIED
    assert first.remedies[0].admissibility_status is RemedyAdmissibility.VERIFIED_AVAILABLE
    assert first.remedies[0].required_evidence == (REQUIREMENT_ID,)
    assert first.strategy_decision.decision_status is StrategyDecisionStatus.RECOMMENDED
    assert first.filing_plans[0].evidence_refs == (MATERIAL_EVIDENCE,)
    assert first.preflights[0].final_status.value == "FILING_READY"
    assert first.report.status is CIRPReportStatus.READY_TO_FILE
    assert first.replay_manifest.digest() == second.replay_manifest.digest()
    artifact_ids = {item.artifact_id for item in first.replay_manifest.artifacts}
    assert f"evidence-requirement:{REQUIREMENT_ID}" in artifact_ids
    assert f"remedy-option:{REMEDY_ID}" in artifact_ids


def test_unknown_deadline_rule_propagates_without_filing() -> None:
    selected = request(
        deadline_rule_key="UNKNOWN-DEADLINE@9",
        include_filing=False,
        include_execution=False,
    )

    result = CanonicalCIRPRuntime().run(selected)

    assert result.deadlines[0].status is DeadlineStatus.UNKNOWN_RULE
    assert result.remedies[0].admissibility_status is RemedyAdmissibility.UNKNOWN
    assert result.strategy_decision.decision_status is StrategyDecisionStatus.NEEDS_EVIDENCE
    assert result.filing_topology.status.value == "CONSOLIDATION_UNCERTAIN"
    assert result.filing_plans == ()
    assert result.report.status is CIRPReportStatus.NEEDS_EVIDENCE


def test_conflicting_service_date_stays_conflicting_and_blocks_filing() -> None:
    selected = request(
        service=conflicting_service(),
        trigger_status=DeadlineTriggerStatus.CONFLICTING,
        trigger_date=None,
        trigger_evidence=None,
        include_filing=False,
        include_execution=False,
    )

    result = CanonicalCIRPRuntime().run(selected)

    assert result.deadlines[0].status is DeadlineStatus.CONFLICTING_EVIDENCE
    assert result.remedies[0].admissibility_status is RemedyAdmissibility.UNKNOWN
    assert result.report.status is CIRPReportStatus.NEEDS_EVIDENCE


def test_missing_critical_evidence_blocks_recommendation() -> None:
    selected = request(
        evidence_requirement=requirement(status=EvidenceRequirementStatus.MISSING),
        available_evidence_ids=(DOC_EVIDENCE, SERVICE_EVIDENCE),
        include_filing=False,
        include_execution=False,
    )

    result = CanonicalCIRPRuntime().run(selected)

    assert result.remedies[0].admissibility_status is RemedyAdmissibility.UNKNOWN
    assert result.strategy_decision.decision_status is StrategyDecisionStatus.NEEDS_EVIDENCE
    assert result.report.status is CIRPReportStatus.NEEDS_EVIDENCE


def test_multiple_safe_strategies_require_human_decision_and_stop_before_filing() -> None:
    selected = request(
        strategies=(
            strategy(strategy_id="strategy:p01:a"),
            strategy(strategy_id="strategy:p01:b"),
        ),
        include_filing=False,
        include_execution=False,
    )

    result = CanonicalCIRPRuntime().run(selected)

    assert result.strategy_decision.decision_status is StrategyDecisionStatus.DECISION_REQUIRED
    assert result.filing_plans == ()
    assert result.preflights == ()
    assert result.report.status is CIRPReportStatus.DECISION_REQUIRED


def test_missing_execution_state_abstains_instead_of_claiming_ready() -> None:
    result = CanonicalCIRPRuntime().run(request(include_execution=False))

    assert result.filing_plans
    assert result.preflights[0].final_status.value == "ABSTAIN"
    assert result.report.status is CIRPReportStatus.ABSTAIN


def test_verified_topology_without_filing_spec_remains_not_ready() -> None:
    result = CanonicalCIRPRuntime().run(
        request(include_filing=False, include_execution=False)
    )

    assert result.strategy_decision.decision_status is StrategyDecisionStatus.RECOMMENDED
    assert result.filing_plans == ()
    assert result.report.status is CIRPReportStatus.NOT_READY
    assert any("filing specification" in item for item in result.report.open_questions)


def test_rule_pack_digest_mismatch_is_rejected_before_execution() -> None:
    selected = request()
    bad_identity = replace(selected.run_identity, rule_pack_digest="b" * 64)

    with pytest.raises(CIRPContractError, match="rule_pack_digest"):
        CanonicalCIRPRuntime().run(replace(selected, run_identity=bad_identity))


def test_service_trigger_cannot_contradict_service_assessment() -> None:
    selected = request()

    with pytest.raises(CIRPContractError, match="trigger date"):
        CanonicalCIRPRuntime().run(
            replace(
                selected,
                deadline_evaluations=(
                    replace(
                        selected.deadline_evaluations[0],
                        trigger_date=date(2026, 9, 10),
                    ),
                ),
            )
        )


def test_external_evidence_reference_is_rejected_before_reasoning() -> None:
    selected = request()

    with pytest.raises(CIRPContractError, match="available_evidence_ids"):
        CanonicalCIRPRuntime().run(
            replace(
                selected,
                available_evidence_ids=(
                    *selected.available_evidence_ids,
                    "evidence:outside-run",
                ),
            )
        )
