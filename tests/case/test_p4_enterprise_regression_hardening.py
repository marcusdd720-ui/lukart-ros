from datetime import UTC, date, datetime

import pytest

from core.cirp.contracts import (
    CIRPContractError,
    DeadlineStatus,
    FilingPlan,
    FilingTopologyDecision,
    FilingTopologyStatus,
    LegalSourceRef,
    LegalSourceVerificationStatus,
    PreflightFinalStatus,
    ProceduralRulePack,
    RemedyAdmissibility,
    RemedyOption,
    RulePackStatus,
)
from core.cirp.deadline import (
    DeadlineCalendarProfile,
    DeadlineDurationUnit,
    DeadlineGuard,
    DeadlineRollConvention,
    DeadlineStartRule,
    DeadlineTriggerStatus,
    ExecutableDeadlineRule,
)
from core.cirp.operational_guards import (
    ArtifactLifecycleStatus,
    LifecycleTransitionEvidence,
    RedTeamFinding,
    RedTeamFindingStatus,
    RendererSemanticInput,
    RendererSemanticOutput,
    append_lifecycle_transition,
    assert_legal_effect_claim,
    assert_public_surface_canary_clean,
    begin_reopened_run,
    red_team_downstream_status,
    validate_lifecycle_transition,
    validate_renderer_boundary,
)
from core.cirp.preflight import FilingExecutionState, HardcorePreflight


def _send_ready_evidence() -> LifecycleTransitionEvidence:
    return LifecycleTransitionEvidence(
        preflight_status=PreflightFinalStatus.FILING_READY,
        authority_verified=True,
        filing_route_verified=True,
        no_material_unknowns=True,
    )


def _transition_evidence_for(
    target: ArtifactLifecycleStatus,
) -> LifecycleTransitionEvidence:
    if target is ArtifactLifecycleStatus.PREFLIGHTED:
        return LifecycleTransitionEvidence(preflight_executed=True)
    if target is ArtifactLifecycleStatus.SEND_READY:
        return _send_ready_evidence()
    if target is ArtifactLifecycleStatus.APPROVED:
        return LifecycleTransitionEvidence(explicit_user_authorization=True)
    if target is ArtifactLifecycleStatus.SENT_FILED:
        return LifecycleTransitionEvidence(external_action_receipt_verified=True)
    if target is ArtifactLifecycleStatus.RECEIVED_DELIVERED:
        return LifecycleTransitionEvidence(delivery_proof_verified=True)
    if target is ArtifactLifecycleStatus.RESPONDED:
        return LifecycleTransitionEvidence(response_evidence_verified=True)
    if target is ArtifactLifecycleStatus.ASSESSED:
        return LifecycleTransitionEvidence(assessment_recorded=True)
    if target is ArtifactLifecycleStatus.CLOSED_ARCHIVED:
        return LifecycleTransitionEvidence(closure_recorded=True)
    return LifecycleTransitionEvidence()


def test_p4_a_full_lifecycle_requires_each_evidence_gated_edge() -> None:
    history: tuple[ArtifactLifecycleStatus, ...] = (ArtifactLifecycleStatus.DRAFT,)
    history = append_lifecycle_transition(
        history,
        ArtifactLifecycleStatus.PREFLIGHTED,
        LifecycleTransitionEvidence(preflight_executed=True),
    )
    history = append_lifecycle_transition(
        history,
        ArtifactLifecycleStatus.SEND_READY,
        _send_ready_evidence(),
    )
    history = append_lifecycle_transition(
        history,
        ArtifactLifecycleStatus.APPROVED,
        LifecycleTransitionEvidence(explicit_user_authorization=True),
    )
    history = append_lifecycle_transition(
        history,
        ArtifactLifecycleStatus.SENT_FILED,
        LifecycleTransitionEvidence(external_action_receipt_verified=True),
    )
    history = append_lifecycle_transition(
        history,
        ArtifactLifecycleStatus.RECEIVED_DELIVERED,
        LifecycleTransitionEvidence(delivery_proof_verified=True),
    )
    history = append_lifecycle_transition(
        history,
        ArtifactLifecycleStatus.RESPONDED,
        LifecycleTransitionEvidence(response_evidence_verified=True),
    )
    history = append_lifecycle_transition(
        history,
        ArtifactLifecycleStatus.ASSESSED,
        LifecycleTransitionEvidence(assessment_recorded=True),
    )
    history = append_lifecycle_transition(
        history,
        ArtifactLifecycleStatus.CLOSED_ARCHIVED,
        LifecycleTransitionEvidence(closure_recorded=True),
    )
    assert history == tuple(ArtifactLifecycleStatus)


