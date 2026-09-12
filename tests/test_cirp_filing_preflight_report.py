from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from core.cirp.contracts import (
    CIRPContractError,
    DeadlineAssessment,
    DeadlineSafety,
    DeadlineStatus,
    EvidenceCategory,
    EvidenceImportance,
    EvidenceRequirement,
    EvidenceRequirementStatus,
    FilingPlan,
    FilingTopologyDecision,
    FilingTopologyStatus,
    MeritsStrength,
    PreflightFinalStatus,
    PreflightResult,
    RemedyAdmissibility,
    RemedyOption,
    StrategyDecision,
    StrategyDecisionStatus,
    StrategyOption,
    VerificationLevel,
)
from core.cirp.filing import FilingPlanner, FilingSpec
from core.cirp.preflight import FilingExecutionState, HardcorePreflight
from core.cirp.report import CIRPReport, CIRPReportBuilder, CIRPReportStatus


RULE = "rule:synthetic:review@1#" + "a" * 64
EVIDENCE = "evidence:synthetic:primary"
DEADLINE_ID = "deadline:synthetic:review"
REMEDY_ID = "remedy:synthetic:review"
STRATEGY_ID = "strategy:synthetic:review"
FILING_ID = "filing:synthetic:review"


def remedy(
    *,
    status: RemedyAdmissibility = RemedyAdmissibility.VERIFIED_AVAILABLE,
    deadline_id: str | None = DEADLINE_ID,
    filing_via: str | None = "synthetic-route",
) -> RemedyOption:
    blockers = (
        ()
        if status is RemedyAdmissibility.VERIFIED_AVAILABLE
        else ("synthetic blocker",)
    )
    return RemedyOption(
        remedy_id=REMEDY_ID,
        remedy_type="SYNTHETIC_REVIEW",
        target_authority="synthetic-target",
        filing_authority="synthetic-filing-authority",
        filing_via=filing_via,
        applicable_rule_ids=(RULE,),
        deadline_id=deadline_id,
        formal_requirements=("formal:synthetic:signature",),
        required_evidence=(EVIDENCE,),
        preserves_options=("option:synthetic",),
        waives_options=(),
        admissibility_status=status,
        blockers=blockers,
    )


def strategy() -> StrategyOption:
    return StrategyOption(
        strategy_id=STRATEGY_ID,
        objective="Obtain synthetic review",
        remedy_ids=(REMEDY_ID,),
        proposed_actions=("Prepare synthetic filing",),
        required_evidence=(EVIDENCE,),
        deadline_safety=DeadlineSafety.SAFE,
        admissibility=VerificationLevel.VERIFIED,
        merits_strength=MeritsStrength.MODERATE,
        preserves_options=("option:synthetic",),
        closes_options=(),
        risks=(),
        advantages=("Synthetic procedural preservation",),
        disadvantages=(),
        unresolved=(),
    )


def decision(
    status: StrategyDecisionStatus = StrategyDecisionStatus.RECOMMENDED,
) -> StrategyDecision:
    selected = (
        STRATEGY_ID
        if status is StrategyDecisionStatus.RECOMMENDED
        else None
    )
    evidence = (EVIDENCE,) if selected is not None else ()
    rules = (RULE,) if selected is not None else ()
    return StrategyDecision(
        selected_strategy_id=selected,
        decision_status=status,
        rationale="Synthetic strategy decision",
        rejected_strategy_ids=(),
        rejection_reasons={},
        decisive_evidence=evidence,
        decisive_rules=rules,
        unresolved_risks=(),
    )


def topology() -> FilingTopologyDecision:
    return FilingTopologyDecision(
        status=FilingTopologyStatus.SINGLE_FILING_SAFE,
        filing_count=1,
        combined_remedies=(REMEDY_ID,),
        separated_remedies=(),
        rationale="One verified synthetic filing unit",
        blockers=(),
    )


