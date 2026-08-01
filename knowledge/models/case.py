"""
Knowledge Operating System (KOS)

File: knowledge/models/case.py
Version: 1.1
Sprint: CASE-001 / CASE-004

Domain model for a legal case (virtual chambers).
Evidence-driven: no decision without recorded facts.
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
class Decision:
    """
    Auditable legal decision.

    Optional section fields support complex filings (style 3.1):
    scope_not_challenged, issues, assessment_points, closing_statement, attachments.
    Legacy cases may leave them empty and use summary + outcomes only.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    kind: DecisionKind = DecisionKind.PROCEDURAL
    summary: str = ""
    fact_ids: list[str] = field(default_factory=list)
    legal_basis_ids: list[str] = field(default_factory=list)
    outcomes: list[str] = field(default_factory=list)

    # Structured sections for large matters
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
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    signature: str = ""
    status: CaseStatus = CaseStatus.NEW

    parties: list[Party] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    legal_bases: list[LegalBasis] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def touch(self) -> None:
        self.updated_at = _now()

    def add_party(self, party: Party) -> None:
        self.parties.append(party)
        self.touch()

    def add_fact(self, fact: Fact) -> None:
        fact.validate()
        self.facts.append(fact)
        if self.status in (CaseStatus.NEW, CaseStatus.INTAKE):
            self.status = CaseStatus.FACTS
        self.touch()

    def add_legal_basis(self, basis: LegalBasis) -> None:
        if not basis.reference.strip():
            raise ValueError("LegalBasis.reference cannot be empty.")
        self.legal_bases.append(basis)
        self.touch()

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
            "title": self.title,
            "signature": self.signature,
            "status": self.status.name,
            "parties": len(self.parties),
            "facts": len(self.facts),
            "legal_bases": len(self.legal_bases),
            "decisions": len(self.decisions),
        }