def test_p4_a_complete_transition_matrix_allows_only_adjacent_edges() -> None:
    states = tuple(ArtifactLifecycleStatus)
    allowed = set(zip(states[:-1], states[1:], strict=True))
    assert len(states) == 9
    assert len(allowed) == 8

    evaluated = 0
    for current in states:
        for target in states:
            evaluated += 1
            evidence = _transition_evidence_for(target)
            if (current, target) in allowed:
                validate_lifecycle_transition(current, target, evidence)
            else:
                with pytest.raises(CIRPContractError):
                    validate_lifecycle_transition(current, target, evidence)
    assert evaluated == 81


@pytest.mark.parametrize(
    ("current", "target", "evidence", "message"),
    (
        (
            ArtifactLifecycleStatus.DRAFT,
            ArtifactLifecycleStatus.SEND_READY,
            _send_ready_evidence(),
            "invalid lifecycle transition",
        ),
        (
            ArtifactLifecycleStatus.DRAFT,
            ArtifactLifecycleStatus.SENT_FILED,
            LifecycleTransitionEvidence(external_action_receipt_verified=True),
            "invalid lifecycle transition",
        ),
        (
            ArtifactLifecycleStatus.PREFLIGHTED,
            ArtifactLifecycleStatus.SENT_FILED,
            LifecycleTransitionEvidence(external_action_receipt_verified=True),
            "invalid lifecycle transition",
        ),
        (
            ArtifactLifecycleStatus.PREFLIGHTED,
            ArtifactLifecycleStatus.SEND_READY,
            LifecycleTransitionEvidence(
                preflight_status=PreflightFinalStatus.NOT_READY,
                authority_verified=True,
                filing_route_verified=True,
                no_material_unknowns=True,
            ),
            "FILING_READY",
        ),
        (
            ArtifactLifecycleStatus.PREFLIGHTED,
            ArtifactLifecycleStatus.SEND_READY,
            LifecycleTransitionEvidence(
                preflight_status=PreflightFinalStatus.ABSTAIN,
                authority_verified=True,
                filing_route_verified=True,
                no_material_unknowns=False,
            ),
            "FILING_READY",
        ),
        (
            ArtifactLifecycleStatus.SEND_READY,
            ArtifactLifecycleStatus.APPROVED,
            LifecycleTransitionEvidence(),
            "explicit user authorization",
        ),
        (
            ArtifactLifecycleStatus.APPROVED,
            ArtifactLifecycleStatus.SENT_FILED,
            LifecycleTransitionEvidence(),
            "external-action evidence",
        ),
        (
            ArtifactLifecycleStatus.SENT_FILED,
            ArtifactLifecycleStatus.RECEIVED_DELIVERED,
            LifecycleTransitionEvidence(),
            "delivery proof",
        ),
        (
            ArtifactLifecycleStatus.RECEIVED_DELIVERED,
            ArtifactLifecycleStatus.RESPONDED,
            LifecycleTransitionEvidence(),
            "response evidence",
        ),
    ),
)
def test_p4_a_forbidden_lifecycle_transitions_fail_closed(
    current: ArtifactLifecycleStatus,
    target: ArtifactLifecycleStatus,
    evidence: LifecycleTransitionEvidence,
    message: str,
) -> None:
    with pytest.raises(CIRPContractError, match=message):
        validate_lifecycle_transition(current, target, evidence)


