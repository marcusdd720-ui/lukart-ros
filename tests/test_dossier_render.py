"""Tests for knowledge.models.dossier_render"""

from __future__ import annotations

from datetime import date

import pytest

from knowledge.models.case import (
    Case,
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
from knowledge.models.dossier_render import DossierContext, DossierRenderer


def _sample_case() -> Case:
    case = Case(
        title="Stanowisko testowe",
        working_title="Sprawa testowa",
        signature="DS.3960.2025",
        metadata={"prosecutor_ref": "DS.3960.2025"},
    )
    case.add_party(Party(name="Mariusz Brodziszewski", role="applicant"))
    fact = Fact(
        statement="Sporzadzono umowe darowizny.",
        status=FactStatus.SUPPORTED,
        source_refs=["umowa-darowizny"],
    )
    case.add_fact(fact)
    case.add_timeline_event(
        TimelineEvent(
            date_label="31.05.2025",
            sort_key="2025-05-31",
            event="Umowa darowizny",
            source="umowa-darowizny",
            procedural_meaning="Podstawa dalszych czynnosci",
        )
    )
    case.add_evidence(
        EvidenceItem(
            label="Umowa darowizny",
            source_ref="umowa-darowizny",
            proves=["istnienie pisemnej umowy"],
            does_not=["skutecznosc cywilnoprawna sama przez sie"],
            weight=EvidenceWeight.HIGH,
            open_questions=["ocena oswiadczen woli"],
        )
    )
    basis = LegalBasis(reference="art. 7 k.p.k.", note="swobodna ocena dowodow")
    case.add_legal_basis(basis)
    case.add_decision(
        Decision(
            kind=DecisionKind.PROCEDURAL,
            summary="Stanowisko analityczne testowe.",
            fact_ids=[fact.id],
            legal_basis_ids=[basis.id],
            outcomes=["przyjecie stanowiska do akt"],
            scope_not_challenged=["istnienie umowy jako dokumentu"],
            issues=["ocena caloksztaltu materialu"],
            assessment_points=["Dokumenty tworza jawny ciag czynnosci."],
            closing_statement="Oparte wylacznie na materialie zrodlowym.",
            attachments=["umowa darowizny"],
        )
    )
    return case


def test_dossier_contains_core_sections() -> None:
    case = _sample_case()
    text = DossierRenderer().render(
        case,
        context=DossierContext(
            author_name="Mariusz Brodziszewski",
            place="Poznan",
            dossier_date=date(2026, 8, 4),
            recipient_lines=["Prokuratura Rejonowa Poznan-Wilda"],
            subject="Test dossier",
        ),
    )
    assert "STANOWISKO PROCESOWE" in text
    assert "I. METODYKA OPRACOWANIA" in text
    assert "II. PRZEDMIOT STANOWISKA" in text
    assert "III. STAN FAKTYCZNY" in text
    assert "IV. CHRONOLOGIA ZDARZEŃ" in text
    assert "V. ANALIZA MATERIAŁU DOWODOWEGO" in text
    assert "VI. PODSTAWA PRAWNA" in text
    assert "VII. OCENA ŁĄCZNA I STANOWISKO" in text
    assert "VIII. WNIOSKI DOWODOWE" in text
    assert "IX. WNIOSKI KOŃCOWE" in text
    assert "X. ZAŁĄCZNIKI" in text
    assert "Sygnatura: DS.3960.2025" in text
    assert "Umowa darowizny" in text
    assert "art. 7 k.p.k." in text
    assert "Poznan, dnia 04.08.2026 r." in text


def test_dossier_without_decision_raises() -> None:
    case = Case(title="Pusta")
    with pytest.raises(ValueError, match="no decision"):
        DossierRenderer().render(case)