def verified_deadline(
    status: DeadlineStatus = DeadlineStatus.VERIFIED,
) -> DeadlineAssessment:
    blocking: tuple[str, ...] = ()
    legal_deadline: date | None = date(2030, 1, 20)
    if status in {
        DeadlineStatus.MISSING_INPUT,
        DeadlineStatus.CONFLICTING_EVIDENCE,
        DeadlineStatus.UNKNOWN_RULE,
    }:
        blocking = ("Resolve synthetic deadline state",)
        legal_deadline = None
    return DeadlineAssessment(
        deadline_id=DEADLINE_ID,
        trigger_type="SYNTHETIC_SERVICE",
        trigger_date=date(2030, 1, 10),
        trigger_evidence="evidence:synthetic:service",
        rule_pack_id="pack:synthetic",
        rule_id="deadline-rule:synthetic",
        rule_version="1",
        legal_source_refs=("source:synthetic",),
        effective_law_date=date(2030, 1, 10),
        duration_value=10,
        duration_unit="CALENDAR_DAYS",
        calculation_method="SYNTHETIC",
        calendar_profile="calendar:synthetic",
        timezone="Europe/Warsaw",
        legal_deadline=legal_deadline,
        safe_internal_deadline=None,
        status=status,
        blocking_questions=blocking,
    )


def filing_spec(
    *,
    evidence_refs: tuple[str, ...] = (EVIDENCE,),
    rule_refs: tuple[str, ...] = (RULE,),
) -> FilingSpec:
    return FilingSpec(
        filing_id=FILING_ID,
        filing_type="SYNTHETIC_REVIEW_FILING",
        remedy_ids=(REMEDY_ID,),
        requests=("Grant synthetic review",),
        allegations_or_grounds=("Synthetic verified ground",),
        evidence_refs=evidence_refs,
        rule_refs=rule_refs,
        attachment_requirements=("attachment:synthetic",),
        signature_requirements=("signature:synthetic",),
        copy_requirements=("copy:synthetic",),
        delivery_method="SYNTHETIC_ELECTRONIC",
    )


def build_plan(
    *,
    remedy_option: RemedyOption | None = None,
    deadline: DeadlineAssessment | None = None,
    spec: FilingSpec | None = None,
) -> FilingPlan:
    selected_remedy = remedy_option or remedy()
    selected_deadline = deadline or verified_deadline()
    selected_spec = spec or filing_spec()
    return FilingPlanner().plan(
        strategy_decision=decision(),
        strategies=(strategy(),),
        topology=topology(),
        remedies=(selected_remedy,),
        deadlines=(selected_deadline,),
        available_evidence_ids=(EVIDENCE,),
        specs=(selected_spec,),
    )[0]


def execution(
    *,
    provided_attachments: tuple[str, ...] = ("attachment:synthetic",),
    satisfied_formal_requirements: tuple[str, ...] = (
        "formal:synthetic:signature",
    ),
    signature_ready: bool = True,
    copies_ready: bool = True,
    critical_unknowns: tuple[str, ...] = (),
) -> FilingExecutionState:
    return FilingExecutionState(
        filing_id=FILING_ID,
        provided_attachments=provided_attachments,
        satisfied_formal_requirements=satisfied_formal_requirements,
        signature_ready=signature_ready,
        copies_ready=copies_ready,
        critical_unknowns=critical_unknowns,
    )


def ready_preflight(plan: FilingPlan) -> PreflightResult:
    return HardcorePreflight().evaluate(
        plan=plan,
        remedies=(remedy(),),
        deadlines=(verified_deadline(),),
        available_evidence_ids=(EVIDENCE,),
        execution=execution(),
    )


def evidence_requirement(
    status: EvidenceRequirementStatus = EvidenceRequirementStatus.PRESENT,
) -> EvidenceRequirement:
    refs = (EVIDENCE,) if status is EvidenceRequirementStatus.PRESENT else ()
    return EvidenceRequirement(
        requirement_id="requirement:synthetic:primary",
        description="Synthetic primary evidence",
        category=EvidenceCategory.MERITS_CRITICAL,
        importance=EvidenceImportance.CRITICAL,
        required_for=(RULE,),
        expected_evidence_kind="SYNTHETIC_DOCUMENT",
        status=status,
        evidence_refs=refs,
    )


def build_report(
    *,
    evidence_requirements: tuple[EvidenceRequirement, ...],
    plan: FilingPlan,
    preflight: PreflightResult,
    critical_unknowns: tuple[str, ...] = (),
) -> CIRPReport:
    return CIRPReportBuilder().build(
        case_id="case:synthetic:1",
        run_id="cirp-run:synthetic:1",
        document_summary="Synthetic notice",
        procedural_summary="Synthetic response stage",
        deadline_summaries=("Synthetic verified deadline",),
        remedy_summaries=("Synthetic verified remedy",),
        evidence_requirements=evidence_requirements,
        strategy_decision=decision(),
        strategy_summary="Synthetic recommended strategy",
        topology=topology(),
        filing_plans=(plan,),
        preflights=(preflight,),
        critical_unknowns=critical_unknowns,
    )


