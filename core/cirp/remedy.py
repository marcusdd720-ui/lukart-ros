"""Fail-closed remedy and evidence-gap semantics for CIRP-03.

The runtime in this module is jurisdiction-neutral. Production remedy law is
supplied through verified ``ProceduralRulePack`` data and executable rule
semantics bound by content digest. Evidence gaps are propagated explicitly;
critical gaps cannot be promoted to a verified remedy decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import TypedDict

from core.cirp.contracts import (
    CIRPContractError,
    DeadlineAssessment,
    DeadlineStatus,
    EvidenceCategory,
    EvidenceImportance,
    EvidenceRequirement,
    EvidenceRequirementStatus,
    LegalSourceVerificationStatus,
    ProceduralRulePack,
    RemedyAdmissibility,
    RemedyOption,
    RulePackStatus,
)
from core.p3.contracts import content_digest


class RemedyApplicabilityStatus(StrEnum):
    """Evidence posture for case-specific applicability of an executable remedy rule."""

    VERIFIED = "VERIFIED"
    PROVISIONAL = "PROVISIONAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"
    CONFLICTING = "CONFLICTING"


class _RemedyOptionBase(TypedDict):
    remedy_id: str
    remedy_type: str
    target_authority: str
    filing_authority: str
    filing_via: str | None
    applicable_rule_ids: tuple[str, ...]
    deadline_id: str | None
    formal_requirements: tuple[str, ...]
    required_evidence: tuple[str, ...]
    preserves_options: tuple[str, ...]
    waives_options: tuple[str, ...]


def _require_nonblank(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise CIRPContractError(f"{field_name} must be nonblank and already canonical")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CIRPContractError(f"{field_name} cannot contain control characters")
    return value


def _optional_nonblank(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_nonblank(value, field_name=field_name)


def _unique_nonblank(values: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    normalized = tuple(_require_nonblank(item, field_name=field_name) for item in values)
    if len(normalized) != len(set(normalized)):
        raise CIRPContractError(f"{field_name} cannot contain duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class ExecutableRemedyRule:
    """Executable remedy semantics cryptographically bindable to a rule pack."""

    rule_id: str
    version: str
    remedy_type: str
    target_authority: str
    filing_authority: str
    filing_via: str | None
    formal_requirements: tuple[str, ...]
    required_evidence_ids: tuple[str, ...]
    preserves_options: tuple[str, ...]
    waives_options: tuple[str, ...]
    legal_source_ids: tuple[str, ...]
    deadline_required: bool
    effective_from: date
    effective_until: date | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "rule_id",
            "version",
            "remedy_type",
            "target_authority",
            "filing_authority",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_nonblank(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self,
            "filing_via",
            _optional_nonblank(self.filing_via, field_name="filing_via"),
        )
        for field_name in (
            "formal_requirements",
            "required_evidence_ids",
            "preserves_options",
            "waives_options",
            "legal_source_ids",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique_nonblank(getattr(self, field_name), field_name=field_name),
            )
        if not self.legal_source_ids:
            raise CIRPContractError("executable remedy rule requires legal_source_ids")
        if not isinstance(self.deadline_required, bool):
            raise CIRPContractError("deadline_required must be boolean")
        if self.effective_until is not None and self.effective_until < self.effective_from:
            raise CIRPContractError("remedy rule effective_until precedes effective_from")

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
            "remedy_type": self.remedy_type,
            "target_authority": self.target_authority,
            "filing_authority": self.filing_authority,
            "filing_via": self.filing_via,
            "formal_requirements": list(self.formal_requirements),
            "required_evidence_ids": list(self.required_evidence_ids),
            "preserves_options": list(self.preserves_options),
            "waives_options": list(self.waives_options),
            "legal_source_ids": list(self.legal_source_ids),
            "deadline_required": self.deadline_required,
            "effective_from": self.effective_from.isoformat(),
            "effective_until": (
                self.effective_until.isoformat() if self.effective_until is not None else None
            ),
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


class RemedyGuard:
    """Evaluate remedy availability while propagating dependent evidence gaps."""

    _CRITICAL_CATEGORIES = frozenset(
        {
            EvidenceCategory.DEADLINE_CRITICAL,
            EvidenceCategory.ADMISSIBILITY_CRITICAL,
            EvidenceCategory.MERITS_CRITICAL,
        }
    )

    def __init__(
        self,
        *,
        rule_pack: ProceduralRulePack,
        rules: tuple[ExecutableRemedyRule, ...],
    ) -> None:
        if rule_pack.status is not RulePackStatus.ACTIVE:
            raise CIRPContractError("RemedyGuard requires an ACTIVE ProceduralRulePack")
        if not rules:
            raise CIRPContractError("RemedyGuard requires at least one executable remedy rule")

        rule_map: dict[str, ExecutableRemedyRule] = {}
        for rule in rules:
            if rule.key in rule_map:
                raise CIRPContractError(f"duplicate executable remedy rule key: {rule.key}")
            rule_map[rule.key] = rule

        expected_tokens = tuple(sorted(rule.pack_token for rule in rules))
        actual_tokens = tuple(sorted(rule_pack.remedy_rules))
        if actual_tokens != expected_tokens:
            raise CIRPContractError(
                "ProceduralRulePack remedy_rules do not exactly bind executable semantics"
            )

        source_ids = {source.source_id for source in rule_pack.source_set}
        for source in rule_pack.source_set:
            if source.jurisdiction != rule_pack.jurisdiction:
                raise CIRPContractError(
                    "rule pack legal source jurisdiction does not match rule pack jurisdiction"
                )
        for rule in rules:
            missing_sources = set(rule.legal_source_ids) - source_ids
            if missing_sources:
                joined = ", ".join(sorted(missing_sources))
                raise CIRPContractError(
                    f"remedy runtime references sources outside rule pack: {joined}"
                )

        self._rule_pack = rule_pack
        self._rules = MappingProxyType(rule_map)
        self._sources = MappingProxyType(
            {source.source_id: source for source in rule_pack.source_set}
        )

    def evaluate(
        self,
        *,
        remedy_id: str,
        rule_key: str,
        applicability_status: RemedyApplicabilityStatus,
        evidence_requirements: tuple[EvidenceRequirement, ...],
        effective_law_date: date | None,
        deadline: DeadlineAssessment | None = None,
    ) -> RemedyOption:
        remedy_id = _require_nonblank(remedy_id, field_name="remedy_id")
        rule_key = _require_nonblank(rule_key, field_name="rule_key")
        rule = self._rules.get(rule_key)
        if rule is None:
            raise CIRPContractError(f"unknown executable remedy rule: {rule_key}")

        requirement_map: dict[str, EvidenceRequirement] = {}
        for requirement in evidence_requirements:
            if requirement.requirement_id in requirement_map:
                raise CIRPContractError(
                    f"duplicate evidence requirement: {requirement.requirement_id}"
                )
            requirement_map[requirement.requirement_id] = requirement

        deadline_id = deadline.deadline_id if deadline is not None else None
        common: _RemedyOptionBase = {
            "remedy_id": remedy_id,
            "remedy_type": rule.remedy_type,
            "target_authority": rule.target_authority,
            "filing_authority": rule.filing_authority,
            "filing_via": rule.filing_via,
            "applicable_rule_ids": (rule.pack_token,),
            "deadline_id": deadline_id if rule.deadline_required else None,
            "formal_requirements": rule.formal_requirements,
            "required_evidence": rule.required_evidence_ids,
            "preserves_options": rule.preserves_options,
            "waives_options": rule.waives_options,
        }

        if not rule.deadline_required and deadline is not None:
            raise CIRPContractError(
                f"remedy rule {rule.key} does not declare a deadline dependency"
            )

        if effective_law_date is None:
            return RemedyOption(
                **common,
                admissibility_status=RemedyAdmissibility.UNKNOWN,
                blockers=("Establish the effective-law date for remedy evaluation.",),
            )

        if not self._pack_effective_on(effective_law_date) or not rule.effective_on(
            effective_law_date
        ):
            return RemedyOption(
                **common,
                admissibility_status=RemedyAdmissibility.UNKNOWN,
                blockers=(
                    "Resolve the rule pack/remedy rule version effective on the relevant law date.",
                ),
            )

        source_blockers = self._source_blockers(rule.legal_source_ids, effective_law_date)
        if source_blockers:
            return RemedyOption(
                **common,
                admissibility_status=RemedyAdmissibility.UNKNOWN,
                blockers=source_blockers,
            )

        if applicability_status is RemedyApplicabilityStatus.NOT_APPLICABLE:
            return RemedyOption(
                **common,
                admissibility_status=RemedyAdmissibility.NOT_AVAILABLE,
                blockers=("Verified applicability assessment excludes this remedy.",),
            )
        if applicability_status is RemedyApplicabilityStatus.UNKNOWN:
            return RemedyOption(
                **common,
                admissibility_status=RemedyAdmissibility.UNKNOWN,
                blockers=("Establish whether the remedy rule applies to the current posture.",),
            )
        if applicability_status is RemedyApplicabilityStatus.CONFLICTING:
            return RemedyOption(
                **common,
                admissibility_status=RemedyAdmissibility.UNKNOWN,
                blockers=("Resolve conflicting evidence about remedy applicability.",),
            )

        provisional_blockers: list[str] = []
        if applicability_status is RemedyApplicabilityStatus.PROVISIONAL:
            provisional_blockers.append("Verify case-specific remedy applicability.")

        deadline_status, deadline_blockers = self._evaluate_deadline_dependency(
            rule=rule,
            deadline=deadline,
            effective_law_date=effective_law_date,
        )
        if deadline_status is RemedyAdmissibility.NOT_AVAILABLE:
            return RemedyOption(
                **common,
                admissibility_status=deadline_status,
                blockers=deadline_blockers,
            )
        if deadline_status is RemedyAdmissibility.UNKNOWN:
            return RemedyOption(
                **common,
                admissibility_status=deadline_status,
                blockers=deadline_blockers,
            )
        if deadline_status is RemedyAdmissibility.PROVISIONALLY_AVAILABLE:
            provisional_blockers.extend(deadline_blockers)

        evidence_status, evidence_blockers = self._evaluate_evidence_dependencies(
            rule=rule,
            requirement_map=requirement_map,
        )
        if evidence_status is RemedyAdmissibility.UNKNOWN:
            return RemedyOption(
                **common,
                admissibility_status=evidence_status,
                blockers=evidence_blockers,
            )
        if evidence_status is RemedyAdmissibility.PROVISIONALLY_AVAILABLE:
            provisional_blockers.extend(evidence_blockers)

        if provisional_blockers:
            return RemedyOption(
                **common,
                admissibility_status=RemedyAdmissibility.PROVISIONALLY_AVAILABLE,
                blockers=tuple(dict.fromkeys(provisional_blockers)),
            )

        return RemedyOption(
            **common,
            admissibility_status=RemedyAdmissibility.VERIFIED_AVAILABLE,
            blockers=(),
        )

    def _evaluate_deadline_dependency(
        self,
        *,
        rule: ExecutableRemedyRule,
        deadline: DeadlineAssessment | None,
        effective_law_date: date,
    ) -> tuple[RemedyAdmissibility, tuple[str, ...]]:
        if not rule.deadline_required:
            return RemedyAdmissibility.VERIFIED_AVAILABLE, ()
        if deadline is None:
            return (
                RemedyAdmissibility.UNKNOWN,
                ("Assess the deadline required by this remedy rule.",),
            )
        if deadline.rule_pack_id != self._rule_pack.pack_id:
            return (
                RemedyAdmissibility.UNKNOWN,
                ("Deadline assessment is bound to a different procedural rule pack.",),
            )
        if deadline.effective_law_date != effective_law_date:
            return (
                RemedyAdmissibility.UNKNOWN,
                ("Deadline and remedy evaluations use different effective-law dates.",),
            )
        if deadline.status is DeadlineStatus.EXPIRED:
            return (
                RemedyAdmissibility.NOT_AVAILABLE,
                (f"Dependent deadline is expired: {deadline.deadline_id}",),
            )
        if deadline.status is DeadlineStatus.VERIFIED:
            return RemedyAdmissibility.VERIFIED_AVAILABLE, ()
        if deadline.status is DeadlineStatus.PROVISIONAL:
            blockers = deadline.blocking_questions or (
                f"Verify dependent deadline: {deadline.deadline_id}",
            )
            return RemedyAdmissibility.PROVISIONALLY_AVAILABLE, blockers
        if deadline.status is DeadlineStatus.CONFLICTING_EVIDENCE:
            blockers = deadline.blocking_questions or (
                f"Resolve conflicting dependent deadline evidence: {deadline.deadline_id}",
            )
            return RemedyAdmissibility.UNKNOWN, blockers
        if deadline.status in {DeadlineStatus.MISSING_INPUT, DeadlineStatus.UNKNOWN_RULE}:
            blockers = deadline.blocking_questions or (
                f"Resolve dependent deadline assessment: {deadline.deadline_id}",
            )
            return RemedyAdmissibility.UNKNOWN, blockers
        return (
            RemedyAdmissibility.UNKNOWN,
            (f"Dependent deadline is not applicable to this remedy: {deadline.deadline_id}",),
        )

    def _evaluate_evidence_dependencies(
        self,
        *,
        rule: ExecutableRemedyRule,
        requirement_map: dict[str, EvidenceRequirement],
    ) -> tuple[RemedyAdmissibility, tuple[str, ...]]:
        provisional_blockers: list[str] = []
        unknown_blockers: list[str] = []
        accepted_bindings = {rule.key, rule.pack_token}

        for requirement_id in rule.required_evidence_ids:
            requirement = requirement_map.get(requirement_id)
            if requirement is None:
                unknown_blockers.append(
                    f"Assess required evidence requirement: {requirement_id}"
                )
                continue
            if not accepted_bindings.intersection(requirement.required_for):
                raise CIRPContractError(
                    "evidence requirement is not bound to executable remedy rule: "
                    f"{requirement_id} -> {rule.key}"
                )
            if requirement.status is EvidenceRequirementStatus.PRESENT:
                continue

            label = self._evidence_gap_label(requirement)
            is_critical = (
                requirement.importance is EvidenceImportance.CRITICAL
                or requirement.category in self._CRITICAL_CATEGORIES
            )
            if requirement.status in {
                EvidenceRequirementStatus.CONFLICTING,
                EvidenceRequirementStatus.NOT_APPLICABLE,
            }:
                unknown_blockers.append(label)
            elif is_critical:
                unknown_blockers.append(label)
            else:
                provisional_blockers.append(label)

        if unknown_blockers:
            return RemedyAdmissibility.UNKNOWN, tuple(unknown_blockers)
        if provisional_blockers:
            return RemedyAdmissibility.PROVISIONALLY_AVAILABLE, tuple(provisional_blockers)
        return RemedyAdmissibility.VERIFIED_AVAILABLE, ()

    @staticmethod
    def _evidence_gap_label(requirement: EvidenceRequirement) -> str:
        return (
            f"Evidence gap {requirement.requirement_id}: "
            f"{requirement.status.value} ({requirement.category.value}, "
            f"{requirement.importance.value})"
        )

    def _pack_effective_on(self, value: date) -> bool:
        return self._rule_pack.effective_from <= value and (
            self._rule_pack.effective_until is None or value <= self._rule_pack.effective_until
        )

    def _source_blockers(
        self,
        source_ids: tuple[str, ...],
        effective_law_date: date,
    ) -> tuple[str, ...]:
        blockers: list[str] = []
        for source_id in source_ids:
            source = self._sources[source_id]
            if source.verification_status is not LegalSourceVerificationStatus.VERIFIED:
                blockers.append(f"Verify legal source: {source_id}")
            elif not source.effective_on(effective_law_date):
                blockers.append(
                    f"Resolve legal source version effective on {effective_law_date.isoformat()}: "
                    f"{source_id}"
                )
        return tuple(blockers)
