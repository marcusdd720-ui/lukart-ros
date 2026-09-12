from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from core.cirp.contracts import (
    CIRPContractError,
    DeadlineAssessment,
    DeadlineStatus,
    EvidenceCategory,
    EvidenceImportance,
    EvidenceRequirement,
    EvidenceRequirementStatus,
    LegalSourceRef,
    LegalSourceVerificationStatus,
    ProceduralRulePack,
    RemedyAdmissibility,
    RulePackStatus,
)
from core.cirp.remedy import (
    ExecutableRemedyRule,
    RemedyApplicabilityStatus,
    RemedyGuard,
)

DIGEST_A = "a" * 64
NOW = datetime(2026, 9, 12, 10, 30, tzinfo=UTC)
LAW_DATE = date(2026, 9, 12)
PACK_ID = "PL-SYNTHETIC@1"
SOURCE_ID = "source:synthetic:remedy:v1"


def legal_source(
    *,
    verification_status: LegalSourceVerificationStatus = LegalSourceVerificationStatus.VERIFIED,
    effective_from: date = date(2026, 1, 1),
    effective_until: date | None = None,
    jurisdiction: str = "PL",
) -> LegalSourceRef:
    return LegalSourceRef(
        source_id=SOURCE_ID,
        jurisdiction=jurisdiction,
        authority_type="synthetic_fixture",
        formal_citation="Synthetic remedy source 1",
        source_uri="synthetic://procedural/remedy-source-1",
        source_digest=(
            DIGEST_A
            if verification_status is LegalSourceVerificationStatus.VERIFIED
            else None
        ),
        effective_from=effective_from,
        effective_until=effective_until,
        retrieved_at=NOW,
        verification_status=verification_status,
    )


def rule(
    *,
    required_evidence_ids: tuple[str, ...] = ("evidence:req:service",),
    deadline_required: bool = True,
    formal_requirements: tuple[str, ...] = ("signed-filing",),
    effective_from: date = date(2026, 1, 1),
) -> ExecutableRemedyRule:
    return ExecutableRemedyRule(
        rule_id="PL-SYNTHETIC-REMEDY-1",
        version="1",
        remedy_type="SYNTHETIC_REVIEW",
        target_authority="synthetic-target-authority",
        filing_authority="synthetic-filing-authority",
        filing_via="synthetic-filing-route",
        formal_requirements=formal_requirements,
        required_evidence_ids=required_evidence_ids,
        preserves_options=("synthetic-option-a",),
        waives_options=(),
        legal_source_ids=(SOURCE_ID,),
        deadline_required=deadline_required,
        effective_from=effective_from,
    )


def pack(
    executable_rule: ExecutableRemedyRule,
    source: LegalSourceRef,
    *,
    remedy_rules: tuple[str, ...] | None = None,
) -> ProceduralRulePack:
    return ProceduralRulePack.build(
        pack_id=PACK_ID,
        version="1",
        jurisdiction="PL",
        procedure_family="synthetic_procedure",
        effective_from=date(2026, 1, 1),
        effective_until=None,
        source_set=(source,),
        remedy_rules=(executable_rule.pack_token,) if remedy_rules is None else remedy_rules,
        status=RulePackStatus.ACTIVE,
    )


def guard(
    *,
    executable_rule: ExecutableRemedyRule | None = None,
    source: LegalSourceRef | None = None,
) -> tuple[RemedyGuard, ExecutableRemedyRule]:
    selected_rule = executable_rule or rule()
    selected_source = source or legal_source()
    return (
        RemedyGuard(
            rule_pack=pack(selected_rule, selected_source),
            rules=(selected_rule,),
        ),
        selected_rule,
    )


