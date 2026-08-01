"""Tests for knowledge.models.case"""

from __future__ import annotations

import pytest

from knowledge.models.case import (
    Case,
    CaseStatus,
    Decision,
    DecisionKind,
    Fact,
    FactStatus,
    LegalBasis,
    Party,
)


def test_case_add_fact_and_decision() -> None:
    case = Case(title="Skarga na pouczenie", signature="II Kp 459/26")
    case.add_party(Party(name="Arkadiusz Mielewczyk", role="applicant"))
    case.add_party(Party(name="Prezes SR Wejherowo", role="authority"))

    fact = Fact(
        statement="W dniu 10.06.2026 r. sędzia referent wysłał wiadomość e-mail.",
        status=FactStatus.SUPPORTED,
        source_refs=["email-2026-06-10"],
    )
    case.add_fact(fact)
    assert case.status == CaseStatus.FACTS

    basis = LegalBasis(reference="art. 16 § 1–3 k.p.k.")
    case.add_legal_basis(basis)

    decision = Decision(
        kind=DecisionKind.PROCEDURAL,
        summary="Wniosek o ponowne rozpoznanie skargi w zakresie sposobu pouczenia.",
        fact_ids=[fact.id],
        legal_basis_ids=[basis.id],
        outcomes=[
            "ponowne rozpoznanie skargi",
            "wskazanie charakteru wiadomości z 10.06.2026",
        ],
    )
    case.add_decision(decision)

    assert case.status == CaseStatus.DECISION
    assert case.latest_decision() is decision
    assert case.summary()["facts"] == 1
    assert case.summary()["decisions"] == 1


def test_decision_requires_facts_and_law() -> None:
    case = Case(title="X")
    decision = Decision(summary="Bez podstaw", fact_ids=[], legal_basis_ids=[])
    with pytest.raises(ValueError):
        case.add_decision(decision)


def test_decision_unknown_fact_rejected() -> None:
    case = Case(title="X")
    basis = LegalBasis(reference="art. 7 k.p.a.")
    case.add_legal_basis(basis)
    decision = Decision(
        summary="Opinia",
        fact_ids=["missing-fact"],
        legal_basis_ids=[basis.id],
    )
    with pytest.raises(ValueError, match="unknown facts"):
        case.add_decision(decision)


def test_empty_fact_statement_rejected() -> None:
    case = Case(title="X")
    with pytest.raises(ValueError):
        case.add_fact(Fact(statement="  "))