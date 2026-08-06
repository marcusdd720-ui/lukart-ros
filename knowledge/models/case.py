"""
Knowledge Operating System (KOS)

File: knowledge/models/case.py
Version: 1.3.9
Sprint: CASE-010

Compat for render/dossier: timeline, evidence, ordered_timeline(), has_signature().
LegalIssue between Fact and Law.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum, auto
from typing import Any
from uuid import uuid4


class CaseStatus(StrEnum):
    NEW = auto()
    INTAKE = auto()
    FACTS = auto()
    ANALYSIS = auto()
    DECISION = auto()
    DRAFT = auto()
    FILED = auto()
    CLOSED = auto()


class FactStatus(StrEnum):
    UNVERIFIED = auto()
    SUPPORTED = auto()
    DISPUTED = auto()
    REJECTED = auto()


class IssueStatus(StrEnum):
    OPEN = auto()
    ANALYZED = auto()
    DECIDED = auto()
    DROPPED = auto()


class DecisionKind(StrEnum):
    PROCEDURAL = auto()
    SUBSTANTIVE = auto()
    INTERIM = auto()
    CLOSING = auto()


class EvidenceWeight(StrEnum):
    PRIMARY = auto()
    SUPPORTING = auto()
    CONTEXT = auto()
    PARTY_STATEMENT = auto()
    HIGH = auto()
    MEDIUM = auto()
    LOW = auto()
    CRITICAL = auto()


class PartyStatus(StrEnum):
    ACTIVE = auto()
    PASSIVE = auto()
    UNKNOWN = auto()


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class Party:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    role: str = ""
    status: PartyStatus = PartyStatus.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)


class EvidenceItem:
    def __init__(self, **kwargs: Any) -> None:
        self.id: str = str(kwargs.pop("id", None) or uuid4())
        self.label: str = str(kwargs.pop("label", "") or "")
        self.title: str = str(kwargs.pop("title", "") or "")
        self.description: str = str(kwargs.pop("description", "") or "")
        self.source_ref: str = str(kwargs.pop("source_ref", "") or "")
        self.ref: str = str(kwargs.pop("ref", "") or "")
        self.source: str = str(kwargs.pop("source", "") or "")
        weight = kwargs.pop("weight", EvidenceWeight.SUPPORTING)
        if isinstance(weight, EvidenceWeight):
            self.weight = weight
        elif isinstance(weight, str):
            key = weight.upper().replace(" ", "_")
            self.weight = (
                EvidenceWeight[key]
                if key in EvidenceWeight.__members__
                else EvidenceWeight.SUPPORTING
            )
        else:
            self.weight = EvidenceWeight.SUPPORTING
        self.date = kwargs.pop("date", None)
        self.date_label: str = str(kwargs.pop("date_label", "") or "")
        self.kind: str = str(kwargs.pop("kind", "") or "")
        self.category: str = str(kwargs.pop("category", "") or "")
        self.path: str = str(kwargs.pop("path", "") or "")
        self.filename: str = str(kwargs.pop("filename", "") or "")
        self.metadata: dict[str, Any] = dict(kwargs.pop("metadata", None) or {})
        self.created_at = kwargs.pop("created_at", None) or _now()
        for key, value in kwargs.items():
            setattr(self, key, value)
        if not self.label and self.title:
            self.label = self.title
        if not self.title and self.label:
            self.title = self.label
        if not self.source_ref and self.ref:
            self.source_ref = self.ref
        if not self.ref and self.source_ref:
            self.ref = self.source_ref
        if not self.source_ref and self.source:
            self.source_ref = self.source

    def validate(self) -> None:
        name = (
            self.label
            or self.title
            or self.ref
            or self.source_ref
            or self.source
            or getattr(self, "name", "")
            or ""
        )
        if not str(name).strip():
            raise ValueError("EvidenceItem needs a name/label/title/ref/source")


class TimelineEvent:
    def __init__(self, **kwargs: Any) -> None:
        self.id: str = str(kwargs.pop("id", None) or uuid4())
        self.when = kwargs.pop("when", None)
        self.date = kwargs.pop("date", None)
        if self.when is None and self.date is not None:
            self.when = self.date
        if self.date is None and self.when is not None:
            self.date = self.when
        self.date_label: str = str(kwargs.pop("date_label", "") or "")
        self.label: str = str(kwargs.pop("label", "") or "")
        self.title: str = str(kwargs.pop("title", "") or "")
        self.event: str = str(kwargs.pop("event", "") or "")
        self.description: str = str(kwargs.pop("description", "") or "")
        self.summary: str = str(kwargs.pop("summary", "") or "")
        self.source: str = str(kwargs.pop("source", "") or "")
        self.evidence_ids: list[str] = list(kwargs.pop("evidence_ids", None) or [])
        self.fact_ids: list[str] = list(kwargs.pop("fact_ids", None) or [])
        self.sort_key: str = str(kwargs.pop("sort_key", "") or "")
        self.metadata: dict[str, Any] = dict(kwargs.pop("metadata", None) or {})
        for key, value in kwargs.items():
            setattr(self, key, value)
        if not self.description and self.source:
            self.description = self.source
        if not self.event:
            self.event = (
                self.label
                or self.title
                or self.description
                or self.summary
                or self.source
            )
        if not self.label:
            self.label = self.event or self.title or self.source
        if not self.title:
            self.title = self.label or self.event
        if not self.description and self.summary:
            self.description = self.summary

    def validate(self) -> None:
        if not (
            str(self.event or "").strip()
            or str(self.label or "").strip()
            or str(self.date_label or "").strip()
            or str(self.description or "").strip()
            or str(self.title or "").strip()
            or str(self.source or "").strip()
        ):
            raise ValueError(
                "TimelineEvent needs event, label, date_label, title, description, or source"
            )


@dataclass(slots=True)
class Fact:
    id: str = field(default_factory=lambda: str(uuid4()))
    statement: str = ""
    status: FactStatus = FactStatus.UNVERIFIED
    source_refs: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)

    def validate(self) -> None:
        if not (self.statement or "").strip():
            raise ValueError("Fact.statement cannot be empty")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("Fact.confidence must be in [0, 1]")


@dataclass(slots=True)
class LegalBasis:
    id: str = field(default_factory=lambda: str(uuid4()))
    reference: str = ""
    note: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not (self.reference or "").strip():
            raise ValueError("LegalBasis.reference cannot be empty")


@dataclass(slots=True)
class LegalIssue:
    id: str = field(default_factory=lambda: str(uuid4()))
    question: str = ""
    status: IssueStatus = IssueStatus.OPEN
    fact_ids: list[str] = field(default_factory=list)
    hypothesis: str = ""
    statute_refs: list[str] = field(default_factory=list)
    case_law_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)

    def validate(self) -> None:
        if not (self.question or "").strip():
            raise ValueError("LegalIssue.question cannot be empty")


@dataclass(slots=True)
class Decision:
    id: str = field(default_factory=lambda: str(uuid4()))
    kind: DecisionKind = DecisionKind.PROCEDURAL
    summary: str = ""
    fact_ids: list[str] = field(default_factory=list)
    legal_basis_ids: list[str] = field(default_factory=list)
    issue_ids: list[str] = field(default_factory=list)
    scope_not_challenged: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    assessment_points: list[str] = field(default_factory=list)
    outcomes: list[str] = field(default_factory=list)
    closing_statement: str = ""
    attachments: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)

    def validate(self) -> None:
        if not (self.summary or "").strip():
            raise ValueError("Decision.summary cannot be empty")


@dataclass(slots=True)
class Case:
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    working_title: str = ""
    signature: str = ""
    status: CaseStatus = CaseStatus.NEW
    parties: list[Party] = field(default_factory=list)
    evidence_items: list[EvidenceItem] = field(default_factory=list)
    timeline_events: list[TimelineEvent] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    legal_bases: list[LegalBasis] = field(default_factory=list)
    legal_issues: list[LegalIssue] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def touch(self) -> None:
        self.updated_at = _now()

    def has_signature(self) -> bool:
        return bool((self.signature or "").strip())

    @property
    def timeline(self) -> list[TimelineEvent]:
        return self.timeline_events

    @property
    def evidence(self) -> list[EvidenceItem]:
        return self.evidence_items

    def ordered_timeline(self) -> list[TimelineEvent]:
        """Chronological order for renderers (render.py / dossier_render.py)."""

        def _key(ev: TimelineEvent) -> tuple:
            d = getattr(ev, "when", None) or getattr(ev, "date", None) or date.min
            sk = str(getattr(ev, "sort_key", "") or "")
            lab = str(
                getattr(ev, "label", "")
                or getattr(ev, "event", "")
                or getattr(ev, "date_label", "")
                or ""
            )
            return (d, sk, lab)

        return sorted(self.timeline_events, key=_key)

    def display_title(self) -> str:
        return (
            (self.working_title or "").strip()
            or (self.title or "").strip()
            or (self.signature or "").strip()
            or self.id
        )

    def add_party(self, party: Party) -> None:
        self.parties.append(party)
        self.touch()

    def add_evidence(self, item: EvidenceItem) -> None:
        item.validate()
        self.evidence_items.append(item)
        self.touch()

    def add_timeline_event(self, event: TimelineEvent) -> None:
        event.validate()
        known_ev = {e.id for e in self.evidence_items}
        known_fa = {f.id for f in self.facts}
        missing_e = [i for i in event.evidence_ids if i not in known_ev]
        missing_f = [i for i in event.fact_ids if i not in known_fa]
        if missing_e:
            raise ValueError(f"TimelineEvent references unknown evidence: {missing_e}")
        if missing_f:
            raise ValueError(f"TimelineEvent references unknown facts: {missing_f}")
        self.timeline_events.append(event)
        self.touch()

    def add_fact(self, fact: Fact) -> None:
        fact.validate()
        known_ev = {e.id for e in self.evidence_items}
        missing = [i for i in fact.evidence_ids if i not in known_ev]
        if missing:
            raise ValueError(f"Fact references unknown evidence: {missing}")
        self.facts.append(fact)
        if self.status in (CaseStatus.NEW, CaseStatus.INTAKE):
            self.status = CaseStatus.FACTS
        self.touch()

    def add_legal_basis(self, basis: LegalBasis) -> None:
        basis.validate()
        self.legal_bases.append(basis)
        self.touch()

    def add_issue(self, issue: LegalIssue) -> None:
        issue.validate()
        known = {f.id for f in self.facts}
        missing = [fid for fid in issue.fact_ids if fid not in known]
        if missing:
            raise ValueError(f"LegalIssue references unknown facts: {missing}")
        self.legal_issues.append(issue)
        if self.status in (CaseStatus.NEW, CaseStatus.INTAKE, CaseStatus.FACTS):
            self.status = CaseStatus.ANALYSIS
        self.touch()

    def add_decision(self, decision: Decision) -> None:
        decision.validate()
        known_facts = {f.id for f in self.facts}
        known_law = {b.id for b in self.legal_bases}
        known_issues = {i.id for i in self.legal_issues}
        missing_facts = [fid for fid in decision.fact_ids if fid not in known_facts]
        missing_law = [lid for lid in decision.legal_basis_ids if lid not in known_law]
        missing_issues = [iid for iid in decision.issue_ids if iid not in known_issues]
        if missing_facts:
            raise ValueError(f"Decision references unknown facts: {missing_facts}")
        if missing_law:
            raise ValueError(f"Decision references unknown legal bases: {missing_law}")
        if missing_issues:
            raise ValueError(f"Decision references unknown legal issues: {missing_issues}")
        self.decisions.append(decision)
        self.status = CaseStatus.DECISION
        self.touch()

    def get_fact(self, fact_id: str) -> Fact | None:
        for fact in self.facts:
            if fact.id == fact_id:
                return fact
        return None

    def get_issue(self, issue_id: str) -> LegalIssue | None:
        for issue in self.legal_issues:
            if issue.id == issue_id:
                return issue
        return None

    def get_evidence(self, evidence_id: str) -> EvidenceItem | None:
        for item in self.evidence_items:
            if item.id == evidence_id:
                return item
        return None

    def latest_decision(self) -> Decision | None:
        if not self.decisions:
            return None
        return self.decisions[-1]

    def advance_to(self, status: CaseStatus) -> None:
        self.status = status
        self.touch()

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "working_title": self.working_title,
            "signature": self.signature,
            "has_signature": self.has_signature(),
            "status": self.status.name,
            "parties": len(self.parties),
            "evidence_items": len(self.evidence_items),
            "timeline_events": len(self.timeline_events),
            "facts": len(self.facts),
            "legal_bases": len(self.legal_bases),
            "legal_issues": len(self.legal_issues),
            "decisions": len(self.decisions),
        }