def requirement(
    executable_rule: ExecutableRemedyRule,
    *,
    status: EvidenceRequirementStatus = EvidenceRequirementStatus.PRESENT,
    category: EvidenceCategory = EvidenceCategory.ADMISSIBILITY_CRITICAL,
    importance: EvidenceImportance = EvidenceImportance.CRITICAL,
    required_for: tuple[str, ...] | None = None,
) -> EvidenceRequirement:
    evidence_refs = () if status is EvidenceRequirementStatus.MISSING else ("evidence:synthetic:1",)
    return EvidenceRequirement(
        requirement_id="evidence:req:service",
        description="Synthetic service evidence",
        category=category,
        importance=importance,
        required_for=(executable_rule.pack_token,) if required_for is None else required_for,
        expected_evidence_kind="synthetic_service_record",
        status=status,
        evidence_refs=evidence_refs,
    )


def deadline(
    *,
    status: DeadlineStatus = DeadlineStatus.VERIFIED,
    rule_pack_id: str = PACK_ID,
    effective_law_date: date | None = LAW_DATE,
    blockers: tuple[str, ...] = (),
) -> DeadlineAssessment:
    return DeadlineAssessment(
        deadline_id="deadline:synthetic:1",
        trigger_type="SERVICE_DATE",
        trigger_date=date(2026, 9, 11),
        trigger_evidence="evidence:synthetic-service",
        rule_pack_id=rule_pack_id,
        rule_id="PL-SYNTHETIC-DEADLINE-1",
        rule_version="1",
        legal_source_refs=(SOURCE_ID,),
        effective_law_date=effective_law_date,
        duration_value=7,
        duration_unit="CALENDAR_DAYS",
        calculation_method="EXCLUDE_TRIGGER/NONE",
        calendar_profile="SYNTHETIC-CALENDAR@1",
        timezone="Europe/Warsaw",
        legal_deadline=date(2026, 9, 18),
        safe_internal_deadline=date(2026, 9, 17),
        status=status,
        blocking_questions=blockers,
    )


def evaluate(
    remedy_guard: RemedyGuard,
    executable_rule: ExecutableRemedyRule,
    *,
    requirements: tuple[EvidenceRequirement, ...] | None = None,
    applicability_status: RemedyApplicabilityStatus = RemedyApplicabilityStatus.VERIFIED,
    selected_deadline: DeadlineAssessment | None = None,
    effective_law_date: date | None = LAW_DATE,
):
    selected_requirements = (
        (requirement(executable_rule),) if requirements is None else requirements
    )
    if selected_deadline is None and executable_rule.deadline_required:
        selected_deadline = deadline()
    return remedy_guard.evaluate(
        remedy_id="remedy:synthetic:1",
        rule_key=executable_rule.key,
        applicability_status=applicability_status,
        evidence_requirements=selected_requirements,
        effective_law_date=effective_law_date,
        deadline=selected_deadline,
    )


def test_verified_remedy_requires_verified_rule_source_deadline_and_evidence() -> None:
    remedy_guard, executable_rule = guard()

    option = evaluate(remedy_guard, executable_rule)

    assert option.admissibility_status is RemedyAdmissibility.VERIFIED_AVAILABLE
    assert option.applicable_rule_ids == (executable_rule.pack_token,)
    assert option.deadline_id == "deadline:synthetic:1"
    assert option.required_evidence == ("evidence:req:service",)
    assert option.blockers == ()


def test_missing_critical_evidence_propagates_unknown_and_blocks_verification() -> None:
    remedy_guard, executable_rule = guard()
    missing = requirement(executable_rule, status=EvidenceRequirementStatus.MISSING)

    option = evaluate(remedy_guard, executable_rule, requirements=(missing,))

    assert option.admissibility_status is RemedyAdmissibility.UNKNOWN
    assert "evidence:req:service" in option.blockers[0]
    assert "MISSING" in option.blockers[0]