def test_filing_planner_builds_evidence_bound_plan() -> None:
    plan = build_plan()

    assert plan.filing_id == FILING_ID
    assert plan.remedy_ids == (REMEDY_ID,)
    assert plan.rule_refs == (RULE,)
    assert plan.evidence_refs == (EVIDENCE,)
    assert plan.deadline_id == DEADLINE_ID
    assert plan.topology_status is FilingTopologyStatus.SINGLE_FILING_SAFE


def test_planner_rejects_non_recommended_strategy() -> None:
    with pytest.raises(CIRPContractError, match="RECOMMENDED"):
        FilingPlanner().plan(
            strategy_decision=decision(
                StrategyDecisionStatus.NEEDS_EVIDENCE
            ),
            strategies=(strategy(),),
            topology=topology(),
            remedies=(remedy(),),
            deadlines=(verified_deadline(),),
            available_evidence_ids=(EVIDENCE,),
            specs=(filing_spec(),),
        )


def test_planner_rejects_unverified_remedy_and_deadline() -> None:
    with pytest.raises(CIRPContractError, match="VERIFIED_AVAILABLE"):
        build_plan(
            remedy_option=remedy(
                status=RemedyAdmissibility.PROVISIONALLY_AVAILABLE
            )
        )

    with pytest.raises(CIRPContractError, match="VERIFIED deadline"):
        build_plan(
            deadline=verified_deadline(DeadlineStatus.PROVISIONAL)
        )


def test_planner_rejects_missing_rule_or_evidence_basis() -> None:
    with pytest.raises(CIRPContractError, match="rule references"):
        build_plan(spec=filing_spec(rule_refs=("rule:wrong",)))

    with pytest.raises(CIRPContractError, match="evidence references"):
        build_plan(spec=filing_spec(evidence_refs=("evidence:wrong",)))


def test_planner_rejects_topology_partition_mismatch() -> None:
    bad_topology = FilingTopologyDecision(
        status=FilingTopologyStatus.MULTIPLE_FILINGS_REQUIRED,
        filing_count=2,
        combined_remedies=(),
        separated_remedies=(REMEDY_ID, "remedy:synthetic:other"),
        rationale="Synthetic split",
        blockers=(),
    )
    with pytest.raises(CIRPContractError, match="filing spec count"):
        FilingPlanner().plan(
            strategy_decision=decision(),
            strategies=(strategy(),),
            topology=bad_topology,
            remedies=(remedy(),),
            deadlines=(verified_deadline(),),
            available_evidence_ids=(EVIDENCE,),
            specs=(filing_spec(),),
        )


def test_hardcore_preflight_can_reach_filing_ready() -> None:
    plan = build_plan()
    result = ready_preflight(plan)

    assert result.final_status is PreflightFinalStatus.FILING_READY
    assert not result.blockers
    assert all(check.status.value == "PASS" for check in result.checks)


@pytest.mark.parametrize(
    ("execution_state", "expected_check"),
    (
        (execution(provided_attachments=()), "attachments"),
        (execution(satisfied_formal_requirements=()), "formal-requirements"),
        (execution(signature_ready=False), "signature"),
        (execution(copies_ready=False), "copies"),
    ),
)
def test_preflight_blocks_incomplete_execution(
    execution_state: FilingExecutionState,
    expected_check: str,
) -> None:
    plan = build_plan()
    result = HardcorePreflight().evaluate(
        plan=plan,
        remedies=(remedy(),),
        deadlines=(verified_deadline(),),
        available_evidence_ids=(EVIDENCE,),
        execution=execution_state,
    )

    assert result.final_status is PreflightFinalStatus.NOT_READY
    assert any(
        item.startswith(expected_check + ":") for item in result.blockers
    )


