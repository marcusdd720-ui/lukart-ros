"""
Knowledge Operating System (KOS)

File: knowledge/models/case.py
Version: 1.3
Sprint: CASE-006

Domain model for a legal case (virtual chambers).
Signature may be assigned late. Timeline is first-class chronology.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import Any
from uuid import uuid4


class CaseStatus(StrEnum):
    NEW = auto()
    INTAKE = auto()
    PRE_CASE = auto()
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


class DecisionKind(StrEnum):
    PROCEDURAL = auto()
    SUBSTANTIVE = auto()
    INTERIM = auto()
    CLOSING = auto()


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class Party:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    role: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Fact:
    id: str = field(default_factory=lambda: str(uuid4()))
    statement: str = ""
    status: FactStatus = FactStatus.UNVERIFIED
    source_refs: list[str] = field(default_factory=list)
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)

    def validate(self) -> None:
        if not self.statement.strip():
            raise ValueError("Fact.statement cannot be empty.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Fact.confidence must be between 0.0 and 1.0.")


@dataclass(slots=True)
class LegalBasis:
    id: str = field(default_factory=lambda: str(uuid4()))
    reference: str = ""
    note: str = ""


@dataclass(slots=True)
class TimelineEvent:
    """
    One row of procedural chronology:
    date | event | source | procedural meaning
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    date_label: str = ""
    event: str = ""
    source: str = ""
    procedural_meaning: str = ""
    sort_key: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.event.strip():
            raise ValueError("TimelineEvent.event cannot be empty.")
        if not self.source.strip():
            raise ValueError("TimelineEvent.source cannot be empty.")


@dataclass(slots=True)
class Decision:
    id: str = field(default_factory=lambda: str(uuid4()))
    kind: DecisionKind = DecisionKind.PROCEDURAL
    summary: str = ""
    fact_ids: list[str] = field(default_factory=list)
    legal_basis_ids: list[str] = field(default_factory=list)
    outcomes: list[str] = field(default_factory=list)

    scope_not_challenged: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    assessment_points: list[str] = field(default_factory=list)
    closing_statement: str = ""
    attachments: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)

    def validate(self) -> None:
        if not self.summary.strip():
            raise ValueError("Decision.summary cannot be empty.")
        if not self.fact_ids:
            raise ValueError("Decision must reference at least one fact.")
        if not self.legal_basis_ids:
            raise ValueError("Decision must reference at least one legal basis.")


@dataclass(slots=True)
class Case:
    """
    Single source of truth for a matter.

    signature may be empty until the authority assigns a file number.
    working_title is used in drafts and early letters.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    working_title: str = ""
    signature: str = ""
    status: CaseStatus = CaseStatus.NEW

    parties: list[Party] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    legal_bases: list[LegalBasis] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    timeline: list[TimelineEvent] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def touch(self) -> None:
        self.updated_at = _now()

    def display_title(self) -> str:
        if self.title.strip():
            return self.title.strip()
        if self.working_title.strip():
            return self.working_title.strip()
        return "Sprawa bez tytułu"

    def has_signature(self) -> bool:
        return bool(self.signature and self.signature.strip())

    def assign_signature(self, signature: str, *, ref_key: str | None = None) -> None:
        text = (signature or "").strip()
        if not text:
            raise ValueError("signature cannot be empty when assigning.")
        self.signature = text
        if ref_key:
            self.metadata[ref_key] = text
        if self.status in (CaseStatus.NEW, CaseStatus.INTAKE, CaseStatus.PRE_CASE):
            self.status = CaseStatus.FACTS if self.facts else CaseStatus.INTAKE
        self.touch()

    def add_party(self, party: Party) -> None:
        self.parties.append(party)
        self.touch()

    def add_fact(self, fact: Fact) -> None:
        fact.validate()
        self.facts.append(fact)
        if self.status in (CaseStatus.NEW, CaseStatus.INTAKE, CaseStatus.PRE_CASE):
            self.status = CaseStatus.FACTS
        self.touch()

    def add_legal_basis(self, basis: LegalBasis) -> None:
        if not basis.reference.strip():
            raise ValueError("LegalBasis.reference cannot be empty.")
        self.legal_bases.append(basis)
        self.touch()

    def add_timeline_event(self, event: TimelineEvent) -> None:
        event.validate()
        self.timeline.append(event)
        self.touch()

    def ordered_timeline(self) -> list[TimelineEvent]:
        def _key(e: TimelineEvent) -> tuple[str, str]:
            return (e.sort_key or e.date_label or "", e.date_label or "")

        return sorted(self.timeline, key=_key)

    def add_decision(self, decision: Decision) -> None:
        decision.validate()
        known_facts = {f.id for f in self.facts}
        known_law = {b.id for b in self.legal_bases}
        missing_facts = [fid for fid in decision.fact_ids if fid not in known_facts]
        missing_law = [lid for lid in decision.legal_basis_ids if lid not in known_law]
        if missing_facts:
            raise ValueError(f"Decision references unknown facts: {missing_facts}")
        if missing_law:
            raise ValueError(f"Decision references unknown legal bases: {missing_law}")
        self.decisions.append(decision)
        self.status = CaseStatus.DECISION
        self.touch()

    def get_fact(self, fact_id: str) -> Fact | None:
        for fact in self.facts:
            if fact.id == fact_id:
                return fact
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
            "title": self.display_title(),
            "working_title": self.working_title,
            "signature": self.signature or None,
            "has_signature": self.has_signature(),
            "status": self.status.name,
            "parties": len(self.parties),
            "facts": len(self.facts),
            "legal_bases": len(self.legal_bases),
            "decisions": len(self.decisions),
            "timeline_events": len(self.timeline),
        }