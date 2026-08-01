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
)
from knowledge.models.render import CaseLetterRenderer, LetterContext


def _sample_case() -> Case:
    case = Case(title="Skarga na sposob pouczenia", signature="II Kp 459/26")
    case.add_party(Party(name="Arkadiusz Mielewczyk", role="applicant"))
    case.add_party(
        Party(
            name="Prezes Sadu Rejonowego w Wejherowie",
            role="authority",
            metadata={"address": "ul. Wniebowstapienia 4, 84-200 Wejherowo"},
        )
    )
    fact = Fact(
        statement="W dniu 10.06.2026 r. sędzia referent wyslal wiadomosc e-mail.",
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
    assert "I. Ustalenia faktyczne" in text
    assert "II. Podstawa prawna" in text
    assert "III. Stanowisko" in text
    assert "IV. Wnioski" in text
    assert "art. 16" in text
    assert "ponowne rozpoznanie skargi" in text
    assert "Wejherowo, dnia 28.07.2026 r." in text


def test_render_without_decision_raises() -> None:
    case = Case(title="Pusta")
    with pytest.raises(ValueError, match="no decision"):
        CaseLetterRenderer().render(case)