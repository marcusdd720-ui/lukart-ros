"""Typed, fail-closed contracts for Case Intake & Response Protocol v1.

CIRP contracts describe derived analytical artifacts. They never replace the
Canonical Case Ledger as the authoritative writable case-history SSOT and they
contain no jurisdiction-specific legal rules or autonomous filing behaviour.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum
from types import MappingProxyType

from core.case_ledger.contracts import CaseId
from core.p3.contracts import P3ContractError, canonical_json, content_digest, require_hex_digest

CIRP_VERSION_V1 = "1.0"
CIRP_RUN_SCHEMA_V1 = "lukart.cirp.run.v1"
DOCUMENT_ASSESSMENT_SCHEMA_V1 = "lukart.cirp.document-assessment.v1"
PROCEDURAL_ASSESSMENT_SCHEMA_V1 = "lukart.cirp.procedural-assessment.v1"
SERVICE_ASSESSMENT_SCHEMA_V1 = "lukart.cirp.service-assessment.v1"
DEADLINE_ASSESSMENT_SCHEMA_V1 = "lukart.cirp.deadline-assessment.v1"
LEGAL_SOURCE_SCHEMA_V1 = "lukart.cirp.legal-source-ref.v1"
RULE_PACK_SCHEMA_V1 = "lukart.cirp.procedural-rule-pack.v1"
REMEDY_OPTION_SCHEMA_V1 = "lukart.cirp.remedy-option.v1"
EVIDENCE_REQUIREMENT_SCHEMA_V1 = "lukart.cirp.evidence-requirement.v1"
STRATEGY_OPTION_SCHEMA_V1 = "lukart.cirp.strategy-option.v1"
STRATEGY_DECISION_SCHEMA_V1 = "lukart.cirp.strategy-decision.v1"
FILING_TOPOLOGY_SCHEMA_V1 = "lukart.cirp.filing-topology-decision.v1"
FILING_PLAN_SCHEMA_V1 = "lukart.cirp.filing-plan.v1"
PREFLIGHT_CHECK_SCHEMA_V1 = "lukart.cirp.preflight-check.v1"
PREFLIGHT_RESULT_SCHEMA_V1 = "lukart.cirp.preflight-result.v1"


class CIRPContractError(P3ContractError):
    """Fail-closed CIRP boundary violation."""


class DocumentKind(StrEnum):
    DECISION = "DECISION"
    ORDER = "ORDER"
    NOTICE = "NOTICE"
    SUMMONS = "SUMMONS"
    REQUEST = "REQUEST"
    CLAIM = "CLAIM"
    RESPONSE = "RESPONSE"
    JUDGMENT = "JUDGMENT"
    ENFORCEMENT_NOTICE = "ENFORCEMENT_NOTICE"
    INFORMATION = "INFORMATION"
    CORRESPONDENCE = "CORRESPONDENCE"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class AssessmentStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PROVISIONAL = "PROVISIONAL"
    UNKNOWN = "UNKNOWN"
    UNRESOLVED = "UNRESOLVED"


class ProceduralStage(StrEnum):
    PRE_PROCEEDING = "PRE_PROCEEDING"
    FIRST_INSTANCE = "FIRST_INSTANCE"
    RESPONSE_REQUIRED = "RESPONSE_REQUIRED"
    APPEAL = "APPEAL"
    COMPLAINT = "COMPLAINT"
    COURT_REVIEW = "COURT_REVIEW"
    ENFORCEMENT = "ENFORCEMENT"
    POST_JUDGMENT = "POST_JUDGMENT"
    EXTRAORDINARY_REMEDY = "EXTRAORDINARY_REMEDY"
    INFORMATION_ONLY = "INFORMATION_ONLY"
    UNKNOWN = "UNKNOWN"


class ServiceStatus(StrEnum):
    VERIFIED = "VERIFIED"
    USER_REPORTED = "USER_REPORTED"
    DOCUMENT_STATED = "DOCUMENT_STATED"
    MISSING = "MISSING"
    CONFLICTING = "CONFLICTING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DeadlineStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PROVISIONAL = "PROVISIONAL"
    MISSING_INPUT = "MISSING_INPUT"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    UNKNOWN_RULE = "UNKNOWN_RULE"
    EXPIRED = "EXPIRED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RulePackStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"
    UNKNOWN = "UNKNOWN"


class LegalSourceVerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PROVISIONAL = "PROVISIONAL"
    UNKNOWN = "UNKNOWN"


class RemedyAdmissibility(StrEnum):
    VERIFIED_AVAILABLE = "VERIFIED_AVAILABLE"
    PROVISIONALLY_AVAILABLE = "PROVISIONALLY_AVAILABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    UNKNOWN = "UNKNOWN"


class EvidenceCategory(StrEnum):
    DEADLINE_CRITICAL = "DEADLINE_CRITICAL"
    ADMISSIBILITY_CRITICAL = "ADMISSIBILITY_CRITICAL"
    MERITS_CRITICAL = "MERITS_CRITICAL"
    PROCEDURAL = "PROCEDURAL"
    SUPPORTING = "SUPPORTING"
    OPTIONAL = "OPTIONAL"


class EvidenceImportance(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EvidenceRequirementStatus(StrEnum):
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    CONFLICTING = "CONFLICTING"
    STALE = "STALE"
    UNVERIFIED = "UNVERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DeadlineSafety(StrEnum):
    SAFE = "SAFE"
    RISK = "RISK"
    UNKNOWN = "UNKNOWN"


class MeritsStrength(StrEnum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    UNKNOWN = "UNKNOWN"


class VerificationLevel(StrEnum):
    VERIFIED = "VERIFIED"
    PROVISIONAL = "PROVISIONAL"
    UNKNOWN = "UNKNOWN"


class StrategyDecisionStatus(StrEnum):
    RECOMMENDED = "RECOMMENDED"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"
    DECISION_REQUIRED = "DECISION_REQUIRED"
    NO_SAFE_OPTION = "NO_SAFE_OPTION"
    ABSTAIN = "ABSTAIN"


class FilingTopologyStatus(StrEnum):
    SINGLE_FILING_SAFE = "SINGLE_FILING_SAFE"
    MULTIPLE_FILINGS_REQUIRED = "MULTIPLE_FILINGS_REQUIRED"
    CONSOLIDATION_UNCERTAIN = "CONSOLIDATION_UNCERTAIN"
    NO_FILING_REQUIRED = "NO_FILING_REQUIRED"


class PreflightSeverity(StrEnum):
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class PreflightStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PreflightFinalStatus(StrEnum):
    FILING_READY = "FILING_READY"
    NOT_READY = "NOT_READY"
    ABSTAIN = "ABSTAIN"


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


def _unique_nonblank(values: Sequence[str], *, field_name: str) -> tuple[str, ...]:
    normalized = tuple(_require_nonblank(item, field_name=field_name) for item in values)
    if len(normalized) != len(set(normalized)):
        raise CIRPContractError(f"{field_name} cannot contain duplicates")
    return normalized


def _normalize_optional_digest(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    try:
        return require_hex_digest(value, field_name=field_name)
    except P3ContractError as exc:
        raise CIRPContractError(str(exc)) from exc


def _normalize_digest(value: str, *, field_name: str) -> str:
    result = _normalize_optional_digest(value, field_name=field_name)
    if result is None:
        raise CIRPContractError(f"{field_name} is required")
    return result


def _freeze_string_mapping(
    value: Mapping[str, str], *, field_name: str
) -> Mapping[str, str]:
    normalized: dict[str, str] = {}
    for key, item in value.items():
        normalized_key = _require_nonblank(key, field_name=f"{field_name} key")
        normalized_value = _require_nonblank(item, field_name=f"{field_name} value")
        if normalized_key in normalized:
            raise CIRPContractError(f"{field_name} contains duplicate keys")
        normalized[normalized_key] = normalized_value
    return MappingProxyType(dict(sorted(normalized.items())))


def _require_aware_datetime(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CIRPContractError(f"{field_name} must be timezone-aware")
    return value


def _canonical_date(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _canonical_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _canonical_time(value: time | None) -> str | None:
    return value.isoformat() if value is not None else None


class _DigestibleContract:
    def canonical_dict(self) -> dict[str, object]:
        raise NotImplementedError

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class CIRPRunIdentity(_DigestibleContract):
    case_id: CaseId
    input_evidence_ids: tuple[str, ...]
    input_event_ids: tuple[str, ...]
    rule_pack_ids: tuple[str, ...]
    rule_pack_digest: str
    policy_identity: str
    runtime_identity: str
    evaluation_time: datetime
    configuration_digest: str
    model_identity: str | None = None
    cirp_version: str = CIRP_VERSION_V1
    schema: str = CIRP_RUN_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CIRP_RUN_SCHEMA_V1 or self.cirp_version != CIRP_VERSION_V1:
            raise CIRPContractError("unsupported CIRP run schema/version")
        object.__setattr__(
            self,
            "input_evidence_ids",
            _unique_nonblank(self.input_evidence_ids, field_name="input_evidence_ids"),
        )
        object.__setattr__(
            self,
            "input_event_ids",
            _unique_nonblank(self.input_event_ids, field_name="input_event_ids"),
        )
        object.__setattr__(
            self,
            "rule_pack_ids",
            _unique_nonblank(self.rule_pack_ids, field_name="rule_pack_ids"),
        )
        if not self.input_evidence_ids and not self.input_event_ids:
            raise CIRPContractError("CIRP run requires evidence or event input")
        object.__setattr__(
            self,
            "rule_pack_digest",
            _normalize_digest(self.rule_pack_digest, field_name="rule_pack_digest"),
        )
        object.__setattr__(
            self,
            "configuration_digest",
            _normalize_digest(self.configuration_digest, field_name="configuration_digest"),
        )
        object.__setattr__(
            self,
            "policy_identity",
            _require_nonblank(self.policy_identity, field_name="policy_identity"),
        )
        object.__setattr__(
            self,
            "runtime_identity",
            _require_nonblank(self.runtime_identity, field_name="runtime_identity"),
        )
        object.__setattr__(
            self,
            "model_identity",
            _optional_nonblank(self.model_identity, field_name="model_identity"),
        )
        _require_aware_datetime(self.evaluation_time, field_name="evaluation_time")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "cirp_version": self.cirp_version,
            "case_id": self.case_id.canonical_dict(),
            "input_evidence_ids": list(self.input_evidence_ids),
            "input_event_ids": list(self.input_event_ids),
            "rule_pack_ids": list(self.rule_pack_ids),
            "rule_pack_digest": self.rule_pack_digest,
            "policy_identity": self.policy_identity,
            "runtime_identity": self.runtime_identity,
            "model_identity": self.model_identity,
            "evaluation_time": _canonical_datetime(self.evaluation_time),
            "configuration_digest": self.configuration_digest,
        }


@dataclass(frozen=True, slots=True)
class DocumentAssessment(_DigestibleContract):
    document_id: str
    source_evidence_id: str
    document_kind: DocumentKind
    issuer: str | None
    recipient: str | None
    document_date: date | None
    case_reference: str | None
    subject: str | None
    operative_content: tuple[str, ...]
    requested_actions: tuple[str, ...]
    stated_deadlines: tuple[str, ...]
    classification_status: AssessmentStatus
    evidence_refs: tuple[str, ...]
    open_questions: tuple[str, ...]
    schema: str = DOCUMENT_ASSESSMENT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != DOCUMENT_ASSESSMENT_SCHEMA_V1:
            raise CIRPContractError("unsupported document assessment schema")
        object.__setattr__(
            self, "document_id", _require_nonblank(self.document_id, field_name="document_id")
        )
        object.__setattr__(
            self,
            "source_evidence_id",
            _require_nonblank(self.source_evidence_id, field_name="source_evidence_id"),
        )
        for field_name in ("issuer", "recipient", "case_reference", "subject"):
            object.__setattr__(
                self,
                field_name,
                _optional_nonblank(getattr(self, field_name), field_name=field_name),
            )
        for field_name in (
            "operative_content",
            "requested_actions",
            "stated_deadlines",
            "evidence_refs",
            "open_questions",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique_nonblank(getattr(self, field_name), field_name=field_name),
            )
        if self.classification_status is AssessmentStatus.VERIFIED:
            if self.document_kind is DocumentKind.UNKNOWN:
                raise CIRPContractError("VERIFIED document classification cannot be UNKNOWN")
            if not self.evidence_refs:
                raise CIRPContractError("VERIFIED document classification requires evidence_refs")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "document_id": self.document_id,
            "source_evidence_id": self.source_evidence_id,
            "document_kind": self.document_kind.value,
            "issuer": self.issuer,
            "recipient": self.recipient,
            "document_date": _canonical_date(self.document_date),
            "case_reference": self.case_reference,
            "subject": self.subject,
            "operative_content": list(self.operative_content),
            "requested_actions": list(self.requested_actions),
            "stated_deadlines": list(self.stated_deadlines),
            "classification_status": self.classification_status.value,
            "evidence_refs": list(self.evidence_refs),
            "open_questions": list(self.open_questions),
        }


@dataclass(frozen=True, slots=True)
class ProceduralAssessment(_DigestibleContract):
    jurisdiction: str
    procedure_family: str
    procedural_stage: ProceduralStage
    issuing_authority: str | None
    competent_authority: str | None
    review_authority: str | None
    filing_authority: str | None
    filing_via: str | None
    procedural_subject: str
    available_action_required: bool | None
    status: AssessmentStatus
    supporting_rules: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    unresolved: tuple[str, ...]
    schema: str = PROCEDURAL_ASSESSMENT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != PROCEDURAL_ASSESSMENT_SCHEMA_V1:
            raise CIRPContractError("unsupported procedural assessment schema")
        for field_name in ("jurisdiction", "procedure_family", "procedural_subject"):
            object.__setattr__(
                self,
                field_name,
                _require_nonblank(getattr(self, field_name), field_name=field_name),
            )
        for field_name in (
            "issuing_authority",
            "competent_authority",
            "review_authority",
            "filing_authority",
            "filing_via",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_nonblank(getattr(self, field_name), field_name=field_name),
            )
        for field_name in ("supporting_rules", "evidence_refs", "unresolved"):
            object.__setattr__(
                self,
                field_name,
                _unique_nonblank(getattr(self, field_name), field_name=field_name),
            )
        if self.status is AssessmentStatus.VERIFIED:
            if self.procedural_stage is ProceduralStage.UNKNOWN:
                raise CIRPContractError("VERIFIED procedural stage cannot be UNKNOWN")
            if not self.evidence_refs:
                raise CIRPContractError("VERIFIED procedural assessment requires evidence_refs")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "jurisdiction": self.jurisdiction,
            "procedure_family": self.procedure_family,
            "procedural_stage": self.procedural_stage.value,
            "issuing_authority": self.issuing_authority,
            "competent_authority": self.competent_authority,
            "review_authority": self.review_authority,
            "filing_authority": self.filing_authority,
            "filing_via": self.filing_via,
            "procedural_subject": self.procedural_subject,
            "available_action_required": self.available_action_required,
            "status": self.status.value,
            "supporting_rules": list(self.supporting_rules),
            "evidence_refs": list(self.evidence_refs),
            "unresolved": list(self.unresolved),
        }


@dataclass(frozen=True, slots=True)
class ServiceAssessment(_DigestibleContract):
    service_required: bool | None
    service_method: str | None
    service_date: date | None
    service_time: time | None
    evidence_refs: tuple[str, ...]
    source_status: ServiceStatus
    conflicting_dates: tuple[date, ...]
    assessment_status: ServiceStatus
    schema: str = SERVICE_ASSESSMENT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != SERVICE_ASSESSMENT_SCHEMA_V1:
            raise CIRPContractError("unsupported service assessment schema")
        object.__setattr__(
            self,
            "service_method",
            _optional_nonblank(self.service_method, field_name="service_method"),
        )
        object.__setattr__(
            self, "evidence_refs", _unique_nonblank(self.evidence_refs, field_name="evidence_refs")
        )
        if len(set(self.conflicting_dates)) != len(self.conflicting_dates):
            raise CIRPContractError("conflicting_dates cannot contain duplicates")
        if self.assessment_status is ServiceStatus.VERIFIED:
            if self.service_date is None or not self.evidence_refs:
                raise CIRPContractError("VERIFIED service requires date and evidence")
            if self.conflicting_dates:
                raise CIRPContractError("VERIFIED service cannot retain conflicting dates")
        if self.assessment_status is ServiceStatus.CONFLICTING:
            if self.service_date is not None or len(self.conflicting_dates) < 2:
                raise CIRPContractError(
                    "CONFLICTING service requires >=2 dates and no settled date"
                )
        if self.assessment_status is ServiceStatus.MISSING and self.service_date is not None:
            raise CIRPContractError("MISSING service cannot have service_date")
        if self.assessment_status is ServiceStatus.NOT_APPLICABLE:
            if self.service_required is not False or self.service_date is not None:
                raise CIRPContractError("NOT_APPLICABLE service requires service_required=False")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "service_required": self.service_required,
            "service_method": self.service_method,
            "service_date": _canonical_date(self.service_date),
            "service_time": _canonical_time(self.service_time),
            "evidence_refs": list(self.evidence_refs),
            "source_status": self.source_status.value,
            "conflicting_dates": [item.isoformat() for item in self.conflicting_dates],
            "assessment_status": self.assessment_status.value,
        }


@dataclass(frozen=True, slots=True)
class LegalSourceRef(_DigestibleContract):
    source_id: str
    jurisdiction: str
    authority_type: str
    formal_citation: str
    source_uri: str
    source_digest: str | None
    effective_from: date
    effective_until: date | None
    retrieved_at: datetime
    verification_status: LegalSourceVerificationStatus
    schema: str = LEGAL_SOURCE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != LEGAL_SOURCE_SCHEMA_V1:
            raise CIRPContractError("unsupported legal source schema")
        for field_name in (
            "source_id",
            "jurisdiction",
            "authority_type",
            "formal_citation",
            "source_uri",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_nonblank(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self,
            "source_digest",
            _normalize_optional_digest(self.source_digest, field_name="source_digest"),
        )
        _require_aware_datetime(self.retrieved_at, field_name="retrieved_at")
        if self.effective_until is not None and self.effective_until < self.effective_from:
            raise CIRPContractError("legal source effective_until precedes effective_from")
        if (
            self.verification_status is LegalSourceVerificationStatus.VERIFIED
            and self.source_digest is None
        ):
            raise CIRPContractError("VERIFIED legal source requires source_digest")

    def effective_on(self, value: date) -> bool:
        return self.effective_from <= value and (
            self.effective_until is None or value <= self.effective_until
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source_id": self.source_id,
            "jurisdiction": self.jurisdiction,
            "authority_type": self.authority_type,
            "formal_citation": self.formal_citation,
            "source_uri": self.source_uri,
            "source_digest": self.source_digest,
            "effective_from": self.effective_from.isoformat(),
            "effective_until": _canonical_date(self.effective_until),
            "retrieved_at": _canonical_datetime(self.retrieved_at),
            "verification_status": self.verification_status.value,
        }


@dataclass(frozen=True, slots=True)
class ProceduralRulePack(_DigestibleContract):
    pack_id: str
    version: str
    jurisdiction: str
    procedure_family: str
    effective_from: date
    effective_until: date | None
    source_set: tuple[LegalSourceRef, ...]
    source_set_digest: str
    deadline_rules: tuple[str, ...]
    remedy_rules: tuple[str, ...]
    routing_rules: tuple[str, ...]
    formal_requirement_rules: tuple[str, ...]
    calendar_rules: tuple[str, ...]
    status: RulePackStatus
    schema: str = RULE_PACK_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != RULE_PACK_SCHEMA_V1:
            raise CIRPContractError("unsupported procedural rule pack schema")
        for field_name in ("pack_id", "version", "jurisdiction", "procedure_family"):
            object.__setattr__(
                self,
                field_name,
                _require_nonblank(getattr(self, field_name), field_name=field_name),
            )
        if self.effective_until is not None and self.effective_until < self.effective_from:
            raise CIRPContractError("rule pack effective_until precedes effective_from")
        source_ids = tuple(item.source_id for item in self.source_set)
        if len(source_ids) != len(set(source_ids)):
            raise CIRPContractError("source_set cannot contain duplicate source_id values")
        expected_digest = content_digest([item.canonical_dict() for item in self.source_set])
        normalized_digest = _normalize_digest(
            self.source_set_digest, field_name="source_set_digest"
        )
        if normalized_digest != expected_digest:
            raise CIRPContractError("source_set_digest mismatch")
        object.__setattr__(self, "source_set_digest", normalized_digest)
        for field_name in (
            "deadline_rules",
            "remedy_rules",
            "routing_rules",
            "formal_requirement_rules",
            "calendar_rules",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique_nonblank(getattr(self, field_name), field_name=field_name),
            )
        if self.status is RulePackStatus.ACTIVE and not self.source_set:
            raise CIRPContractError("ACTIVE rule pack requires a legal source set")

    @classmethod
    def build(
        cls,
        *,
        pack_id: str,
        version: str,
        jurisdiction: str,
        procedure_family: str,
        effective_from: date,
        effective_until: date | None,
        source_set: tuple[LegalSourceRef, ...],
        deadline_rules: tuple[str, ...] = (),
        remedy_rules: tuple[str, ...] = (),
        routing_rules: tuple[str, ...] = (),
        formal_requirement_rules: tuple[str, ...] = (),
        calendar_rules: tuple[str, ...] = (),
        status: RulePackStatus = RulePackStatus.DRAFT,
    ) -> ProceduralRulePack:
        return cls(
            pack_id=pack_id,
            version=version,
            jurisdiction=jurisdiction,
            procedure_family=procedure_family,
            effective_from=effective_from,
            effective_until=effective_until,
            source_set=source_set,
            source_set_digest=content_digest([item.canonical_dict() for item in source_set]),
            deadline_rules=deadline_rules,
            remedy_rules=remedy_rules,
            routing_rules=routing_rules,
            formal_requirement_rules=formal_requirement_rules,
            calendar_rules=calendar_rules,
            status=status,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "pack_id": self.pack_id,
            "version": self.version,
            "jurisdiction": self.jurisdiction,
            "procedure_family": self.procedure_family,
            "effective_from": self.effective_from.isoformat(),
            "effective_until": _canonical_date(self.effective_until),
            "source_set": [item.canonical_dict() for item in self.source_set],
            "source_set_digest": self.source_set_digest,
            "deadline_rules": list(self.deadline_rules),
            "remedy_rules": list(self.remedy_rules),
            "routing_rules": list(self.routing_rules),
            "formal_requirement_rules": list(self.formal_requirement_rules),
            "calendar_rules": list(self.calendar_rules),
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True)
class DeadlineAssessment(_DigestibleContract):
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
    legal_deadline: date | None
    safe_internal_deadline: date | None
    status: DeadlineStatus
    blocking_questions: tuple[str, ...]
    schema: str = DEADLINE_ASSESSMENT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != DEADLINE_ASSESSMENT_SCHEMA_V1:
            raise CIRPContractError("unsupported deadline assessment schema")
        object.__setattr__(
            self, "deadline_id", _require_nonblank(self.deadline_id, field_name="deadline_id")
        )
        object.__setattr__(
            self, "trigger_type", _require_nonblank(self.trigger_type, field_name="trigger_type")
        )
        for field_name in (
            "trigger_evidence",
            "rule_pack_id",
            "rule_id",
            "rule_version",
            "duration_unit",
            "calculation_method",
            "calendar_profile",
            "timezone",
        ):
            object.__setattr__(
                self,
                field_name,
                _optional_nonblank(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self,
            "legal_source_refs",
            _unique_nonblank(self.legal_source_refs, field_name="legal_source_refs"),
        )
        object.__setattr__(
            self,
            "blocking_questions",
            _unique_nonblank(self.blocking_questions, field_name="blocking_questions"),
        )
        if self.duration_value is not None and self.duration_value < 0:
            raise CIRPContractError("duration_value cannot be negative")
        if self.safe_internal_deadline is not None:
            if self.legal_deadline is None:
                raise CIRPContractError("safe_internal_deadline requires legal_deadline")
            if self.safe_internal_deadline > self.legal_deadline:
                raise CIRPContractError("safe_internal_deadline cannot exceed legal_deadline")
        if self.status is DeadlineStatus.VERIFIED:
            required = {
                "trigger_date": self.trigger_date,
                "trigger_evidence": self.trigger_evidence,
                "rule_pack_id": self.rule_pack_id,
                "rule_id": self.rule_id,
                "rule_version": self.rule_version,
                "effective_law_date": self.effective_law_date,
                "legal_deadline": self.legal_deadline,
            }
            missing = sorted(name for name, value in required.items() if value is None)
            if missing:
                raise CIRPContractError("VERIFIED deadline missing: " + ", ".join(missing))
            if not self.legal_source_refs:
                raise CIRPContractError("VERIFIED deadline requires legal_source_refs")
            if self.blocking_questions:
                raise CIRPContractError("VERIFIED deadline cannot contain blocking_questions")
        if (
            self.status
            in {
                DeadlineStatus.MISSING_INPUT,
                DeadlineStatus.UNKNOWN_RULE,
                DeadlineStatus.CONFLICTING_EVIDENCE,
            }
            and not self.blocking_questions
        ):
            raise CIRPContractError(f"{self.status.value} deadline requires blocking_questions")
        if self.status is DeadlineStatus.NOT_APPLICABLE and self.legal_deadline is not None:
            raise CIRPContractError("NOT_APPLICABLE deadline cannot contain legal_deadline")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "deadline_id": self.deadline_id,
            "trigger_type": self.trigger_type,
            "trigger_date": _canonical_date(self.trigger_date),
            "trigger_evidence": self.trigger_evidence,
            "rule_pack_id": self.rule_pack_id,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "legal_source_refs": list(self.legal_source_refs),
            "effective_law_date": _canonical_date(self.effective_law_date),
            "duration_value": self.duration_value,
            "duration_unit": self.duration_unit,
            "calculation_method": self.calculation_method,
            "calendar_profile": self.calendar_profile,
            "timezone": self.timezone,
            "legal_deadline": _canonical_date(self.legal_deadline),
            "safe_internal_deadline": _canonical_date(self.safe_internal_deadline),
            "status": self.status.value,
            "blocking_questions": list(self.blocking_questions),
        }


@dataclass(frozen=True, slots=True)
class RemedyOption(_DigestibleContract):
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
    admissibility_status: RemedyAdmissibility
    blockers: tuple[str, ...]
    schema: str = REMEDY_OPTION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != REMEDY_OPTION_SCHEMA_V1:
            raise CIRPContractError("unsupported remedy option schema")
        for field_name in ("remedy_id", "remedy_type", "target_authority", "filing_authority"):
            object.__setattr__(
                self,
                field_name,
                _require_nonblank(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self, "filing_via", _optional_nonblank(self.filing_via, field_name="filing_via")
        )
        object.__setattr__(
            self, "deadline_id", _optional_nonblank(self.deadline_id, field_name="deadline_id")
        )
        for field_name in (
            "applicable_rule_ids",
            "formal_requirements",
            "required_evidence",
            "preserves_options",
            "waives_options",
            "blockers",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique_nonblank(getattr(self, field_name), field_name=field_name),
            )
        if self.admissibility_status is RemedyAdmissibility.VERIFIED_AVAILABLE:
            if not self.applicable_rule_ids:
                raise CIRPContractError("VERIFIED_AVAILABLE remedy requires applicable_rule_ids")
            if self.blockers:
                raise CIRPContractError("VERIFIED_AVAILABLE remedy cannot contain blockers")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "remedy_id": self.remedy_id,
            "remedy_type": self.remedy_type,
            "target_authority": self.target_authority,
            "filing_authority": self.filing_authority,
            "filing_via": self.filing_via,
            "applicable_rule_ids": list(self.applicable_rule_ids),
            "deadline_id": self.deadline_id,
            "formal_requirements": list(self.formal_requirements),
            "required_evidence": list(self.required_evidence),
            "preserves_options": list(self.preserves_options),
            "waives_options": list(self.waives_options),
            "admissibility_status": self.admissibility_status.value,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True, slots=True)
class EvidenceRequirement(_DigestibleContract):
    requirement_id: str
    description: str
    category: EvidenceCategory
    importance: EvidenceImportance
    required_for: tuple[str, ...]
    expected_evidence_kind: str
    status: EvidenceRequirementStatus
    evidence_refs: tuple[str, ...]
    schema: str = EVIDENCE_REQUIREMENT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != EVIDENCE_REQUIREMENT_SCHEMA_V1:
            raise CIRPContractError("unsupported evidence requirement schema")
        for field_name in ("requirement_id", "description", "expected_evidence_kind"):
            object.__setattr__(
                self,
                field_name,
                _require_nonblank(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self, "required_for", _unique_nonblank(self.required_for, field_name="required_for")
        )
        object.__setattr__(
            self, "evidence_refs", _unique_nonblank(self.evidence_refs, field_name="evidence_refs")
        )
        if self.status is EvidenceRequirementStatus.PRESENT and not self.evidence_refs:
            raise CIRPContractError("PRESENT evidence requirement requires evidence_refs")
        if self.status is EvidenceRequirementStatus.MISSING and self.evidence_refs:
            raise CIRPContractError("MISSING evidence requirement cannot contain evidence_refs")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "requirement_id": self.requirement_id,
            "description": self.description,
            "category": self.category.value,
            "importance": self.importance.value,
            "required_for": list(self.required_for),
            "expected_evidence_kind": self.expected_evidence_kind,
            "status": self.status.value,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True, slots=True)
class StrategyOption(_DigestibleContract):
    strategy_id: str
    objective: str
    remedy_ids: tuple[str, ...]
    proposed_actions: tuple[str, ...]
    required_evidence: tuple[str, ...]
    deadline_safety: DeadlineSafety
    admissibility: VerificationLevel
    merits_strength: MeritsStrength
    preserves_options: tuple[str, ...]
    closes_options: tuple[str, ...]
    risks: tuple[str, ...]
    advantages: tuple[str, ...]
    disadvantages: tuple[str, ...]
    unresolved: tuple[str, ...]
    schema: str = STRATEGY_OPTION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != STRATEGY_OPTION_SCHEMA_V1:
            raise CIRPContractError("unsupported strategy option schema")
        object.__setattr__(
            self, "strategy_id", _require_nonblank(self.strategy_id, field_name="strategy_id")
        )
        object.__setattr__(
            self, "objective", _require_nonblank(self.objective, field_name="objective")
        )
        for field_name in (
            "remedy_ids",
            "proposed_actions",
            "required_evidence",
            "preserves_options",
            "closes_options",
            "risks",
            "advantages",
            "disadvantages",
            "unresolved",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique_nonblank(getattr(self, field_name), field_name=field_name),
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "strategy_id": self.strategy_id,
            "objective": self.objective,
            "remedy_ids": list(self.remedy_ids),
            "proposed_actions": list(self.proposed_actions),
            "required_evidence": list(self.required_evidence),
            "deadline_safety": self.deadline_safety.value,
            "admissibility": self.admissibility.value,
            "merits_strength": self.merits_strength.value,
            "preserves_options": list(self.preserves_options),
            "closes_options": list(self.closes_options),
            "risks": list(self.risks),
            "advantages": list(self.advantages),
            "disadvantages": list(self.disadvantages),
            "unresolved": list(self.unresolved),
        }


@dataclass(frozen=True, slots=True)
class StrategyDecision(_DigestibleContract):
    selected_strategy_id: str | None
    decision_status: StrategyDecisionStatus
    rationale: str
    rejected_strategy_ids: tuple[str, ...]
    rejection_reasons: Mapping[str, str]
    decisive_evidence: tuple[str, ...]
    decisive_rules: tuple[str, ...]
    unresolved_risks: tuple[str, ...]
    schema: str = STRATEGY_DECISION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != STRATEGY_DECISION_SCHEMA_V1:
            raise CIRPContractError("unsupported strategy decision schema")
        object.__setattr__(
            self,
            "selected_strategy_id",
            _optional_nonblank(self.selected_strategy_id, field_name="selected_strategy_id"),
        )
        object.__setattr__(
            self, "rationale", _require_nonblank(self.rationale, field_name="rationale")
        )
        object.__setattr__(
            self,
            "rejected_strategy_ids",
            _unique_nonblank(self.rejected_strategy_ids, field_name="rejected_strategy_ids"),
        )
        object.__setattr__(
            self,
            "rejection_reasons",
            _freeze_string_mapping(self.rejection_reasons, field_name="rejection_reasons"),
        )
        object.__setattr__(
            self,
            "decisive_evidence",
            _unique_nonblank(self.decisive_evidence, field_name="decisive_evidence"),
        )
        object.__setattr__(
            self,
            "decisive_rules",
            _unique_nonblank(self.decisive_rules, field_name="decisive_rules"),
        )
        object.__setattr__(
            self,
            "unresolved_risks",
            _unique_nonblank(self.unresolved_risks, field_name="unresolved_risks"),
        )
        missing_reasons = sorted(set(self.rejected_strategy_ids) - set(self.rejection_reasons))
        if missing_reasons:
            raise CIRPContractError(
                "rejected strategies missing reasons: " + ", ".join(missing_reasons)
            )
        extra_reasons = sorted(set(self.rejection_reasons) - set(self.rejected_strategy_ids))
        if extra_reasons:
            raise CIRPContractError(
                "rejection reasons without rejected strategy: " + ", ".join(extra_reasons)
            )
        if self.decision_status is StrategyDecisionStatus.RECOMMENDED:
            if self.selected_strategy_id is None:
                raise CIRPContractError("RECOMMENDED decision requires selected_strategy_id")
            if not self.decisive_evidence or not self.decisive_rules:
                raise CIRPContractError("RECOMMENDED decision requires decisive evidence and rules")
            if self.selected_strategy_id in self.rejected_strategy_ids:
                raise CIRPContractError("selected strategy cannot also be rejected")
        elif self.selected_strategy_id is not None:
            raise CIRPContractError("non-RECOMMENDED decision cannot select a strategy")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "selected_strategy_id": self.selected_strategy_id,
            "decision_status": self.decision_status.value,
            "rationale": self.rationale,
            "rejected_strategy_ids": list(self.rejected_strategy_ids),
            "rejection_reasons": dict(self.rejection_reasons),
            "decisive_evidence": list(self.decisive_evidence),
            "decisive_rules": list(self.decisive_rules),
            "unresolved_risks": list(self.unresolved_risks),
        }


@dataclass(frozen=True, slots=True)
class FilingTopologyDecision(_DigestibleContract):
    status: FilingTopologyStatus
    filing_count: int
    combined_remedies: tuple[str, ...]
    separated_remedies: tuple[str, ...]
    rationale: str
    blockers: tuple[str, ...]
    schema: str = FILING_TOPOLOGY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != FILING_TOPOLOGY_SCHEMA_V1:
            raise CIRPContractError("unsupported filing topology schema")
        if self.filing_count < 0:
            raise CIRPContractError("filing_count cannot be negative")
        object.__setattr__(
            self,
            "combined_remedies",
            _unique_nonblank(self.combined_remedies, field_name="combined_remedies"),
        )
        object.__setattr__(
            self,
            "separated_remedies",
            _unique_nonblank(self.separated_remedies, field_name="separated_remedies"),
        )
        object.__setattr__(
            self, "rationale", _require_nonblank(self.rationale, field_name="rationale")
        )
        object.__setattr__(self, "blockers", _unique_nonblank(self.blockers, field_name="blockers"))
        if set(self.combined_remedies) & set(self.separated_remedies):
            raise CIRPContractError("a remedy cannot be both combined and separated")
        if self.status is FilingTopologyStatus.SINGLE_FILING_SAFE:
            if self.filing_count != 1 or self.blockers:
                raise CIRPContractError("SINGLE_FILING_SAFE requires one filing and no blockers")
        if self.status is FilingTopologyStatus.MULTIPLE_FILINGS_REQUIRED and self.filing_count < 2:
            raise CIRPContractError("MULTIPLE_FILINGS_REQUIRED requires at least two filings")
        if self.status is FilingTopologyStatus.CONSOLIDATION_UNCERTAIN and not self.blockers:
            raise CIRPContractError("CONSOLIDATION_UNCERTAIN requires blockers")
        if self.status is FilingTopologyStatus.NO_FILING_REQUIRED:
            if self.filing_count != 0 or self.combined_remedies or self.separated_remedies:
                raise CIRPContractError("NO_FILING_REQUIRED requires zero filing work")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "status": self.status.value,
            "filing_count": self.filing_count,
            "combined_remedies": list(self.combined_remedies),
            "separated_remedies": list(self.separated_remedies),
            "rationale": self.rationale,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True, slots=True)
class FilingPlan(_DigestibleContract):
    filing_id: str
    filing_type: str
    target_authority: str
    filing_authority: str
    filing_via: str | None
    objective: str
    requests: tuple[str, ...]
    allegations_or_grounds: tuple[str, ...]
    remedy_ids: tuple[str, ...]
    rule_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    attachment_requirements: tuple[str, ...]
    signature_requirements: tuple[str, ...]
    copy_requirements: tuple[str, ...]
    deadline_id: str | None
    delivery_method: str
    topology_status: FilingTopologyStatus
    schema: str = FILING_PLAN_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != FILING_PLAN_SCHEMA_V1:
            raise CIRPContractError("unsupported filing plan schema")
        for field_name in (
            "filing_id",
            "filing_type",
            "target_authority",
            "filing_authority",
            "objective",
            "delivery_method",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_nonblank(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self, "filing_via", _optional_nonblank(self.filing_via, field_name="filing_via")
        )
        object.__setattr__(
            self, "deadline_id", _optional_nonblank(self.deadline_id, field_name="deadline_id")
        )
        for field_name in (
            "requests",
            "allegations_or_grounds",
            "remedy_ids",
            "rule_refs",
            "evidence_refs",
            "attachment_requirements",
            "signature_requirements",
            "copy_requirements",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique_nonblank(getattr(self, field_name), field_name=field_name),
            )
        if not self.requests:
            raise CIRPContractError("filing plan requires at least one request")
        if not self.remedy_ids:
            raise CIRPContractError("filing plan requires remedy_ids")
        if not self.rule_refs:
            raise CIRPContractError("filing plan requires rule_refs")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "filing_id": self.filing_id,
            "filing_type": self.filing_type,
            "target_authority": self.target_authority,
            "filing_authority": self.filing_authority,
            "filing_via": self.filing_via,
            "objective": self.objective,
            "requests": list(self.requests),
            "allegations_or_grounds": list(self.allegations_or_grounds),
            "remedy_ids": list(self.remedy_ids),
            "rule_refs": list(self.rule_refs),
            "evidence_refs": list(self.evidence_refs),
            "attachment_requirements": list(self.attachment_requirements),
            "signature_requirements": list(self.signature_requirements),
            "copy_requirements": list(self.copy_requirements),
            "deadline_id": self.deadline_id,
            "delivery_method": self.delivery_method,
            "topology_status": self.topology_status.value,
        }


@dataclass(frozen=True, slots=True)
class PreflightCheck(_DigestibleContract):
    check_id: str
    severity: PreflightSeverity
    status: PreflightStatus
    reason: str
    evidence_refs: tuple[str, ...]
    schema: str = PREFLIGHT_CHECK_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != PREFLIGHT_CHECK_SCHEMA_V1:
            raise CIRPContractError("unsupported preflight check schema")
        object.__setattr__(
            self, "check_id", _require_nonblank(self.check_id, field_name="check_id")
        )
        object.__setattr__(self, "reason", _require_nonblank(self.reason, field_name="reason"))
        object.__setattr__(
            self, "evidence_refs", _unique_nonblank(self.evidence_refs, field_name="evidence_refs")
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "check_id": self.check_id,
            "severity": self.severity.value,
            "status": self.status.value,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True, slots=True)
class PreflightResult(_DigestibleContract):
    filing_id: str
    checks: tuple[PreflightCheck, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    final_status: PreflightFinalStatus
    schema: str = PREFLIGHT_RESULT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != PREFLIGHT_RESULT_SCHEMA_V1:
            raise CIRPContractError("unsupported preflight result schema")
        object.__setattr__(
            self, "filing_id", _require_nonblank(self.filing_id, field_name="filing_id")
        )
        check_ids = tuple(item.check_id for item in self.checks)
        if len(check_ids) != len(set(check_ids)):
            raise CIRPContractError("preflight checks cannot contain duplicate check_id values")
        object.__setattr__(self, "blockers", _unique_nonblank(self.blockers, field_name="blockers"))
        object.__setattr__(self, "warnings", _unique_nonblank(self.warnings, field_name="warnings"))
        critical_non_pass = tuple(
            item
            for item in self.checks
            if (
                item.severity is PreflightSeverity.CRITICAL
                and item.status is not PreflightStatus.PASS
            )
        )
        if self.final_status is PreflightFinalStatus.FILING_READY:
            if not self.checks:
                raise CIRPContractError("FILING_READY requires preflight checks")
            if self.blockers or critical_non_pass:
                raise CIRPContractError(
                    "FILING_READY requires all critical checks PASS and no blockers"
                )
        if self.blockers and self.final_status is PreflightFinalStatus.FILING_READY:
            raise CIRPContractError("blockers are incompatible with FILING_READY")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "filing_id": self.filing_id,
            "checks": [item.canonical_dict() for item in self.checks],
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "final_status": self.final_status.value,
        }


def canonical_contract_json(contract: _DigestibleContract) -> str:
    """Return deterministic canonical JSON for a CIRP boundary artifact."""

    return canonical_json(contract.canonical_dict())
