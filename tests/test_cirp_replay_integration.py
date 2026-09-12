from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from core.case_ledger.contracts import CaseId
from core.cirp.contracts import (
    CIRPContractError,
    CIRPRunIdentity,
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
from core.cirp.replay import (
    CIRPReplayArtifactRef,
    CIRPReplayComparison,
    CIRPReplayManifest,
    CIRPReplayVerifier,
)
from core.cirp.report import CIRPReport, CIRPReportBuilder, CIRPReportStatus
from core.cirp.strategy import FilingTopologyGuard, StrategyGuard
from core.p3.contracts import ReplayRelation, content_digest

RULE = "rule:synthetic:review@1#" + "a" * 64
EVIDENCE = "evidence:synthetic:primary"
SERVICE_EVIDENCE = "evidence:synthetic:service"
DEADLINE_ID = "deadline:synthetic:review"
REMEDY_ID = "remedy:synthetic:review"
STRATEGY_ID = "strategy:synthetic:review"
FILING_ID = "filing:synthetic:review"
REPORT_ID = "report:synthetic:cirp-v1"


def run_identity(*, policy_identity: str = "policy:synthetic:v1") -> CIRPRunIdentity:
    return CIRPRunIdentity(
        case_id=CaseId("case:synthetic:replay"),
        input_evidence_ids=(EVIDENCE, SERVICE_EVIDENCE),
        input_event_ids=("event:synthetic:intake",),
        rule_pack_ids=("pack:synthetic:v1",),
        rule_pack_digest=content_digest({"pack": "synthetic:v1"}),
        policy_identity=policy_identity,
        runtime_identity="runtime:synthetic:deterministic-core:v1",
        evaluation_time=datetime(
            2030,
            1,
            10,
            12,
            0,
            tzinfo=ZoneInfo("Europe/Warsaw"),
        ),
        configuration_digest=content_digest({"configuration": "synthetic:v1"}),
        model_identity=None,
    )


def remedy() -> RemedyOption:
    return RemedyOption(
        remedy_id=REMEDY_ID,
        remedy_type="SYNTHETIC_REVIEW",
        target_authority="synthetic-target",
        filing_authority="synthetic-filing-authority",
        filing_via="synthetic-route",
        applicable_rule_ids=(RULE,),
        deadline_id=DEADLINE_ID,
        formal_requirements=("formal:synthetic:signature",),
        required_evidence=(EVIDENCE,),
        preserves_options=("option:synthetic",),
        waives_options=(),
        admissibility_status=RemedyAdmissibility.VERIFIED_AVAILABLE,
        blockers=(),
    )


def strategy(*, strategy_id: str = STRATEGY_ID) -> StrategyOption:
    return StrategyOption(
        strategy_id=strategy_id,
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


def deadline() -> DeadlineAssessment:
    return DeadlineAssessment(
        deadline_id=DEADLINE_ID,
        trigger_type="SYNTHETIC_SERVICE",
        trigger_date=date(2030, 1, 10),
        trigger_evidence=SERVICE_EVIDENCE,
        rule_pack_id="pack:synthetic:v1",
        rule_id="deadline-rule:synthetic",
        rule_version="1",
        legal_source_refs=("source:synthetic",),
        effective_law_date=date(2030, 1, 10),
        duration_value=10,
        duration_unit="CALENDAR_DAYS",
        calculation_method="SYNTHETIC",
        calendar_profile="calendar:synthetic",
        timezone="Europe/Warsaw",
        legal_deadline=date(2030, 1, 20),
        safe_internal_deadline=date(2030, 1, 18),
        status=DeadlineStatus.VERIFIED,
        blocking_questions=(),
    )


def evidence_requirement() -> EvidenceRequirement:
    return EvidenceRequirement(
        requirement_id="requirement:synthetic:primary",
        description="Synthetic primary evidence",
        category=EvidenceCategory.MERITS_CRITICAL,
        importance=EvidenceImportance.CRITICAL,
        required_for=(RULE,),
        expected_evidence_kind="SYNTHETIC_DOCUMENT",
        status=EvidenceRequirementStatus.PRESENT,
        evidence_refs=(EVIDENCE,),
    )


def filing_spec() -> FilingSpec:
    return FilingSpec(
        filing_id=FILING_ID,
        filing_type="SYNTHETIC_REVIEW_FILING",
        remedy_ids=(REMEDY_ID,),
        requests=("Grant synthetic review",),
        allegations_or_grounds=("Synthetic verified ground",),
        evidence_refs=(EVIDENCE,),
        rule_refs=(RULE,),
        attachment_requirements=("attachment:synthetic",),
        signature_requirements=("signature:synthetic",),
        copy_requirements=("copy:synthetic",),
        delivery_method="SYNTHETIC_ELECTRONIC",
    )


def execution(*, critical_unknowns: tuple[str, ...] = ()) -> FilingExecutionState:
    return FilingExecutionState(
        filing_id=FILING_ID,
        provided_attachments=("attachment:synthetic",),
        satisfied_formal_requirements=("formal:synthetic:signature",),
        signature_ready=True,
        copies_ready=True,
        critical_unknowns=critical_unknowns,
    )


def build_chain(
    *,
    tamper_route: bool = False,
    critical_unknowns: tuple[str, ...] = (),
) -> tuple[
    StrategyDecision,
    FilingTopologyDecision,
    FilingPlan,
    PreflightResult,
    CIRPReport,
]:
    selected_remedy = remedy()
    selected_strategy = strategy()
    decision = StrategyGuard().decide(
        options=(selected_strategy,),
        remedies=(selected_remedy,),
        available_evidence_ids=(EVIDENCE,),
        decisive_evidence=(EVIDENCE,),
        decisive_rules=(RULE,),
    )
    topology = FilingTopologyGuard().decide(
        strategy=selected_strategy,
        remedies=(selected_remedy,),
    )
    plan = FilingPlanner().plan(
        strategy_decision=decision,
        strategies=(selected_strategy,),
        topology=topology,
        remedies=(selected_remedy,),
        deadlines=(deadline(),),
        available_evidence_ids=(EVIDENCE,),
        specs=(filing_spec(),),
    )[0]
    if tamper_route:
        plan = replace(plan, filing_via="tampered-route")
    preflight = HardcorePreflight().evaluate(
        plan=plan,
        remedies=(selected_remedy,),
        deadlines=(deadline(),),
        available_evidence_ids=(EVIDENCE,),
        execution=execution(critical_unknowns=critical_unknowns),
    )
    report = CIRPReportBuilder().build(
        case_id="case:synthetic:replay",
        run_id="cirp-run:synthetic:replay",
        document_summary="Synthetic notice",
        procedural_summary="Synthetic response stage",
        deadline_summaries=("Synthetic verified deadline",),
        remedy_summaries=("Synthetic verified remedy",),
        evidence_requirements=(evidence_requirement(),),
        strategy_decision=decision,
        strategy_summary="Synthetic recommended strategy",
        topology=topology,
        filing_plans=(plan,),
        preflights=(preflight,),
        critical_unknowns=critical_unknowns,
    )
    return decision, topology, plan, preflight, report


def artifact_ref(artifact_id: str, artifact: object) -> CIRPReplayArtifactRef:
    schema = getattr(artifact, "schema")
    digest = getattr(artifact, "digest")()
    assert isinstance(schema, str)
    assert isinstance(digest, str)
    return CIRPReplayArtifactRef(
        artifact_id=artifact_id,
        schema=schema,
        digest=digest,
    )


def manifest(
    *,
    run: CIRPRunIdentity | None = None,
    tamper_route: bool = False,
    critical_unknowns: tuple[str, ...] = (),
    reverse_artifacts: bool = False,
) -> CIRPReplayManifest:
    decision, topology, plan, preflight, report = build_chain(
        tamper_route=tamper_route,
        critical_unknowns=critical_unknowns,
    )
    artifacts: tuple[CIRPReplayArtifactRef, ...] = (
        artifact_ref("strategy-decision", decision),
        artifact_ref("filing-topology", topology),
        artifact_ref("filing-plan", plan),
        artifact_ref("preflight", preflight),
        artifact_ref(REPORT_ID, report),
    )
    if reverse_artifacts:
        artifacts = tuple(reversed(artifacts))
    return CIRPReplayManifest.build(
        run_identity=run or run_identity(),
        artifacts=artifacts,
        report_artifact_id=REPORT_ID,
    )


def test_full_synthetic_chain_reaches_ready_and_exact_replay() -> None:
    _, topology, _, preflight, report = build_chain()
    expected = manifest()
    actual = manifest(reverse_artifacts=True)
    comparison = CIRPReplayVerifier.compare(expected, actual)

    assert topology.status is FilingTopologyStatus.SINGLE_FILING_SAFE
    assert preflight.final_status is PreflightFinalStatus.FILING_READY
    assert report.status is CIRPReportStatus.READY_TO_FILE
    assert comparison.relation is ReplayRelation.IDENTICAL
    assert comparison.expected_manifest_digest == comparison.actual_manifest_digest


def test_manifest_order_is_canonical_and_deterministic() -> None:
    forward = manifest()
    reverse = manifest(reverse_artifacts=True)

    assert tuple(item.artifact_id for item in forward.artifacts) == tuple(
        sorted(item.artifact_id for item in forward.artifacts)
    )
    assert forward.canonical_dict() == reverse.canonical_dict()
    assert forward.digest() == reverse.digest()


def test_manifest_rejects_duplicate_artifact_identity() -> None:
    ready = manifest()
    duplicate = ready.artifacts[0]

    with pytest.raises(CIRPContractError, match="duplicate artifact_id"):
        CIRPReplayManifest(
            run_identity_digest=ready.run_identity_digest,
            artifacts=(*ready.artifacts, duplicate),
            report_artifact_id=REPORT_ID,
        )


def test_manifest_requires_exact_report_artifact() -> None:
    ready = manifest()
    non_report_artifacts = tuple(
        item for item in ready.artifacts if item.artifact_id != REPORT_ID
    )

    with pytest.raises(CIRPContractError, match="report_artifact_id"):
        CIRPReplayManifest(
            run_identity_digest=ready.run_identity_digest,
            artifacts=non_report_artifacts,
            report_artifact_id=REPORT_ID,
        )


def test_missing_or_unexpected_artifact_fails_closed_as_incomplete() -> None:
    expected = manifest()
    reduced = tuple(
        item
        for item in expected.artifacts
        if item.artifact_id != "strategy-decision"
    )
    actual = CIRPReplayManifest(
        run_identity_digest=expected.run_identity_digest,
        artifacts=reduced,
        report_artifact_id=REPORT_ID,
    )
    missing = CIRPReplayVerifier.compare(expected, actual)

    extra_ref = CIRPReplayArtifactRef(
        artifact_id="unexpected-artifact",
        schema="lukart.cirp.synthetic-extra.v1",
        digest=content_digest({"extra": True}),
    )
    expanded = CIRPReplayManifest(
        run_identity_digest=expected.run_identity_digest,
        artifacts=(*expected.artifacts, extra_ref),
        report_artifact_id=REPORT_ID,
    )
    unexpected = CIRPReplayVerifier.compare(expected, expanded)

    assert missing.relation is ReplayRelation.INCOMPLETE
    assert missing.missing_artifact_ids == ("strategy-decision",)
    assert unexpected.relation is ReplayRelation.INCOMPLETE
    assert unexpected.unexpected_artifact_ids == ("unexpected-artifact",)


def test_artifact_digest_tampering_is_detected_as_different() -> None:
    expected = manifest()
    tampered_artifacts = tuple(
        replace(item, digest=content_digest({"tampered": item.artifact_id}))
        if item.artifact_id == "filing-plan"
        else item
        for item in expected.artifacts
    )
    actual = CIRPReplayManifest(
        run_identity_digest=expected.run_identity_digest,
        artifacts=tampered_artifacts,
        report_artifact_id=REPORT_ID,
    )
    comparison = CIRPReplayVerifier.compare(expected, actual)

    assert comparison.relation is ReplayRelation.DIFFERENT
    assert comparison.mismatched_artifact_ids == ("filing-plan",)


def test_changed_run_identity_is_never_reported_identical() -> None:
    expected = manifest()
    actual = manifest(run=run_identity(policy_identity="policy:synthetic:v2"))
    comparison = CIRPReplayVerifier.compare(expected, actual)

    assert comparison.relation is ReplayRelation.DIFFERENT
    assert not comparison.run_identity_match
    assert not comparison.mismatched_artifact_ids


def test_route_tampering_propagates_not_ready_and_changes_replay() -> None:
    _, _, _, preflight, report = build_chain(tamper_route=True)
    expected = manifest()
    actual = manifest(tamper_route=True)
    comparison = CIRPReplayVerifier.compare(expected, actual)

    assert preflight.final_status is PreflightFinalStatus.NOT_READY
    assert report.status is CIRPReportStatus.NOT_READY
    assert comparison.relation is ReplayRelation.DIFFERENT
    assert set(comparison.mismatched_artifact_ids) == {
        "filing-plan",
        "preflight",
        REPORT_ID,
    }


def test_critical_unknown_propagates_abstain_and_changes_replay() -> None:
    unknowns = ("UNKNOWN synthetic material fact",)
    _, _, _, preflight, report = build_chain(critical_unknowns=unknowns)
    expected = manifest()
    actual = manifest(critical_unknowns=unknowns)
    comparison = CIRPReplayVerifier.compare(expected, actual)

    assert preflight.final_status is PreflightFinalStatus.ABSTAIN
    assert report.status is CIRPReportStatus.ABSTAIN
    assert comparison.relation is ReplayRelation.DIFFERENT
    assert "preflight" in comparison.mismatched_artifact_ids
    assert REPORT_ID in comparison.mismatched_artifact_ids


def test_multiple_safe_strategies_stop_before_filing_planning() -> None:
    first = strategy(strategy_id="strategy:synthetic:first")
    second = strategy(strategy_id="strategy:synthetic:second")
    selected_remedy = remedy()
    decision = StrategyGuard().decide(
        options=(first, second),
        remedies=(selected_remedy,),
        available_evidence_ids=(EVIDENCE,),
        decisive_evidence=(EVIDENCE,),
        decisive_rules=(RULE,),
    )
    topology = FilingTopologyGuard().decide(
        strategy=first,
        remedies=(selected_remedy,),
    )

    assert decision.decision_status is StrategyDecisionStatus.DECISION_REQUIRED
    with pytest.raises(CIRPContractError, match="RECOMMENDED"):
        FilingPlanner().plan(
            strategy_decision=decision,
            strategies=(first, second),
            topology=topology,
            remedies=(selected_remedy,),
            deadlines=(deadline(),),
            available_evidence_ids=(EVIDENCE,),
            specs=(filing_spec(),),
        )


def test_cross_version_comparable_requires_future_explicit_contract() -> None:
    ready = manifest()
    with pytest.raises(CIRPContractError, match="cross-version"):
        CIRPReplayComparison(
            relation=ReplayRelation.CROSS_VERSION_COMPARABLE,
            expected_manifest_digest=ready.digest(),
            actual_manifest_digest=ready.digest(),
            run_identity_match=True,
            missing_artifact_ids=(),
            unexpected_artifact_ids=(),
            mismatched_artifact_ids=(),
            report_identity_match=True,
        )