def test_missing_noncritical_supporting_evidence_is_provisional_not_verified() -> None:
    remedy_guard, executable_rule = guard()
    missing = requirement(
        executable_rule,
        status=EvidenceRequirementStatus.MISSING,
        category=EvidenceCategory.SUPPORTING,
        importance=EvidenceImportance.MEDIUM,
    )

    option = evaluate(remedy_guard, executable_rule, requirements=(missing,))

    assert option.admissibility_status is RemedyAdmissibility.PROVISIONALLY_AVAILABLE
    assert option.blockers


def test_conflicting_required_evidence_fails_closed_even_when_noncritical() -> None:
    remedy_guard, executable_rule = guard()
    conflicting = requirement(
        executable_rule,
        status=EvidenceRequirementStatus.CONFLICTING,
        category=EvidenceCategory.SUPPORTING,
        importance=EvidenceImportance.MEDIUM,
    )

    option = evaluate(remedy_guard, executable_rule, requirements=(conflicting,))

    assert option.admissibility_status is RemedyAdmissibility.UNKNOWN
    assert "CONFLICTING" in option.blockers[0]


def test_missing_evidence_assessment_object_fails_closed() -> None:
    remedy_guard, executable_rule = guard()

    option = evaluate(remedy_guard, executable_rule, requirements=())

    assert option.admissibility_status is RemedyAdmissibility.UNKNOWN
    assert option.blockers == ("Assess required evidence requirement: evidence:req:service",)


def test_evidence_dependency_must_bind_to_rule_identity() -> None:
    remedy_guard, executable_rule = guard()
    unrelated = requirement(executable_rule, required_for=("other-rule@1",))

    with pytest.raises(CIRPContractError, match="not bound"):
        evaluate(remedy_guard, executable_rule, requirements=(unrelated,))


def test_provisional_case_applicability_cannot_be_promoted_to_verified() -> None:
    remedy_guard, executable_rule = guard()

    option = evaluate(
        remedy_guard,
        executable_rule,
        applicability_status=RemedyApplicabilityStatus.PROVISIONAL,
    )

    assert option.admissibility_status is RemedyAdmissibility.PROVISIONALLY_AVAILABLE
    assert option.blockers == ("Verify case-specific remedy applicability.",)


def test_verified_non_applicability_returns_not_available() -> None:
    remedy_guard, executable_rule = guard()

    option = evaluate(
        remedy_guard,
        executable_rule,
        applicability_status=RemedyApplicabilityStatus.NOT_APPLICABLE,
    )

    assert option.admissibility_status is RemedyAdmissibility.NOT_AVAILABLE
    assert option.blockers


def test_unknown_or_conflicting_applicability_fails_closed() -> None:
    remedy_guard, executable_rule = guard()

    for status in (
        RemedyApplicabilityStatus.UNKNOWN,
        RemedyApplicabilityStatus.CONFLICTING,
    ):
        option = evaluate(remedy_guard, executable_rule, applicability_status=status)
        assert option.admissibility_status is RemedyAdmissibility.UNKNOWN
        assert option.blockers


def test_provisional_deadline_propagates_provisional_remedy() -> None:
    remedy_guard, executable_rule = guard()
    provisional_deadline = deadline(
        status=DeadlineStatus.PROVISIONAL,
        blockers=("Verify deadline trigger evidence.",),
    )

    option = evaluate(
        remedy_guard,
        executable_rule,
        selected_deadline=provisional_deadline,
    )

    assert option.admissibility_status is RemedyAdmissibility.PROVISIONALLY_AVAILABLE
    assert option.blockers == ("Verify deadline trigger evidence.",)


def test_expired_deadline_closes_deadline_dependent_remedy() -> None:
    remedy_guard, executable_rule = guard()

    option = evaluate(
        remedy_guard,
        executable_rule,
        selected_deadline=deadline(status=DeadlineStatus.EXPIRED),
    )

    assert option.admissibility_status is RemedyAdmissibility.NOT_AVAILABLE
    assert "expired" in option.blockers[0]