def test_p4_a_delivery_does_not_imply_legal_effect() -> None:
    with pytest.raises(CIRPContractError, match="legal effect"):
        assert_legal_effect_claim(legal_effect_verified=False)
    assert_legal_effect_claim(legal_effect_verified=True)


def _deadline_guard(
    *,
    source_verification: LegalSourceVerificationStatus = LegalSourceVerificationStatus.VERIFIED,
    source_effective_until: date | None = None,
    rule_effective_until: date | None = None,
    pack_status: RulePackStatus = RulePackStatus.ACTIVE,
) -> tuple[DeadlineGuard, ExecutableDeadlineRule]:
    source = LegalSourceRef(
        source_id="SYN-SOURCE-1",
        jurisdiction="SYNTHETIC",
        authority_type="SYNTHETIC-STATUTE",
        formal_citation="SYN-1",
        source_uri="https://example.invalid/synthetic-source",
        source_digest=(
            "a" * 64
            if source_verification is LegalSourceVerificationStatus.VERIFIED
            else None
        ),
        effective_from=date(2026, 1, 1),
        effective_until=source_effective_until,
        retrieved_at=datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
        verification_status=source_verification,
    )
    calendar = DeadlineCalendarProfile(
        profile_id="SYN-CALENDAR-1",
        timezone="Europe/Warsaw",
        legal_source_ids=(source.source_id,),
    )
    rule = ExecutableDeadlineRule.build(
        rule_id="SYN-DEADLINE-RULE",
        version="1",
        trigger_type="SERVICE",
        duration_value=14,
        duration_unit=DeadlineDurationUnit.CALENDAR_DAYS,
        start_rule=DeadlineStartRule.EXCLUDE_TRIGGER,
        roll_convention=DeadlineRollConvention.NEXT_BUSINESS_DAY,
        calendar_profile=calendar,
        legal_source_ids=(source.source_id,),
        effective_from=date(2026, 1, 1),
        effective_until=rule_effective_until,
    )
    pack = ProceduralRulePack.build(
        pack_id="SYN-PACK-1",
        version="1",
        jurisdiction="SYNTHETIC",
        procedure_family="SYNTHETIC-PROCEDURE",
        effective_from=date(2026, 1, 1),
        effective_until=None,
        source_set=(source,),
        deadline_rules=(rule.pack_token,),
        status=pack_status,
    )
    return DeadlineGuard(rule_pack=pack, rules=(rule,), calendars=(calendar,)), rule


def _evaluate_deadline(
    guard: DeadlineGuard,
    rule: ExecutableDeadlineRule,
    *,
    trigger_date: date | None = date(2026, 9, 1),
    trigger_evidence: str | None = "SYN-EVIDENCE-SERVICE-1",
    trigger_status: DeadlineTriggerStatus = DeadlineTriggerStatus.VERIFIED,
    effective_law_date: date | None = date(2026, 9, 1),
):
    return guard.evaluate(
        deadline_id="SYN-DEADLINE-1",
        rule_key=rule.key,
        trigger_type="SERVICE",
        trigger_date=trigger_date,
        trigger_evidence=trigger_evidence,
        trigger_status=trigger_status,
        effective_law_date=effective_law_date,
        evaluation_time=datetime(2026, 9, 2, 9, 0, tzinfo=UTC),
        safe_buffer_business_days=2,
    )


def test_p4_b_deadline_missing_or_conflicting_trigger_never_verifies() -> None:
    guard, rule = _deadline_guard()
    missing = _evaluate_deadline(
        guard,
        rule,
        trigger_date=None,
        trigger_evidence=None,
        trigger_status=DeadlineTriggerStatus.MISSING,
    )
    conflicting = _evaluate_deadline(
        guard,
        rule,
        trigger_date=None,
        trigger_evidence=None,
        trigger_status=DeadlineTriggerStatus.CONFLICTING,
    )
    assert missing.status is DeadlineStatus.MISSING_INPUT
    assert conflicting.status is DeadlineStatus.CONFLICTING_EVIDENCE
    assert missing.legal_deadline is None
    assert conflicting.legal_deadline is None


