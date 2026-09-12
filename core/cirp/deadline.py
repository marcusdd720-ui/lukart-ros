"""Executable, fail-closed deadline semantics for CIRP-02.

The runtime in this module deliberately contains no jurisdiction-specific legal
rules. It evaluates typed rule specifications supplied by a ProceduralRulePack
and binds the executable semantics to the pack through content digests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import TypedDict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.cirp.contracts import (
    CIRPContractError,
    DeadlineAssessment,
    DeadlineStatus,
    LegalSourceRef,
    LegalSourceVerificationStatus,
    ProceduralRulePack,
    RulePackStatus,
)
from core.p3.contracts import P3ContractError, content_digest, require_hex_digest


class DeadlineDurationUnit(StrEnum):
    CALENDAR_DAYS = "CALENDAR_DAYS"
    BUSINESS_DAYS = "BUSINESS_DAYS"


class DeadlineStartRule(StrEnum):
    EXCLUDE_TRIGGER = "EXCLUDE_TRIGGER"
    INCLUDE_TRIGGER = "INCLUDE_TRIGGER"


class DeadlineRollConvention(StrEnum):
    NONE = "NONE"
    NEXT_BUSINESS_DAY = "NEXT_BUSINESS_DAY"


class DeadlineTriggerStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PROVISIONAL = "PROVISIONAL"
    MISSING = "MISSING"
    CONFLICTING = "CONFLICTING"


def _require_nonblank(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise CIRPContractError(f"{field_name} must be nonblank and already canonical")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CIRPContractError(f"{field_name} cannot contain control characters")
    return value


def _unique_nonblank(values: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    normalized = tuple(_require_nonblank(item, field_name=field_name) for item in values)
    if len(normalized) != len(set(normalized)):
        raise CIRPContractError(f"{field_name} cannot contain duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class DeadlineCalendarProfile:
    """Deterministic calendar semantics referenced by executable deadline rules."""

    profile_id: str
    timezone: str
    weekend_days: tuple[int, ...] = (5, 6)
    holidays: tuple[date, ...] = ()
    legal_source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "profile_id",
            _require_nonblank(self.profile_id, field_name="profile_id"),
        )
        object.__setattr__(
            self,
            "timezone",
            _require_nonblank(self.timezone, field_name="timezone"),
        )
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise CIRPContractError(f"unknown calendar timezone: {self.timezone}") from exc

        normalized_weekend = tuple(sorted(self.weekend_days))
        if len(normalized_weekend) != len(set(normalized_weekend)):
            raise CIRPContractError("weekend_days cannot contain duplicates")
        if any(value < 0 or value > 6 for value in normalized_weekend):
            raise CIRPContractError("weekend_days values must be in range 0..6")
        if len(normalized_weekend) == 7:
            raise CIRPContractError("calendar profile must contain at least one business day")
        object.__setattr__(self, "weekend_days", normalized_weekend)

        normalized_holidays = tuple(sorted(self.holidays))
        if len(normalized_holidays) != len(set(normalized_holidays)):
            raise CIRPContractError("holidays cannot contain duplicates")
        object.__setattr__(self, "holidays", normalized_holidays)
        object.__setattr__(
            self,
            "legal_source_ids",
            _unique_nonblank(self.legal_source_ids, field_name="legal_source_ids"),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "timezone": self.timezone,
            "weekend_days": list(self.weekend_days),
            "holidays": [item.isoformat() for item in self.holidays],
            "legal_source_ids": list(self.legal_source_ids),
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())

    def is_business_day(self, value: date) -> bool:
        return value.weekday() not in self.weekend_days and value not in self.holidays

    def next_business_day(self, value: date) -> date:
        current = value
        while not self.is_business_day(current):
            current += timedelta(days=1)
        return current

    def subtract_business_days(self, value: date, count: int) -> date:
        if count < 0:
            raise CIRPContractError("business-day buffer cannot be negative")
        current = value
        remaining = count
        while remaining:
            current -= timedelta(days=1)
            if self.is_business_day(current):
                remaining -= 1
        return current


@dataclass(frozen=True, slots=True)
class ExecutableDeadlineRule:
    """Executable rule semantics cryptographically bindable to a rule pack."""

    rule_id: str
    version: str
    trigger_type: str
    duration_value: int
    duration_unit: DeadlineDurationUnit
    start_rule: DeadlineStartRule
    roll_convention: DeadlineRollConvention
    calendar_profile_id: str
    calendar_profile_digest: str
    legal_source_ids: tuple[str, ...]
    effective_from: date
    effective_until: date | None = None

    def __post_init__(self) -> None:
        for field_name in ("rule_id", "version", "trigger_type", "calendar_profile_id"):
            object.__setattr__(
                self,
                field_name,
                _require_nonblank(getattr(self, field_name), field_name=field_name),
            )
        if self.duration_value < 0:
            raise CIRPContractError("duration_value cannot be negative")
        if self.effective_until is not None and self.effective_until < self.effective_from:
            raise CIRPContractError("deadline rule effective_until precedes effective_from")
        try:
            normalized_calendar_digest = require_hex_digest(
                self.calendar_profile_digest,
                field_name="calendar_profile_digest",
            )
        except P3ContractError as exc:
            raise CIRPContractError(str(exc)) from exc
        object.__setattr__(self, "calendar_profile_digest", normalized_calendar_digest)
        object.__setattr__(
            self,
            "legal_source_ids",
            _unique_nonblank(self.legal_source_ids, field_name="legal_source_ids"),
        )
        if not self.legal_source_ids:
            raise CIRPContractError("executable deadline rule requires legal_source_ids")

    @classmethod
    def build(
        cls,
        *,
        rule_id: str,
        version: str,
        trigger_type: str,
        duration_value: int,
        duration_unit: DeadlineDurationUnit,
        start_rule: DeadlineStartRule,
        roll_convention: DeadlineRollConvention,
        calendar_profile: DeadlineCalendarProfile,
        legal_source_ids: tuple[str, ...],
        effective_from: date,
        effective_until: date | None = None,
    ) -> ExecutableDeadlineRule:
        return cls(
            rule_id=rule_id,
            version=version,
            trigger_type=trigger_type,
            duration_value=duration_value,
            duration_unit=duration_unit,
            start_rule=start_rule,
            roll_convention=roll_convention,
            calendar_profile_id=calendar_profile.profile_id,
            calendar_profile_digest=calendar_profile.digest(),
            legal_source_ids=legal_source_ids,
            effective_from=effective_from,
            effective_until=effective_until,
        )

    @property
    def key(self) -> str:
        return f"{self.rule_id}@{self.version}"

    @property
    def pack_token(self) -> str:
        return f"{self.key}#{self.digest()}"

    def effective_on(self, value: date) -> bool:
        return self.effective_from <= value and (
            self.effective_until is None or value <= self.effective_until
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "version": self.version,
            "trigger_type": self.trigger_type,
            "duration_value": self.duration_value,
            "duration_unit": self.duration_unit.value,
            "start_rule": self.start_rule.value,
            "roll_convention": self.roll_convention.value,
            "calendar_profile_id": self.calendar_profile_id,
            "calendar_profile_digest": self.calendar_profile_digest,
            "legal_source_ids": list(self.legal_source_ids),
            "effective_from": self.effective_from.isoformat(),
            "effective_until": (
                self.effective_until.isoformat() if self.effective_until is not None else None
            ),
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


class _DeadlineAssessmentBase(TypedDict):
    deadline_id: str
    trigger_type: str
    trigger_date: date | None
    trigger_evidence: str | None
    rule_pack_id: str | None
    rule_id: str | None
    rule_version: str | None
    legal_source_refs: tuple[str, ...]
    effective_law_date: date | None
    duration_value: int | None
    duration_unit: str | None
    calculation_method: str | None
    calendar_profile: str | None
    timezone: str | None


class DeadlineGuard:
    """Fail-closed evaluator for CIRP-02 executable deadline rules."""

    def __init__(
        self,
        *,
        rule_pack: ProceduralRulePack,
        rules: tuple[ExecutableDeadlineRule, ...],
        calendars: tuple[DeadlineCalendarProfile, ...],
    ) -> None:
        if rule_pack.status is not RulePackStatus.ACTIVE:
            raise CIRPContractError("DeadlineGuard requires an ACTIVE ProceduralRulePack")
        if not rules:
            raise CIRPContractError("DeadlineGuard requires at least one executable deadline rule")

        rule_map: dict[str, ExecutableDeadlineRule] = {}
        for rule in rules:
            if rule.key in rule_map:
                raise CIRPContractError(f"duplicate executable deadline rule key: {rule.key}")
            rule_map[rule.key] = rule

        calendar_map: dict[str, DeadlineCalendarProfile] = {}
        for calendar in calendars:
            if calendar.profile_id in calendar_map:
                raise CIRPContractError(
                    f"duplicate deadline calendar profile: {calendar.profile_id}"
                )
            calendar_map[calendar.profile_id] = calendar

        expected_tokens = tuple(sorted(rule.pack_token for rule in rules))
        actual_tokens = tuple(sorted(rule_pack.deadline_rules))
        if actual_tokens != expected_tokens:
            raise CIRPContractError(
                "ProceduralRulePack deadline_rules do not exactly bind executable semantics"
            )

        source_ids = {source.source_id for source in rule_pack.source_set}
        for source in rule_pack.source_set:
            if source.jurisdiction != rule_pack.jurisdiction:
                raise CIRPContractError(
                    "rule pack legal source jurisdiction does not match rule pack jurisdiction"
                )
        for rule in rules:
            bound_calendar = calendar_map.get(rule.calendar_profile_id)
            if bound_calendar is None:
                raise CIRPContractError(
                    f"missing calendar profile for executable rule: {rule.calendar_profile_id}"
                )
            if bound_calendar.digest() != rule.calendar_profile_digest:
                raise CIRPContractError(
                    f"calendar profile digest mismatch for executable rule: {rule.key}"
                )
            missing_sources = (
                set(rule.legal_source_ids) | set(bound_calendar.legal_source_ids)
            ) - source_ids
            if missing_sources:
                joined = ", ".join(sorted(missing_sources))
                raise CIRPContractError(
                    f"deadline runtime references sources outside rule pack: {joined}"
                )

        self._rule_pack = rule_pack
        self._rules = MappingProxyType(rule_map)
        self._calendars = MappingProxyType(calendar_map)
        self._sources = MappingProxyType(
            {source.source_id: source for source in rule_pack.source_set}
        )

    def evaluate(
        self,
        *,
        deadline_id: str,
        rule_key: str,
        trigger_type: str,
        trigger_date: date | None,
        trigger_evidence: str | None,
        trigger_status: DeadlineTriggerStatus,
        effective_law_date: date | None,
        evaluation_time: datetime,
        safe_buffer_business_days: int | None = None,
    ) -> DeadlineAssessment:
        deadline_id = _require_nonblank(deadline_id, field_name="deadline_id")
        rule_key = _require_nonblank(rule_key, field_name="rule_key")
        trigger_type = _require_nonblank(trigger_type, field_name="trigger_type")
        if evaluation_time.tzinfo is None or evaluation_time.utcoffset() is None:
            raise CIRPContractError("evaluation_time must be timezone-aware")
        if safe_buffer_business_days is not None and safe_buffer_business_days < 0:
            raise CIRPContractError("safe_buffer_business_days cannot be negative")

        rule = self._rules.get(rule_key)
        if rule is None:
            return DeadlineAssessment(
                deadline_id=deadline_id,
                trigger_type=trigger_type,
                trigger_date=trigger_date,
                trigger_evidence=trigger_evidence,
                rule_pack_id=self._rule_pack.pack_id,
                rule_id=rule_key,
                rule_version=None,
                legal_source_refs=(),
                effective_law_date=effective_law_date,
                duration_value=None,
                duration_unit=None,
                calculation_method=None,
                calendar_profile=None,
                timezone=None,
                legal_deadline=None,
                safe_internal_deadline=None,
                status=DeadlineStatus.UNKNOWN_RULE,
                blocking_questions=(f"Resolve executable deadline rule: {rule_key}",),
            )

        calendar = self._calendars[rule.calendar_profile_id]
        source_ids = tuple(sorted(set(rule.legal_source_ids) | set(calendar.legal_source_ids)))
        common: _DeadlineAssessmentBase = {
            "deadline_id": deadline_id,
            "trigger_type": trigger_type,
            "trigger_date": trigger_date,
            "trigger_evidence": trigger_evidence,
            "rule_pack_id": self._rule_pack.pack_id,
            "rule_id": rule.rule_id,
            "rule_version": rule.version,
            "legal_source_refs": source_ids,
            "effective_law_date": effective_law_date,
            "duration_value": rule.duration_value,
            "duration_unit": rule.duration_unit.value,
            "calculation_method": self._calculation_method(rule),
            "calendar_profile": calendar.profile_id,
            "timezone": calendar.timezone,
        }

        if effective_law_date is None:
            return DeadlineAssessment(
                **common,
                legal_deadline=None,
                safe_internal_deadline=None,
                status=DeadlineStatus.MISSING_INPUT,
                blocking_questions=("Establish the effective-law date for deadline evaluation.",),
            )

        if not self._pack_effective_on(effective_law_date) or not rule.effective_on(
            effective_law_date
        ):
            return DeadlineAssessment(
                **common,
                legal_deadline=None,
                safe_internal_deadline=None,
                status=DeadlineStatus.UNKNOWN_RULE,
                blocking_questions=(
                    "Resolve the rule pack/rule version effective on the relevant law date.",
                ),
            )

        source_blockers = self._source_blockers(source_ids, effective_law_date)
        if source_blockers:
            return DeadlineAssessment(
                **common,
                legal_deadline=None,
                safe_internal_deadline=None,
                status=DeadlineStatus.UNKNOWN_RULE,
                blocking_questions=source_blockers,
            )

        if trigger_type != rule.trigger_type:
            return DeadlineAssessment(
                **common,
                legal_deadline=None,
                safe_internal_deadline=None,
                status=DeadlineStatus.UNKNOWN_RULE,
                blocking_questions=(
                    f"Rule {rule.key} requires trigger type {rule.trigger_type}, "
                    f"not {trigger_type}.",
                ),
            )

        if trigger_status is DeadlineTriggerStatus.CONFLICTING:
            return DeadlineAssessment(
                **common,
                legal_deadline=None,
                safe_internal_deadline=None,
                status=DeadlineStatus.CONFLICTING_EVIDENCE,
                blocking_questions=("Resolve conflicting trigger-date evidence.",),
            )

        if trigger_status is DeadlineTriggerStatus.MISSING or trigger_date is None:
            return DeadlineAssessment(
                **common,
                legal_deadline=None,
                safe_internal_deadline=None,
                status=DeadlineStatus.MISSING_INPUT,
                blocking_questions=("Establish the deadline trigger date.",),
            )

        if trigger_evidence is None:
            return DeadlineAssessment(
                **common,
                legal_deadline=None,
                safe_internal_deadline=None,
                status=DeadlineStatus.MISSING_INPUT,
                blocking_questions=("Bind the trigger date to evidence.",),
            )
        trigger_evidence = _require_nonblank(trigger_evidence, field_name="trigger_evidence")
        common["trigger_evidence"] = trigger_evidence

        legal_deadline = self._calculate_deadline(rule, calendar, trigger_date)
        safe_internal_deadline = None
        if safe_buffer_business_days is not None:
            safe_internal_deadline = calendar.subtract_business_days(
                legal_deadline,
                safe_buffer_business_days,
            )
            if safe_internal_deadline < trigger_date:
                raise CIRPContractError(
                    "safe_buffer_business_days moves the internal deadline before the trigger date"
                )

        status = DeadlineStatus.PROVISIONAL
        if trigger_status is DeadlineTriggerStatus.VERIFIED:
            local_evaluation_date = evaluation_time.astimezone(ZoneInfo(calendar.timezone)).date()
            status = (
                DeadlineStatus.EXPIRED
                if local_evaluation_date > legal_deadline
                else DeadlineStatus.VERIFIED
            )

        return DeadlineAssessment(
            **common,
            legal_deadline=legal_deadline,
            safe_internal_deadline=safe_internal_deadline,
            status=status,
            blocking_questions=(),
        )

    @staticmethod
    def _calculation_method(rule: ExecutableDeadlineRule) -> str:
        return ":".join(
            (
                "CIRP-02",
                rule.duration_unit.value,
                rule.start_rule.value,
                rule.roll_convention.value,
            )
        )

    def _pack_effective_on(self, value: date) -> bool:
        return self._rule_pack.effective_from <= value and (
            self._rule_pack.effective_until is None or value <= self._rule_pack.effective_until
        )

    def _source_blockers(self, source_ids: tuple[str, ...], value: date) -> tuple[str, ...]:
        blockers: list[str] = []
        for source_id in source_ids:
            source: LegalSourceRef = self._sources[source_id]
            if source.verification_status is not LegalSourceVerificationStatus.VERIFIED:
                blockers.append(f"Verify legal source before deadline use: {source_id}")
                continue
            if not source.effective_on(value):
                blockers.append(
                    f"Legal source is not effective on {value.isoformat()}: {source_id}"
                )
        return tuple(blockers)

    @staticmethod
    def _calculate_deadline(
        rule: ExecutableDeadlineRule,
        calendar: DeadlineCalendarProfile,
        trigger_date: date,
    ) -> date:
        if rule.duration_value == 0:
            candidate = trigger_date
        elif rule.duration_unit is DeadlineDurationUnit.CALENDAR_DAYS:
            offset = rule.duration_value
            if rule.start_rule is DeadlineStartRule.INCLUDE_TRIGGER:
                offset -= 1
            candidate = trigger_date + timedelta(days=offset)
        else:
            candidate = trigger_date
            remaining = rule.duration_value
            if (
                rule.start_rule is DeadlineStartRule.INCLUDE_TRIGGER
                and calendar.is_business_day(candidate)
            ):
                remaining -= 1
            while remaining > 0:
                candidate += timedelta(days=1)
                if calendar.is_business_day(candidate):
                    remaining -= 1

        if rule.roll_convention is DeadlineRollConvention.NEXT_BUSINESS_DAY:
            candidate = calendar.next_business_day(candidate)
        return candidate
