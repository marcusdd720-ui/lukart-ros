"""Tests for knowledge.models.render"""

from __future__ import annotations

from datetime import date

import pytest

from knowledge.models.case import (
    Case,
    Decision,
    DecisionKind,
    Fact,
    FactStatus,
    LegalBasis,
    Party,
    TimelineEvent,
)
from knowledge.models.render import CaseLetterRenderer, LetterContext


def _sample_case() -> Case:
    case = Case(
        title="Skarga na sposob pouczenia",
        signature="II Kp 459/26",
        metadata={"prosecutor_ref": "4057-0.Ds.2517.2025"},
    )
    case.add_party(Party(name="Arkadiusz Mielewczyk", role="applicant"))
    case.add_party(
        Party(
            name="Prezes Sadu Rejonowego w Wejherowie",
            role="authority",
            metadata={"address": "ul. Wniebowstapienia 4, 84-200 Wejherowo"},
        )
    )
    fact = Fact(
        statement="W dniu 10.06.2026 r. sedzia referent wyslal wiadomosc e-mail.",
        status=FactStatus.SUPPORTED,
        source_refs=["email-2026-06-10"],
    )
    case.add_fact(fact)
    basis = LegalBasis(reference="art. 16 par. 1-3 k.p.k.")
    case.add_legal_basis(basis)
    case.add_decision(
        Decision(
            kind=DecisionKind.PROCEDURAL,
            summary=(
                "Wnosze o ponowne rozpoznanie skargi w zakresie sposobu "
                "wykonania obowiazku informacyjnego."
            ),
            fact_ids=[fact.id],
            legal_basis_ids=[basis.id],
            outcomes=[
                "ponowne rozpoznanie skargi",
                "wskazanie charakteru wiadomosci z 10.06.2026",
            ],
        )
    )
    return case


def test_render_contains_sections() -> None:
    case = _sample_case()
    text = CaseLetterRenderer().render(
        case,
        context=LetterContext(
            sender_name="Arkadiusz Mielewczyk",
            place="Wejherowo",
            letter_date=date(2026, 7, 28),
        ),
    )
    assert "Sygn. akt: II Kp 459/26" in text
    assert "Sygn. prokuratorska: 4057-0.Ds.2517.2025" in text
    assert "I. Przedmiot sprawy" in text
    assert "II. Ustalenia faktyczne" in text
    assert "III. Podstawa prawna" in text
    assert "IV. Stanowisko" in text
    assert "V. Wnioski" in text
    assert "art. 16" in text
    assert "ponowne rozpoznanie skargi" in text
    assert "Wejherowo, dnia 28.07.2026 r." in text


def test_render_without_decision_raises() -> None:
    case = Case(title="Pusta")
    with pytest.raises(ValueError, match="no decision"):
        CaseLetterRenderer().render(case)


def test_render_structured_sections() -> None:
    case = Case(
        title="Test",
        signature="II Kp 459/26",
        metadata={"prosecutor_ref": "4057-0.Ds.2517.2025"},
    )
    case.add_party(Party(name="A", role="applicant"))
    fact = Fact(statement="Fakt testowy.", status=FactStatus.SUPPORTED)
    case.add_fact(fact)
    basis = LegalBasis(reference="art. 16 k.p.k.")
    case.add_legal_basis(basis)
    case.add_decision(
        Decision(
            kind=DecisionKind.PROCEDURAL,
            summary="Wniosek o ponowne rozpoznanie.",
            fact_ids=[fact.id],
            legal_basis_ids=[basis.id],
            outcomes=["przyjecie do akt"],
            scope_not_challenged=["autentycznosc wiadomosci"],
            issues=["sposob pouczenia"],
            assessment_points=["Odpowiedz nie odnosi sie do standardu art. 16."],
            closing_statement="Zalezy mi na spokojnym wyjasnieniu.",
            attachments=["kopia skargi"],
        )
    )
    text = CaseLetterRenderer().render(case, context=LetterContext(sender_name="A"))
    assert "I. Przedmiot sprawy" in text
    assert "Nie jest kwestionowane:" in text
    assert "Sygn. prokuratorska: 4057-0.Ds.2517.2025" in text
    assert "Zalaczniki:" in text or "Załączniki:" in text
    assert "kopia skargi" in text


def test_render_timeline_section() -> None:
    case = Case(signature="DS.3960.2025", metadata={"prosecutor_ref": "DS.3960.2025"})
    case.add_party(Party(name="M", role="applicant"))
    fact = Fact(statement="Fakt.", status=FactStatus.SUPPORTED)
    case.add_fact(fact)
    basis = LegalBasis(reference="art. 7 k.p.k.")
    case.add_legal_basis(basis)
    case.add_timeline_event(
        TimelineEvent(
            date_label="31.05.2025",
            sort_key="2025-05-31",
            event="Rejestracja",
            source="dowod",
            procedural_meaning="Wpis administracyjny",
        )
    )
    case.add_decision(
        Decision(
            summary="Stanowisko.",
            fact_ids=[fact.id],
            legal_basis_ids=[basis.id],
            outcomes=["przyjecie"],
        )
    )
    text = CaseLetterRenderer().render(case, context=LetterContext(sender_name="M"))
    assert "II.A. Chronologia zdarzeń" in text
    assert "Rejestracja" in text
    assert text.count("DS.3960.2025") >= 1
    assert "Sygn. akt: DS.3960.2025" not in text or "Sygn. prokuratorska: DS.3960.2025" in text