def test_p4_b_verified_trigger_without_evidence_cannot_produce_verified_deadline() -> None:
    guard, rule = _deadline_guard()
    result = _evaluate_deadline(
        guard,
        rule,
        trigger_date=date(2026, 9, 4),
        trigger_evidence=None,
        trigger_status=DeadlineTriggerStatus.VERIFIED,
    )
    assert result.status is DeadlineStatus.MISSING_INPUT
    assert result.legal_deadline is None
    assert result.safe_internal_deadline is None


def test_p4_b_missing_effective_law_date_cannot_produce_verified_deadline() -> None:
    guard, rule = _deadline_guard()
    result = _evaluate_deadline(guard, rule, effective_law_date=None)
    assert result.status is DeadlineStatus.MISSING_INPUT
    assert result.legal_deadline is None


def test_p4_b_unknown_rule_and_ineffective_source_fail_closed() -> None:
    guard, rule = _deadline_guard()
    unknown = guard.evaluate(
        deadline_id="SYN-DEADLINE-UNKNOWN",
        rule_key="MISSING-RULE@1",
        trigger_type="SERVICE",
        trigger_date=date(2026, 9, 1),
        trigger_evidence="SYN-EVIDENCE-SERVICE-1",
        trigger_status=DeadlineTriggerStatus.VERIFIED,
        effective_law_date=date(2026, 9, 1),
        evaluation_time=datetime(2026, 9, 2, 9, 0, tzinfo=UTC),
    )
    stale_guard, stale_rule = _deadline_guard(source_effective_until=date(2026, 8, 31))
    stale = _evaluate_deadline(stale_guard, stale_rule)
    assert unknown.status is DeadlineStatus.UNKNOWN_RULE
    assert stale.status is DeadlineStatus.UNKNOWN_RULE


def test_p4_b_stale_rule_and_unverified_source_fail_closed() -> None:
    stale_guard, stale_rule = _deadline_guard(rule_effective_until=date(2026, 8, 31))
    stale = _evaluate_deadline(stale_guard, stale_rule)
    unverified_guard, unverified_rule = _deadline_guard(
        source_verification=LegalSourceVerificationStatus.PROVISIONAL
    )
    unverified = _evaluate_deadline(unverified_guard, unverified_rule)
    assert stale.status is DeadlineStatus.UNKNOWN_RULE
    assert unverified.status is DeadlineStatus.UNKNOWN_RULE
    assert stale.legal_deadline is None
    assert unverified.legal_deadline is None


def test_p4_b_calendar_digest_mismatch_is_rejected() -> None:
    source = LegalSourceRef(
        source_id="SYN-SOURCE-CALENDAR",
        jurisdiction="SYNTHETIC",
        authority_type="SYNTHETIC-STATUTE",
        formal_citation="SYN-CALENDAR-1",
        source_uri="https://example.invalid/synthetic-calendar-source",
        source_digest="b" * 64,
        effective_from=date(2026, 1, 1),
        effective_until=None,
        retrieved_at=datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
        verification_status=LegalSourceVerificationStatus.VERIFIED,
    )
    bound_calendar = DeadlineCalendarProfile(
        profile_id="SYN-CALENDAR-BOUND",
        timezone="Europe/Warsaw",
        legal_source_ids=(source.source_id,),
    )
    rule = ExecutableDeadlineRule.build(
        rule_id="SYN-CALENDAR-RULE",
        version="1",
        trigger_type="SERVICE",
        duration_value=14,
        duration_unit=DeadlineDurationUnit.CALENDAR_DAYS,
        start_rule=DeadlineStartRule.EXCLUDE_TRIGGER,
        roll_convention=DeadlineRollConvention.NEXT_BUSINESS_DAY,
        calendar_profile=bound_calendar,
        legal_source_ids=(source.source_id,),
        effective_from=date(2026, 1, 1),
    )
    pack = ProceduralRulePack.build(
        pack_id="SYN-CALENDAR-PACK",
        version="1",
        jurisdiction="SYNTHETIC",
        procedure_family="SYNTHETIC-PROCEDURE",
        effective_from=date(2026, 1, 1),
        effective_until=None,
        source_set=(source,),
        deadline_rules=(rule.pack_token,),
        status=RulePackStatus.ACTIVE,
    )
    drifted_calendar = DeadlineCalendarProfile(
        profile_id=bound_calendar.profile_id,
        timezone=bound_calendar.timezone,
        holidays=(date(2026, 9, 15),),
        legal_source_ids=bound_calendar.legal_source_ids,
    )
    with pytest.raises(CIRPContractError, match="calendar profile digest mismatch"):
        DeadlineGuard(
            rule_pack=pack,
            rules=(rule,),
            calendars=(drifted_calendar,),
        )