def test_preflight_abstains_on_critical_unknown() -> None:
    plan = build_plan()
    result = HardcorePreflight().evaluate(
        plan=plan,
        remedies=(remedy(),),
        deadlines=(verified_deadline(),),
        available_evidence_ids=(EVIDENCE,),
        execution=execution(
            critical_unknowns=("UNKNOWN synthetic fact",)
        ),
    )

    assert result.final_status is PreflightFinalStatus.ABSTAIN
    assert any("critical-unknowns" in item for item in result.blockers)


def test_preflight_detects_route_tampering() -> None:
    plan = replace(build_plan(), filing_via="tampered-route")
    result = HardcorePreflight().evaluate(
        plan=plan,
        remedies=(remedy(),),
        deadlines=(verified_deadline(),),
        available_evidence_ids=(EVIDENCE,),
        execution=execution(),
    )

    assert result.final_status is PreflightFinalStatus.NOT_READY
    assert any(
        item.startswith("filing-route:") for item in result.blockers
    )


def test_preflight_abstains_when_deadline_is_unverified() -> None:
    plan = build_plan()
    result = HardcorePreflight().evaluate(
        plan=plan,
        remedies=(remedy(),),
        deadlines=(verified_deadline(DeadlineStatus.PROVISIONAL),),
        available_evidence_ids=(EVIDENCE,),
        execution=execution(),
    )

    assert result.final_status is PreflightFinalStatus.ABSTAIN
    assert any(item.startswith("deadline:") for item in result.blockers)


def test_report_ready_projection_is_deterministic() -> None:
    plan = build_plan()
    preflight = ready_preflight(plan)

    first = build_report(
        evidence_requirements=(evidence_requirement(),),
        plan=plan,
        preflight=preflight,
    )
    second = build_report(
        evidence_requirements=(evidence_requirement(),),
        plan=plan,
        preflight=preflight,
    )

    assert first.status is CIRPReportStatus.READY_TO_FILE
    assert first.canonical_json() == second.canonical_json()
    assert first.digest() == second.digest()


def test_report_exposes_evidence_gap_and_critical_unknown() -> None:
    plan = build_plan()
    preflight = ready_preflight(plan)

    gap = build_report(
        evidence_requirements=(
            evidence_requirement(EvidenceRequirementStatus.MISSING),
        ),
        plan=plan,
        preflight=preflight,
    )
    unknown = build_report(
        evidence_requirements=(evidence_requirement(),),
        plan=plan,
        preflight=preflight,
        critical_unknowns=("UNKNOWN synthetic issue",),
    )

    assert gap.status is CIRPReportStatus.NEEDS_EVIDENCE
    assert gap.evidence_gaps == ("requirement:synthetic:primary",)
    assert unknown.status is CIRPReportStatus.ABSTAIN
    assert unknown.critical_unknowns == ("UNKNOWN synthetic issue",)


def test_report_requires_exact_preflight_coverage() -> None:
    plan = build_plan()
    with pytest.raises(CIRPContractError, match="one preflight"):
        CIRPReportBuilder().build(
            case_id="case:synthetic:1",
            run_id="cirp-run:synthetic:1",
            document_summary="Synthetic notice",
            procedural_summary="Synthetic response stage",
            deadline_summaries=("Synthetic verified deadline",),
            remedy_summaries=("Synthetic verified remedy",),
            evidence_requirements=(evidence_requirement(),),
            strategy_decision=decision(),
            strategy_summary="Synthetic recommended strategy",
            topology=topology(),
            filing_plans=(plan,),
            preflights=(),
        )


def test_ready_report_contract_cannot_hide_critical_unknowns() -> None:
    with pytest.raises(CIRPContractError, match="cannot hide"):
        CIRPReport(
            case_id="case:synthetic:1",
            run_id="cirp-run:synthetic:1",
            document_summary="Synthetic notice",
            procedural_summary="Synthetic response stage",
            deadline_summaries=(),
            remedy_summaries=(),
            evidence_gaps=(),
            strategy_status=StrategyDecisionStatus.RECOMMENDED.value,
            strategy_summary="Synthetic strategy",
            filing_topology_status=(
                FilingTopologyStatus.SINGLE_FILING_SAFE.value
            ),
            filing_ids=(FILING_ID,),
            preflight_statuses=(
                f"{FILING_ID}:{PreflightFinalStatus.FILING_READY.value}",
            ),
            open_questions=(),
            critical_unknowns=("UNKNOWN synthetic issue",),
            status=CIRPReportStatus.READY_TO_FILE,
        )
