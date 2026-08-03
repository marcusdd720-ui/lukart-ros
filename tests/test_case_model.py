"""Tests for knowledge.models.case"""

from __future__ import annotations

import pytest

from knowledge.models.case import (
    Case,
    CaseStatus,
    Decision,
    DecisionKind,
    EvidenceItem,
    EvidenceWeight,
    Fact,
    FactStatus,
    LegalBasis,
    Party,
    TimelineEvent,
)
from knowledge.models.render import CaseLetterRenderer, LetterContext


def test_case_add_fact_and_decision() -> None:
    case = Case(title="Skarga na pouczenie", signature="II Kp 459/26")
    case.add_party(Party(name="Arkadiusz Mielewczyk", role="applicant"))
    case.add_party(Party(name="Prezes SR Wejherowo", role="authority"))

    fact = Fact(
        statement="W dniu 10.06.2026 r. sedzia referent wyslal wiadomosc e-mail.",
        status=FactStatus.SUPPORTED,
        source_refs=["email-2026-06-10"],
    )
    case.add_fact(fact)
    assert case.status == CaseStatus.FACTS

    basis = LegalBasis(reference="art. 16 k.p.k.")
    case.add_legal_basis(basis)

    decision = Decision(
        kind=DecisionKind.PROCEDURAL,
        summary="Wniosek o ponowne rozpoznanie skargi.",
        fact_ids=[fact.id],
        legal_basis_ids=[basis.id],
        outcomes=["ponowne rozpoznanie skargi"],
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


def test_case_without_signature_and_assign_later() -> None:
    case = Case(
        working_title="VW Transporter – spor po darowiznie",
        status=CaseStatus.INTAKE,
    )
    assert case.has_signature() is False
    assert case.display_title() == "VW Transporter – spor po darowiznie"
    assert case.summary()["signature"] is None

    case.assign_signature("DS.3960.2025", ref_key="prosecutor_ref")
    assert case.has_signature() is True
    assert case.signature == "DS.3960.2025"
    assert case.metadata["prosecutor_ref"] == "DS.3960.2025"


def test_render_without_signature_uses_working_title() -> None:
    case = Case(
        working_title="Sprawa wstepna bez sygnatury",
        status=CaseStatus.PRE_CASE,
    )
    case.add_party(Party(name="X", role="applicant"))
    fact = Fact(
        statement="Dokument w dyspozycji strony.",
        status=FactStatus.SUPPORTED,
    )
    case.add_fact(fact)
    basis = LegalBasis(reference="art. 7 k.p.k.")
    case.add_legal_basis(basis)
    case.add_decision(
        Decision(
            summary="Stanowisko wstepne.",
            fact_ids=[fact.id],
            legal_basis_ids=[basis.id],
            outcomes=["przyjecie pisma"],
        )
    )
    text = CaseLetterRenderer().render(
        case,
        context=LetterContext(sender_name="X"),
    )
    assert "Sygn. akt:" not in text
    assert "Sprawa: Sprawa wstepna bez sygnatury" in text


def test_timeline_ordering() -> None:
    case = Case(working_title="T")
    case.add_timeline_event(
        TimelineEvent(
            date_label="07.07.2025",
            sort_key="2025-07-07",
            event="Wezwanie",
            source="wezwanie",
            procedural_meaning="Spor",
        )
    )
    case.add_timeline_event(
        TimelineEvent(
            date_label="31.05.2025",
            sort_key="2025-05-31",
            event="Rejestracja",
            source="dowod",
            procedural_meaning="Wpis",
        )
    )
    ordered = case.ordered_timeline()
    assert ordered[0].event == "Rejestracja"
    assert ordered[1].event == "Wezwanie"
    assert case.summary()["timeline_events"] == 2


def test_evidence_item_analysis() -> None:
    case = Case(working_title="E")
    case.add_evidence(
        EvidenceItem(
            label="Umowa darowizny",
            source_ref="umowa-darowizny",
            proves=["istnienie pisemnej umowy stron"],
            does_not=["samodzielne przesadzenie skutecznosci cywilnoprawnej"],
            weight=EvidenceWeight.HIGH,
            open_questions=["czy wszystkie elementy oswiadczen woli sa bezsporne"],
        )
    )
    assert case.summary()["evidence_items"] == 1
    assert case.status == CaseStatus.ANALYSIS