def test_p4_b_inactive_pack_and_bad_timezone_are_rejected() -> None:
    with pytest.raises(CIRPContractError, match="ACTIVE"):
        _deadline_guard(pack_status=RulePackStatus.RETIRED)
    with pytest.raises(CIRPContractError, match="timezone"):
        DeadlineCalendarProfile(profile_id="SYN-BAD-CALENDAR", timezone="Not/A-Timezone")


def test_p4_b_document_date_is_not_service_trigger_date() -> None:
    guard, rule = _deadline_guard()
    document_date = date(2026, 9, 1)
    service_date = date(2026, 9, 4)
    from_service = _evaluate_deadline(guard, rule, trigger_date=service_date)
    from_document = _evaluate_deadline(guard, rule, trigger_date=document_date)
    assert document_date != service_date
    assert from_service.trigger_type == "SERVICE"
    assert from_service.trigger_date == service_date
    assert from_service.legal_deadline != from_document.legal_deadline


def test_p4_b_safe_internal_deadline_never_exceeds_legal_and_trigger_change_changes_result(
) -> None:
    guard, rule = _deadline_guard()
    first = _evaluate_deadline(guard, rule, trigger_date=date(2026, 9, 1))
    second = _evaluate_deadline(guard, rule, trigger_date=date(2026, 9, 2))
    assert first.status in {DeadlineStatus.VERIFIED, DeadlineStatus.EXPIRED}
    assert first.safe_internal_deadline is not None
    assert first.legal_deadline is not None
    assert first.safe_internal_deadline <= first.legal_deadline
    assert first.digest() != second.digest()
    assert first.legal_deadline != second.legal_deadline


def _remedy(
    *,
    target_authority: str = "SYN-REVIEW-AUTHORITY",
    filing_authority: str = "SYN-FILING-AUTHORITY",
    filing_via: str | None = "SYN-FILING-AUTHORITY",
    applicable_rule_ids: tuple[str, ...] = ("SYN-RULE-1",),
    deadline_id: str | None = None,
) -> RemedyOption:
    return RemedyOption(
        remedy_id="SYN-REMEDY-1",
        remedy_type="SYNTHETIC-REVIEW",
        target_authority=target_authority,
        filing_authority=filing_authority,
        filing_via=filing_via,
        applicable_rule_ids=applicable_rule_ids,
        deadline_id=deadline_id,
        formal_requirements=(),
        required_evidence=(),
        preserves_options=(),
        waives_options=(),
        admissibility_status=RemedyAdmissibility.VERIFIED_AVAILABLE,
        blockers=(),
    )


def _plan(
    *,
    target_authority: str = "SYN-REVIEW-AUTHORITY",
    filing_authority: str = "SYN-FILING-AUTHORITY",
    filing_via: str | None = "SYN-FILING-AUTHORITY",
    topology: FilingTopologyStatus = FilingTopologyStatus.SINGLE_FILING_SAFE,
    signature_requirements: tuple[str, ...] = (),
    rule_refs: tuple[str, ...] = ("SYN-RULE-1",),
    deadline_id: str | None = None,
    delivery_method: str = "SYNTHETIC-CHANNEL",
) -> FilingPlan:
    return FilingPlan(
        filing_id="SYN-FILING-1",
        filing_type="SYNTHETIC-REVIEW",
        target_authority=target_authority,
        filing_authority=filing_authority,
        filing_via=filing_via,
        objective="Exercise synthetic review route",
        requests=("Synthetic request",),
        allegations_or_grounds=("Synthetic ground",),
        remedy_ids=("SYN-REMEDY-1",),
        rule_refs=rule_refs,
        evidence_refs=(),
        attachment_requirements=(),
        signature_requirements=signature_requirements,
        copy_requirements=(),
        deadline_id=deadline_id,
        delivery_method=delivery_method,
        topology_status=topology,
    )