def test_unknown_deadline_state_blocks_remedy() -> None:
    remedy_guard, executable_rule = guard()
    unresolved_deadline = deadline(
        status=DeadlineStatus.UNKNOWN_RULE,
        blockers=("Resolve deadline rule.",),
    )

    option = evaluate(
        remedy_guard,
        executable_rule,
        selected_deadline=unresolved_deadline,
    )

    assert option.admissibility_status is RemedyAdmissibility.UNKNOWN
    assert option.blockers == ("Resolve deadline rule.",)


def test_deadline_must_use_same_rule_pack_and_effective_law_date() -> None:
    remedy_guard, executable_rule = guard()

    wrong_pack = evaluate(
        remedy_guard,
        executable_rule,
        selected_deadline=deadline(rule_pack_id="OTHER-PACK@1"),
    )
    wrong_date = evaluate(
        remedy_guard,
        executable_rule,
        selected_deadline=deadline(effective_law_date=date(2026, 9, 11)),
    )

    assert wrong_pack.admissibility_status is RemedyAdmissibility.UNKNOWN
    assert wrong_date.admissibility_status is RemedyAdmissibility.UNKNOWN


def test_missing_effective_law_date_blocks_remedy() -> None:
    remedy_guard, executable_rule = guard()

    option = evaluate(remedy_guard, executable_rule, effective_law_date=None)

    assert option.admissibility_status is RemedyAdmissibility.UNKNOWN
    assert option.blockers


def test_unverified_or_ineffective_legal_source_blocks_remedy() -> None:
    provisional_source = legal_source(
        verification_status=LegalSourceVerificationStatus.PROVISIONAL
    )
    remedy_guard, executable_rule = guard(source=provisional_source)
    provisional = evaluate(remedy_guard, executable_rule)

    future_source = legal_source(effective_from=date(2026, 10, 1))
    future_guard, future_rule = guard(source=future_source)
    ineffective = evaluate(future_guard, future_rule)

    assert provisional.admissibility_status is RemedyAdmissibility.UNKNOWN
    assert ineffective.admissibility_status is RemedyAdmissibility.UNKNOWN


def test_rule_pack_must_exactly_bind_executable_remedy_semantics() -> None:
    original = rule()
    changed = rule(formal_requirements=("signed-filing", "synthetic-copy"))

    with pytest.raises(CIRPContractError, match="exactly bind"):
        RemedyGuard(
            rule_pack=pack(original, legal_source()),
            rules=(changed,),
        )


def test_semantic_change_changes_remedy_pack_token() -> None:
    original = rule()
    changed = rule(formal_requirements=("signed-filing", "synthetic-copy"))

    assert original.key == changed.key
    assert original.pack_token != changed.pack_token


def test_cross_jurisdiction_source_binding_is_rejected() -> None:
    executable_rule = rule()

    with pytest.raises(CIRPContractError, match="jurisdiction"):
        RemedyGuard(
            rule_pack=pack(executable_rule, legal_source(jurisdiction="DE")),
            rules=(executable_rule,),
        )


def test_deadline_input_is_rejected_when_rule_has_no_deadline_dependency() -> None:
    executable_rule = rule(deadline_required=False)
    remedy_guard, _ = guard(executable_rule=executable_rule)

    with pytest.raises(CIRPContractError, match="does not declare"):
        evaluate(
            remedy_guard,
            executable_rule,
            selected_deadline=deadline(),
        )


def test_unknown_executable_rule_is_rejected_without_guessing() -> None:
    remedy_guard, executable_rule = guard()

    with pytest.raises(CIRPContractError, match="unknown executable remedy rule"):
        remedy_guard.evaluate(
            remedy_id="remedy:synthetic:1",
            rule_key="UNKNOWN-RULE@1",
            applicability_status=RemedyApplicabilityStatus.VERIFIED,
            evidence_requirements=(requirement(executable_rule),),
            effective_law_date=LAW_DATE,
            deadline=deadline(),
        )
