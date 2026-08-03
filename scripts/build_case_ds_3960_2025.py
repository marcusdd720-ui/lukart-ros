"""
Build case DS.3960.2025 (VW Transporter / Mariusz Brodziszewski).

Evidence-only facts. No civil-ownership conclusions.
Focus: open course of dealing + belief in right to dispose of the vehicle.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
from knowledge.models.docx_export import CaseDocxExporter
from knowledge.models.render import CaseLetterRenderer, LetterContext


def build_case() -> Case:
    case = Case(
        title="Stanowisko procesowe wraz z analizą materiału dowodowego",
        working_title="VW Transporter – czynności po umowie darowizny",
        signature="DS.3960.2025",
        status=CaseStatus.INTAKE,
        metadata={
            "prosecutor_ref": "DS.3960.2025",
            "vehicle": "Volkswagen Transporter",
            "reg": "PZ2V467",
            "vin": "WV1ZZZ7HZDH008410",
            "contact_sylwia": "Sylwia Grochowska",
        },
    )

    case.add_party(
        Party(
            name="Mariusz Brodziszewski",
            role="applicant",
            metadata={"acts_without_counsel": True},
        )
    )
    case.add_party(
        Party(
            name="Katarzyna Anna Brodziszewska",
            role="other_party",
            metadata={"relation": "former_spouse"},
        )
    )
    case.add_party(
        Party(
            name="Prokuratura Rejonowa Poznań-Wilda",
            role="authority",
            metadata={"case_ref": "DS.3960.2025"},
        )
    )

    # --- Facts strictly from documents / marked statements ---
    f1 = Fact(
        statement=(
            "Sporządzono pisemną umowę darowizny pojazdu marki Volkswagen Transporter "
            "pomiędzy Katarzyną Anną Brodziszewską jako darczyńcą a Mariuszem Brodziszewskim "
            "jako obdarowanym; dokument identyfikuje pojazd (w tym VIN)."
        ),
        status=FactStatus.SUPPORTED,
        source_refs=["umowa-darowizny"],
    )
    f2 = Fact(
        statement=(
            "W dniu 31.05.2025 r. właściwy organ administracji dokonał rejestracji "
            "pojazdu z wpisem Mariusza Brodziszewskiego jako właściciela w dowodzie "
            "rejestracyjnym (czynność administracyjna; nie przesądza sama przez się "
            "skuteczności nabycia własności w rozumieniu prawa cywilnego)."
        ),
        status=FactStatus.SUPPORTED,
        source_refs=["dowod-rejestracyjny"],
    )
    f3 = Fact(
        statement=(
            "Dla przedmiotowego pojazdu zawarto umowę obowiązkowego ubezpieczenia OC."
        ),
        status=FactStatus.SUPPORTED,
        source_refs=["polisa-oc"],
    )
    f4 = Fact(
        statement=(
            "Funkcjonariusze Policji zabezpieczyli oryginał umowy darowizny; dokument "
            "pozostaje w dyspozycji organów prowadzących postępowanie."
        ),
        status=FactStatus.SUPPORTED,
        source_refs=["notatka-policji-zabezpieczenie-umowy"],
    )
    f5 = Fact(
        statement=(
            "W dniu 07.07.2025 r. sporządzono wezwanie skierowane do Mariusza "
            "Brodziszewskiego do wydania pojazdu — dokument potwierdza istnienie sporu "
            "co do prawa do dysponowania pojazdem."
        ),
        status=FactStatus.SUPPORTED,
        source_refs=["wezwanie-2025-07-07"],
    )
    f6 = Fact(
        statement=(
            "Małżeństwo Mariusza Brodziszewskiego i Katarzyny Brodziszewskiej zostało "
            "rozwiązane przez rozwód (okoliczność wynikająca z odpisu wyroku; znaczenie "
            "prawne dla oceny wcześniejszych czynności nie jest tu przesądzane)."
        ),
        status=FactStatus.SUPPORTED,
        source_refs=["wyrok-rozwodowy"],
    )
    f7 = Fact(
        statement=(
            "Mariusz Brodziszewski oświadcza, że pojazd pozostaje na jego posesji, "
            "nie został ukryty, zbyty ani przekazany osobom trzecim i jest dostępny "
            "dla organów prowadzących postępowanie."
        ),
        status=FactStatus.SUPPORTED,
        source_refs=["oswiadczenie-mariusza-posesja"],
        confidence=0.85,
        metadata={"kind": "party_statement"},
    )
    for fact in (f1, f2, f3, f4, f5, f6, f7):
        case.add_fact(fact)

    b1 = LegalBasis(
        reference="art. 7 k.p.k.",
        note="swobodna ocena dowodów — nie dowolna; logika, wiedza, doświadczenie życiowe",
    )
    b2 = LegalBasis(
        reference="art. 4 k.p.k.",
        note="zasada obiektywizmu",
    )
    b3 = LegalBasis(
        reference="art. 410 k.p.k.",
        note="podstawa rozstrzygnięcia — całokształt ujawnionych okoliczności",
    )
    b4 = LegalBasis(
        reference="art. 167 k.p.k.",
        note="inicjatywa dowodowa",
    )
    b5 = LegalBasis(
        reference="[ORZECZNICTWO – DO UZUPEŁNIENIA PO WERYFIKACJI]",
        note="linie orzecznicze dot. art. 7 i 410 k.p.k. — dopiero po weryfikacji sygnatur",
    )
    for basis in (b1, b2, b3, b4, b5):
        case.add_legal_basis(basis)

    case.add_decision(
        Decision(
            kind=DecisionKind.PROCEDURAL,
            summary=(
                "Stanowisko ma na celu wykazanie okoliczności, w jakich Mariusz "
                "Brodziszewski wykonywał czynności dotyczące pojazdu, oraz przedstawienie "
                "dokumentów stanowiących podstawę jego przekonania o przysługującym prawie "
                "do dysponowania pojazdem. Nie przesądza się skuteczności cywilnoprawnej "
                "umowy darowizny; akcent spoczywa na jawnym, udokumentowanym ciągu czynności "
                "oraz na ocenie zamiaru w świetle całokształtu materiału dowodowego."
            ),
            fact_ids=[f1.id, f2.id, f3.id, f4.id, f5.id, f6.id, f7.id],
            legal_basis_ids=[b1.id, b2.id, b3.id, b4.id, b5.id],
            scope_not_challenged=[
                "istnienie pisemnej umowy darowizny jako dokumentu w sprawie",
                "fakt dokonania rejestracji pojazdu przez organ administracji",
                "zawarcie polisy OC dla pojazdu",
                "zabezpieczenie oryginału umowy przez Policję",
                "istnienie sporu co do pojazdu (wezwanie do wydania)",
                "rozwiązanie małżeństwa przez rozwód",
            ],
            issues=[
                "czy czynności Mariusza (rejestracja, OC, posiadanie pojazdu) były podejmowane w oparciu o dokumenty i w przekonaniu o prawie do dysponowania pojazdem",
                "czy sam późniejszy spór cywilny/rodzinny wystarcza do przyjęcia znamion czynu zabronionego bez oceny całokształtu materiału",
                "czy ocena sprawy wymaga oddzielenia skutków cywilnoprawnych darowizny od oceny zachowania na gruncie prawa karnego",
            ],
            assessment_points=[
                "Umowa darowizny, rejestracja i polisa OC tworzą jawny, weryfikowalny ciąg czynności — nie ukryty obrót pojazdem.",
                "Rejestracja nie konstytuuje własności, ale potwierdza, że organ administracji uznał dokumenty za wystarczające do wpisu.",
                "Spór (wezwanie 07.07.2025) ujawnił się po rejestracji i ubezpieczeniu — chronologia ma znaczenie dla oceny zamiaru.",
                "Oryginał umowy jest w dyspozycji organów — treść i autentyczność mogą być ocenione bezpośrednio.",
                "Oświadczenie o posesji jest oświadczeniem strony i podlega ocenie łącznie z dokumentami, nie zamiast nich.",
                "Na obecnym etapie materiał nie pozwala na automatyczne przesądzenie realizacji znamion czynu zabronionego bez wszechstronnej oceny (art. 7 i 410 k.p.k.).",
            ],
            outcomes=[
                "uwzględnienie całokształtu dokumentów (umowa, dowód rejestracyjny, polisa OC, dokument Policji, wezwanie, wyrok rozwodowy) przy ocenie zachowania Mariusza Brodziszewskiego",
                "oddzielenie oceny cywilnoprawnej skuteczności darowizny od oceny karnej zamiaru i przekonania o prawie do dysponowania pojazdem",
                "dopuszczenie i przeprowadzenie dowodów z dokumentów wskazanych w wnioskach dowodowych",
                "przeprowadzenie czynności zmierzających do wszechstronnego wyjaśnienia sprawy, bez pochopnego przesądzania odpowiedzialności karnej",
                "przyjęcie niniejszego stanowiska do akt sprawy DS.3960.2025",
            ],
            closing_statement=(
                "Niniejsze stanowisko opiera się na dokumentach pozostających w dyspozycji "
                "składającego. Okoliczności wynikające wyłącznie z oświadczenia strony zostały "
                "oznaczone. Nie formułuje się twierdzeń wykraczających poza materiał źródłowy."
            ),
            attachments=[
                "umowa darowizny (kopia / informacja o oryginale u Policji)",
                "dowód rejestracyjny pojazdu",
                "polisa OC",
                "dokument Policji – zabezpieczenie umowy darowizny",
                "wezwanie do wydania pojazdu z 07.07.2025 r.",
                "odpis wyroku rozwodowego",
            ],
        )
    )
    return case


def main() -> None:
    case = build_case()
    # Sygnatura już znana — ale workflow PRE_CASE też by zadziałał przed assign_signature()
    ctx = LetterContext(
        sender_name="Mariusz Brodziszewski",
        place="Poznań",
        letter_date=date.today(),
        subject=(
            "Stanowisko procesowe wraz z analizą materiału dowodowego "
            "— pojazd Volkswagen Transporter"
        ),
        prosecutor_ref="DS.3960.2025",
        recipient_lines=[
            "Prokuratura Rejonowa Poznań-Wilda",
            "sygn. DS.3960.2025",
        ],
    )

    out_dir = Path("output/cases/DS_3960_2025")
    out_dir.mkdir(parents=True, exist_ok=True)

    text = CaseLetterRenderer().render(case, context=ctx)
    txt_path = out_dir / "stanowisko_szkic.txt"
    txt_path.write_text(text, encoding="utf-8")
    print("TXT:", txt_path.resolve())

    docx_path = CaseDocxExporter().export(
        case,
        out_dir / "stanowisko_szkic.docx",
        context=ctx,
    )
    print("DOCX:", docx_path.resolve())
    print("Case summary:", case.summary())


if __name__ == "__main__":
    main()