def _preflight(
    plan: FilingPlan,
    execution: FilingExecutionState,
    *,
    remedy: RemedyOption | None = None,
    deadlines=(),
):
    selected_remedy = remedy if remedy is not None else _remedy()
    return HardcorePreflight().evaluate(
        plan=plan,
        remedies=(selected_remedy,),
        deadlines=deadlines,
        available_evidence_ids=(),
        execution=execution,
    )


def test_p4_c_authority_unknown_and_wrong_signer_block_readiness() -> None:
    unknown = _preflight(
        _plan(),
        FilingExecutionState(
            filing_id="SYN-FILING-1",
            critical_unknowns=("authority representation is UNKNOWN",),
        ),
    )
    wrong_signer = _preflight(
        _plan(signature_requirements=("AUTHORIZED-SIGNER",)),
        FilingExecutionState(filing_id="SYN-FILING-1", signature_ready=False),
    )
    assert unknown.final_status is PreflightFinalStatus.ABSTAIN
    assert wrong_signer.final_status is PreflightFinalStatus.NOT_READY


@pytest.mark.parametrize("authority_state", ("MISSING", "INVALID", "REVOKED"))
def test_p4_c_unverified_authority_state_blocks_send_ready(authority_state: str) -> None:
    assert authority_state in {"MISSING", "INVALID", "REVOKED"}
    evidence = LifecycleTransitionEvidence(
        preflight_status=PreflightFinalStatus.FILING_READY,
        authority_verified=False,
        filing_route_verified=True,
        no_material_unknowns=True,
    )
    with pytest.raises(CIRPContractError, match="verified authority"):
        validate_lifecycle_transition(
            ArtifactLifecycleStatus.PREFLIGHTED,
            ArtifactLifecycleStatus.SEND_READY,
            evidence,
        )


def test_p4_c_missing_required_rule_basis_is_rejected_by_contract() -> None:
    with pytest.raises(CIRPContractError, match="rule_refs"):
        _plan(rule_refs=())


def test_p4_c_verified_authority_path_can_reach_filing_ready() -> None:
    result = _preflight(
        _plan(signature_requirements=("AUTHORIZED-SIGNER",)),
        FilingExecutionState(filing_id="SYN-FILING-1", signature_ready=True),
    )
    assert result.final_status is PreflightFinalStatus.FILING_READY
    validate_lifecycle_transition(
        ArtifactLifecycleStatus.PREFLIGHTED,
        ArtifactLifecycleStatus.SEND_READY,
        _send_ready_evidence(),
    )


def test_p4_d_wrong_direct_route_and_uncertain_consolidation_fail_closed() -> None:
    wrong_route = _preflight(
        _plan(
            filing_authority="SYN-REVIEW-AUTHORITY",
            filing_via=None,
        ),
        FilingExecutionState(filing_id="SYN-FILING-1"),
    )
    uncertain = _preflight(
        _plan(topology=FilingTopologyStatus.CONSOLIDATION_UNCERTAIN),
        FilingExecutionState(filing_id="SYN-FILING-1"),
    )
    assert wrong_route.final_status is PreflightFinalStatus.NOT_READY
    assert uncertain.final_status is PreflightFinalStatus.NOT_READY


