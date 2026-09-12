from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from core.cirp.contracts import (
    CIRPContractError,
    DeadlineStatus,
    LegalSourceRef,
    LegalSourceVerificationStatus,
    ProceduralRulePack,
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

DIGEST_A = "a" * 64
NOW = datetime(2026, 9, 12, 8, 45, tzinfo=UTC)


def legal_source(
    *,
    verification_status: LegalSourceVerificationStatus = LegalSourceVerificationStatus.VERIFIED,
    effective_from: date = date(2026, 1, 1),
    effective_until: date | None = None,
    jurisdiction: str = "PL",
) -> LegalSourceRef:
    return LegalSourceRef(
        source_id="source:synthetic:deadline:v1",
        jurisdiction=jurisdiction,
        authority_type="synthetic_fixture",
        formal_citation="Synthetic deadline source 1",
        source_uri="synthetic://procedural/deadline-source-1",
        source_digest=DIGEST_A if verification_status is LegalSourceVerificationStatus.VERIFIED else None,
        effective_from=effective_from,
        effective_until=effective_until,
        retrieved_at=NOW,
        verification_status=verification_status,
    )


def calendar(*, holidays: tuple[date, ...] = ()) -> DeadlineCalendarProfile:
    return DeadlineCalendarProfile(
        profile_id="PL-SYNTHETIC-CALENDAR@1",
        timezone="Europe/Warsaw",
        weekend_days=(5, 6),
        holidays=holidays,
        legal_source_ids=("source:synthetic:deadline:v1",),
    )


def rule(
    profile: DeadlineCalendarProfile,
    *,
    duration_value: int = 2,
    duration_unit: DeadlineDurationUnit = DeadlineDurationUnit.CALENDAR_DAYS,
    start_rule: DeadlineStartRule = DeadlineStartRule.EXCLUDE_TRIGGER,
    roll_convention: DeadlineRollConvention = DeadlineRollConvention.NEXT_BUSINESS_DAY,
) -> ExecutableDeadlineRule:
    return ExecutableDeadlineRule.build(
        rule_id="PL-SYNTHETIC-DEADLINE-1",
        version="1",
        trigger_type="SERVICE_DATE",
        duration_value=duration_value,
        duration_unit=duration_unit,
        start_rule=start_rule,
        roll_convention=roll_convention,
        calendar_profile=profile,
        legal_source_ids=("source:synthetic:deadline:v1",),
        effective_from=date(2026, 1, 1),
    )


def pack(
    executable_rule: ExecutableDeadlineRule,
    source: LegalSourceRef,
    *,
    deadline_rules: tuple[str, ...] | None = None,
) -> ProceduralRulePack:
    return ProceduralRulePack.build(
        pack_id="PL-SYNTHETIC@1",
        version="1",
        jurisdiction="PL",
        procedure_family="synthetic_procedure",
        effective_from=date(2026, 1, 1),
        effective_until=None,
        source_set=(source,),
        deadline_rules=(executable_rule.pack_token,) if deadline_rules is None else deadline_rules,
        status=RulePackStatus.ACTIVE,
    )


def guard(
    *,
    profile: DeadlineCalendarProfile | None = None,
    source: LegalSourceRef | None = None,
    executable_rule: ExecutableDeadlineRule | None = None,
) -> tuple[DeadlineGuard, ExecutableDeadlineRule]:
    selected_profile = profile or calendar()
    selected_source = source or legal_source()
    selected_rule = executable_rule or rule(selected_profile)
    return (
        DeadlineGuard(
            rule_pack=pack(selected_rule, selected_source),
            rules=(selected_rule,),
            calendars=(selected_profile,),
        ),
        selected_rule,
    )


def evaluate(
    deadline_guard: DeadlineGuard,
    executable_rule: ExecutableDeadlineRule,
    *,
    trigger_date: date | None = date(2026, 9, 11),
    trigger_evidence: str | None = "evidence:synthetic-service",
    trigger_status: DeadlineTriggerStatus = DeadlineTriggerStatus.VERIFIED,
    effective_law_date: date | None = date(2026, 9, 11),
    evaluation_time: datetime = NOW,
    safe_buffer_business_days: int | None = None,
):
    return deadline_guard.evaluate(
        deadline_id="deadline:synthetic:1",
        rule_key=executable_rule.key,
        trigger_type="SERVICE_DATE",
        trigger_date=trigger_date,
        trigger_evidence=trigger_evidence,
        trigger_status=trigger_status,
        effective_law_date=effective_law_date,
        evaluation_time=evaluation_time,
        safe_buffer_business_days=safe_buffer_business_days,
    )


def test_verified_deadline_rolls_weekend_and_sets_safe_internal_target() -> None:
    deadline_guard, executable_rule = guard()

    assessment = evaluate(
        deadline_guard,
        executable_rule,
        safe_buffer_business_days=1,
    )

    assert assessment.status is DeadlineStatus.VERIFIED
    assert assessment.legal_deadline == date(2026, 9, 14)
    assert assessment.safe_internal_deadline == date(2026, 9, 11)
    assert assessment.rule_id == executable_rule.rule_id
    assert assessment.rule_version == executable_rule.version
    assert assessment.legal_source_refs == ("source:synthetic:deadline:v1",)
    assert assessment.blocking_questions == ()


def test_business_day_deadline_skips_weekend_and_holiday() -> None:
    selected_calendar = calendar(holidays=(date(2026, 9, 14),))
    executable_rule = rule(
        selected_calendar,
        duration_unit=DeadlineDurationUnit.BUSINESS_DAYS,
        roll_convention=DeadlineRollConvention.NONE,
    )
    deadline_guard, _ = guard(profile=selected_calendar, executable_rule=executable_rule)

    assessment = evaluate(deadline_guard, executable_rule)

    assert assessment.status is DeadlineStatus.VERIFIED
    assert assessment.legal_deadline == date(2026, 9, 16)


def test_provisional_trigger_cannot_be_promoted_to_verified_deadline() -> None:
    deadline_guard, executable_rule = guard()

    assessment = evaluate(
        deadline_guard,
        executable_rule,
        trigger_status=DeadlineTriggerStatus.PROVISIONAL,
    )

    assert assessment.status is DeadlineStatus.PROVISIONAL
    assert assessment.legal_deadline == date(2026, 9, 14)


@pytest.mark.parametrize(
    ("trigger_status", "trigger_date", "expected_status"),
    [
        (DeadlineTriggerStatus.MISSING, None, DeadlineStatus.MISSING_INPUT),
        (DeadlineTriggerStatus.CONFLICTING, None, DeadlineStatus.CONFLICTING_EVIDENCE),
    ],
)
def test_missing_or_conflicting_trigger_fails_closed(
    trigger_status: DeadlineTriggerStatus,
    trigger_date: date | None,
    expected_status: DeadlineStatus,
) -> None:
    deadline_guard, executable_rule = guard()

    assessment = evaluate(
        deadline_guard,
        executable_rule,
        trigger_date=trigger_date,
        trigger_evidence=None,
        trigger_status=trigger_status,
    )

    assert assessment.status is expected_status
    assert assessment.legal_deadline is None
    assert assessment.blocking_questions


def test_missing_effective_law_date_blocks_calculation() -> None:
    deadline_guard, executable_rule = guard()

    assessment = evaluate(
        deadline_guard,
        executable_rule,
        effective_law_date=None,
    )

    assert assessment.status is DeadlineStatus.MISSING_INPUT
    assert assessment.legal_deadline is None


def test_unverified_legal_source_cannot_produce_verified_deadline() -> None:
    provisional_source = legal_source(
        verification_status=LegalSourceVerificationStatus.PROVISIONAL
    )
    deadline_guard, executable_rule = guard(source=provisional_source)

    assessment = evaluate(deadline_guard, executable_rule)

    assert assessment.status is DeadlineStatus.UNKNOWN_RULE
    assert assessment.legal_deadline is None
    assert assessment.blocking_questions


def test_source_not_effective_on_relevant_date_fails_closed() -> None:
    future_source = legal_source(effective_from=date(2026, 10, 1))
    deadline_guard, executable_rule = guard(source=future_source)

    assessment = evaluate(deadline_guard, executable_rule)

    assert assessment.status is DeadlineStatus.UNKNOWN_RULE
    assert assessment.legal_deadline is None


def test_unknown_rule_identity_returns_unknown_rule_without_guessing() -> None:
    deadline_guard, _ = guard()

    assessment = deadline_guard.evaluate(
        deadline_id="deadline:synthetic:unknown",
        rule_key="unknown-rule@9",
        trigger_type="SERVICE_DATE",
        trigger_date=date(2026, 9, 11),
        trigger_evidence="evidence:synthetic-service",
        trigger_status=DeadlineTriggerStatus.VERIFIED,
        effective_law_date=date(2026, 9, 11),
        evaluation_time=NOW,
    )

    assert assessment.status is DeadlineStatus.UNKNOWN_RULE
    assert assessment.legal_deadline is None
    assert "unknown-rule@9" in assessment.blocking_questions[0]


def test_pack_token_binds_exact_executable_rule_semantics() -> None:
    selected_calendar = calendar()
    original_rule = rule(selected_calendar, duration_value=2)
    changed_rule = rule(selected_calendar, duration_value=3)
    selected_source = legal_source()
    rule_pack = pack(
        original_rule,
        selected_source,
        deadline_rules=(original_rule.pack_token,),
    )

    with pytest.raises(CIRPContractError, match="exactly bind executable semantics"):
        DeadlineGuard(
            rule_pack=rule_pack,
            rules=(changed_rule,),
            calendars=(selected_calendar,),
        )


def test_calendar_digest_prevents_semantic_calendar_substitution() -> None:
    original_calendar = calendar()
    changed_calendar = calendar(holidays=(date(2026, 9, 14),))
    executable_rule = rule(original_calendar)
    selected_source = legal_source()

    with pytest.raises(CIRPContractError, match="calendar profile digest mismatch"):
        DeadlineGuard(
            rule_pack=pack(executable_rule, selected_source),
            rules=(executable_rule,),
            calendars=(changed_calendar,),
        )


def test_rule_pack_rejects_cross_jurisdiction_source_binding() -> None:
    selected_calendar = calendar()
    executable_rule = rule(selected_calendar)
    foreign_source = legal_source(jurisdiction="XX")

    with pytest.raises(CIRPContractError, match="jurisdiction"):
        DeadlineGuard(
            rule_pack=pack(executable_rule, foreign_source),
            rules=(executable_rule,),
            calendars=(selected_calendar,),
        )


def test_expired_status_uses_timezone_aware_evaluation_time() -> None:
    deadline_guard, executable_rule = guard()

    assessment = evaluate(
        deadline_guard,
        executable_rule,
        evaluation_time=datetime(2026, 9, 15, 1, 0, tzinfo=UTC),
    )

    assert assessment.status is DeadlineStatus.EXPIRED
    assert assessment.legal_deadline == date(2026, 9, 14)


def test_naive_evaluation_time_is_rejected() -> None:
    deadline_guard, executable_rule = guard()

    with pytest.raises(CIRPContractError, match="timezone-aware"):
        evaluate(
            deadline_guard,
            executable_rule,
            evaluation_time=datetime(2026, 9, 12, 8, 45),
        )


def test_internal_buffer_cannot_move_before_trigger_date() -> None:
    deadline_guard, executable_rule = guard()

    with pytest.raises(CIRPContractError, match="before the trigger date"):
        evaluate(
            deadline_guard,
            executable_rule,
            safe_buffer_business_days=2,
        )


def test_calendar_requires_at_least_one_business_day() -> None:
    with pytest.raises(CIRPContractError, match="at least one business day"):
        DeadlineCalendarProfile(
            profile_id="invalid-calendar",
            timezone="UTC",
            weekend_days=(0, 1, 2, 3, 4, 5, 6),
        )