def test_p4_d_wrong_filing_via_and_deadline_identity_fail_closed() -> None:
    wrong_via = _preflight(
        _plan(filing_via="SYN-REVIEW-AUTHORITY"),
        FilingExecutionState(filing_id="SYN-FILING-1"),
    )
    deadline_mismatch = _preflight(
        _plan(deadline_id=None),
        FilingExecutionState(filing_id="SYN-FILING-1"),
        remedy=_remedy(deadline_id="SYN-DEADLINE-REQUIRED"),
    )
    assert wrong_via.final_status is PreflightFinalStatus.NOT_READY
    assert deadline_mismatch.final_status is PreflightFinalStatus.NOT_READY
    assert any(blocker.startswith("filing-route:") for blocker in wrong_via.blockers)
    assert any(blocker.startswith("deadline:") for blocker in deadline_mismatch.blockers)


def test_p4_d_missing_required_deadline_assessment_abstains() -> None:
    result = _preflight(
        _plan(deadline_id="SYN-DEADLINE-REQUIRED"),
        FilingExecutionState(filing_id="SYN-FILING-1"),
        remedy=_remedy(deadline_id="SYN-DEADLINE-REQUIRED"),
    )
    assert result.final_status is PreflightFinalStatus.ABSTAIN
    assert any(blocker.startswith("deadline:") for blocker in result.blockers)


def test_p4_d_delivery_channel_must_be_explicit() -> None:
    with pytest.raises(CIRPContractError, match="delivery_method"):
        _plan(delivery_method="")


def test_p4_d_topology_contract_distinguishes_single_multiple_and_uncertain() -> None:
    single = FilingTopologyDecision(
        status=FilingTopologyStatus.SINGLE_FILING_SAFE,
        filing_count=1,
        combined_remedies=("SYN-REMEDY-1",),
        separated_remedies=(),
        rationale="Synthetic single filing is verified safe.",
        blockers=(),
    )
    multiple = FilingTopologyDecision(
        status=FilingTopologyStatus.MULTIPLE_FILINGS_REQUIRED,
        filing_count=2,
        combined_remedies=(),
        separated_remedies=("SYN-REMEDY-1", "SYN-REMEDY-2"),
        rationale="Synthetic remedies require distinct filings.",
        blockers=(),
    )
    uncertain = FilingTopologyDecision(
        status=FilingTopologyStatus.CONSOLIDATION_UNCERTAIN,
        filing_count=1,
        combined_remedies=(),
        separated_remedies=("SYN-REMEDY-1",),
        rationale="Synthetic consolidation cannot be verified.",
        blockers=("Resolve consolidation authority.",),
    )
    assert single.status is FilingTopologyStatus.SINGLE_FILING_SAFE
    assert multiple.filing_count == 2
    assert uncertain.blockers


def _closed_history() -> tuple[ArtifactLifecycleStatus, ...]:
    return tuple(ArtifactLifecycleStatus)


def test_p4_e_closed_case_requires_new_material_evidence_for_new_run_without_history_rewrite(
) -> None:
    closed = _closed_history()
    with pytest.raises(CIRPContractError, match="new material evidence"):
        begin_reopened_run(closed, material_evidence_ids=())
    reopened = begin_reopened_run(closed, material_evidence_ids=("SYN-EVIDENCE-NEW-1",))
    assert reopened == (ArtifactLifecycleStatus.DRAFT,)
    assert closed == _closed_history()
    with pytest.raises(CIRPContractError, match="closed lifecycle history"):
        append_lifecycle_transition(
            closed,
            ArtifactLifecycleStatus.DRAFT,
            LifecycleTransitionEvidence(),
        )


def _renderer_input() -> RendererSemanticInput:
    return RendererSemanticInput(
        semantic_digest="1" * 64,
        filing_plan_digest="2" * 64,
        strategy_digest="3" * 64,
        evidence_digest="4" * 64,
        unresolved_markers=("UNKNOWN-SYN-1",),
    )


def test_p4_f_renderer_allows_presentation_only_diff_but_no_semantic_change() -> None:
    source = _renderer_input()
    rendered = RendererSemanticOutput(
        semantic_digest=source.semantic_digest,
        filing_plan_digest=source.filing_plan_digest,
        strategy_digest=source.strategy_digest,
        evidence_digest=source.evidence_digest,
        unresolved_markers=source.unresolved_markers,
        presentation_digest="5" * 64,
    )
    validate_renderer_boundary(source, rendered, send_ready=False)


@pytest.mark.parametrize(
    "rendered",
    (
        RendererSemanticOutput(
            semantic_digest="9" * 64,
            filing_plan_digest="2" * 64,
            strategy_digest="3" * 64,
            evidence_digest="4" * 64,
            unresolved_markers=("UNKNOWN-SYN-1",),
        ),
        RendererSemanticOutput(
            semantic_digest="1" * 64,
            filing_plan_digest="2" * 64,
            strategy_digest="3" * 64,
            evidence_digest="4" * 64,
            unresolved_markers=("UNKNOWN-SYN-1",),
            invented_fields=("synthetic-personal-identifier",),
        ),
        RendererSemanticOutput(
            semantic_digest="1" * 64,
            filing_plan_digest="2" * 64,
            strategy_digest="3" * 64,
            evidence_digest="4" * 64,
            unresolved_markers=(),
        ),
        RendererSemanticOutput(
            semantic_digest="1" * 64,
            filing_plan_digest="2" * 64,
            strategy_digest="3" * 64,
            evidence_digest="4" * 64,
            unresolved_markers=("UNKNOWN-SYN-1",),
            critical_placeholders=("SYN-PLACEHOLDER-ADDRESS",),
        ),
    ),
)
def test_p4_f_renderer_truth_boundary_fails_closed(rendered: RendererSemanticOutput) -> None:
    with pytest.raises(CIRPContractError):
        validate_renderer_boundary(_renderer_input(), rendered, send_ready=True)


def test_p4_g_private_canary_cannot_reach_branch_commit_ci_or_public_fixture() -> None:
    canary = "SYN-PRIVATE-CANARY-7F31"
    public_surfaces = (
        "case-testy/p4-safe-branch",
        "case-testy: synthetic regression",
        "CI PASS: synthetic-only",
        "fixture: synthetic-public-value",
    )
    assert_public_surface_canary_clean(
        private_canaries=(canary,),
        public_values=public_surfaces,
    )
    for index in range(len(public_surfaces)):
        leaked = list(public_surfaces)
        leaked[index] += f"::{canary}"
        with pytest.raises(CIRPContractError, match="canary leaked"):
            assert_public_surface_canary_clean(
                private_canaries=(canary,),
                public_values=tuple(leaked),
            )


@pytest.mark.parametrize(
    "finding_id",
    (
        "unsupported-fact",
        "missing-attachment",
        "stale-or-unknown-rule",
        "missing-authority",
        "wrong-filing-route",
        "hidden-contradiction",
        "premature-legal-conclusion",
        "privacy-leak",
        "outside-recipient-competence",
    ),
)
def test_p4_h_red_team_fail_propagates_to_downstream_blocker(finding_id: str) -> None:
    findings = (
        RedTeamFinding(
            finding_id=finding_id,
            status=RedTeamFindingStatus.FAIL,
            reason=f"Synthetic adversarial finding: {finding_id}",
        ),
    )
    assert (
        red_team_downstream_status(
            findings,
            preflight_status=PreflightFinalStatus.FILING_READY,
        )
        is PreflightFinalStatus.NOT_READY
    )


def test_p4_h_red_team_unknown_abstains_and_pass_preserves_preflight() -> None:
    unknown = RedTeamFinding(
        finding_id="synthetic-unknown",
        status=RedTeamFindingStatus.UNKNOWN,
        reason="Synthetic material uncertainty remains.",
    )
    passed = RedTeamFinding(
        finding_id="synthetic-pass",
        status=RedTeamFindingStatus.PASS,
        reason="Synthetic adversarial check passed.",
    )
    assert (
        red_team_downstream_status(
            (unknown,),
            preflight_status=PreflightFinalStatus.FILING_READY,
        )
        is PreflightFinalStatus.ABSTAIN
    )
    assert (
        red_team_downstream_status(
            (passed,),
            preflight_status=PreflightFinalStatus.FILING_READY,
        )
        is PreflightFinalStatus.FILING_READY
    )
