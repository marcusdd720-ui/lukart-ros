"""
Build case DS.3960.2025 (VW Transporter / Mariusz Brodziszewski).

Evidence-only facts + timeline + evidence analysis.
Exports short letter and full analytical dossier.
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
    EvidenceItem,
    EvidenceWeight,
    Fact,
    FactStatus,
    LegalBasis,
    Party,
    TimelineEvent,
)
from knowledge.models.docx_export import CaseDocxExporter
from knowledge.models.dossier_render import DossierContext, DossierRenderer
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

    case.add_timeline_event(
        TimelineEvent(
            date_label="31.05.2025",
            sort_key="2025-05-31",
            event="Sporządzenie umowy darowizny VW Transporter",
            source="umowa-darowizny",
            procedural_meaning=(
                "Dokument stanowiący podstawę dalszych czynności; "
                "nie przesądza skuteczności cywilnoprawnej."
            ),
        )
    )
    case.add_timeline_event(
        TimelineEvent(
            date_label="31.05.2025",
            sort_key="2025-05-31-b",
            event="Rejestracja pojazdu na Mariusza Brodziszewskiego",
            source="dowod-rejestracyjny",
            procedural_meaning="Czynność administracyjna na podstawie przedstawionych dokumentów.",
        )
    )
    case.add_timeline_event(
        TimelineEvent(
            date_label="po rejestracji",
            sort_key="2025-06-01",
            event="Zawarcie obowiązkowego ubezpieczenia OC",
            source="polisa-oc",
            procedural_meaning="Jawne wykonywanie obowiązków związanych z pojazdem.",
        )
    )
    case.add_timeline_event(
        TimelineEvent(
            date_label="07.07.2025",
            sort_key="2025-07-07",
            event="Wezwanie do wydania pojazdu",
            source="wezwanie-2025-07-07",
            procedural_meaning="Ujawnienie sporu pomiędzy stronami.",
        )
    )
    case.add_timeline_event(
        TimelineEvent(
            date_label="wg dokumentacji Policji",
            sort_key="2025-07-08",
            event="Zabezpieczenie oryginału umowy darowizny",
            source="notatka-policji-zabezpieczenie-umowy",
            procedural_meaning="Oryginał w dyspozycji organów — możliwa bezpośrednia ocena.",
        )
    )
    case.add_timeline_event(
        TimelineEvent(
            date_label="12.05.2026",
            sort_key="2026-05-12",
            event="Rozwód stron",
            source="wyrok-rozwodowy",
            procedural_meaning=(
                "Zdarzenie po czynnościach dotyczących pojazdu; tło konfliktu, "
                "nie przesłanka automatycznej bezprawności."
            ),
        )
    )
    case.add_timeline_event(
        TimelineEvent(
            date_label="stan na dzień stanowiska",
            sort_key="2099-01-01",
            event="Pojazd na posesji Mariusza (oświadczenie)",
            source="oswiadczenie-mariusza-posesja",
            procedural_meaning="Oświadczenie strony; podlega ocenie łącznie z dokumentami.",
        )
    )

    case.add_evidence(
        EvidenceItem(
            label="Umowa darowizny",
            source_ref="umowa-darowizny",
            proves=[
                "istnienie pisemnej umowy pomiędzy wskazanymi stronami",
                "oznaczenie pojazdu (w tym VIN) jako przedmiotu czynności",
            ],
            does_not=[
                "samodzielne przesądzenie skuteczności cywilnoprawnej darowizny",
                "automatyczne wyłączenie sporu co do prawa do pojazdu",
            ],
            weight=EvidenceWeight.HIGH,
            open_questions=[
                "czy treść i forma umowy nie budzą wątpliwości co do oświadczeń woli",
                "jak organ oceni związek umowy z późniejszą rejestracją",
            ],
        )
    )
    case.add_evidence(
        EvidenceItem(
            label="Dowód rejestracyjny",
            source_ref="dowod-rejestracyjny",
            proves=[
                "dokonanie rejestracji pojazdu przez organ administracji",
                "wpisanie Mariusza Brodziszewskiego w dowodzie rejestracyjnym",
            ],
            does_not=[
                "konstytutywne nabycie własności w rozumieniu prawa cywilnego",
                "rozstrzygnięcie sporu karnego",
            ],
            weight=EvidenceWeight.HIGH,
            open_questions=[
                "na podstawie jakiego kompletu dokumentów organ dokonał wpisu",
            ],
        )
    )
    case.add_evidence(
        EvidenceItem(
            label="Polisa OC",
            source_ref="polisa-oc",
            proves=[
                "zawarcie obowiązkowego ubezpieczenia OC dla pojazdu",
                "wykonywanie czynności charakterystycznych dla bieżącego dysponowania pojazdem",
            ],
            does_not=[
                "prawo własności",
                "brak sporu pomiędzy stronami",
            ],
            weight=EvidenceWeight.MEDIUM,
            open_questions=[],
        )
    )
    case.add_evidence(
        EvidenceItem(
            label="Dokument Policji – zabezpieczenie umowy",
            source_ref="notatka-policji-zabezpieczenie-umowy",
            proves=[
                "zabezpieczenie oryginału umowy darowizny przez Policję",
                "pozostawanie oryginału w dyspozycji organów",
            ],
            does_not=[
                "oceny merytorycznej treści umowy",
                "wniosku o odpowiedzialności karnej którejkolwiek ze stron",
            ],
            weight=EvidenceWeight.HIGH,
            open_questions=[
                "treść protokołu/notatki w zakresie okoliczności zabezpieczenia",
            ],
        )
    )
    case.add_evidence(
        EvidenceItem(
            label="Wezwanie do wydania pojazdu (07.07.2025)",
            source_ref="wezwanie-2025-07-07",
            proves=[
                "istnienie sporu co do prawa do dysponowania pojazdem",
                "moment ujawnienia konfliktu po rejestracji i ubezpieczeniu",
            ],
            does_not=[
                "rozstrzygnięcie, która strona ma rację",
                "udowodnienie znamion czynu zabronionego",
            ],
            weight=EvidenceWeight.MEDIUM,
            open_questions=[
                "pełna treść żądań i podstaw wskazanych przez wzywającego",
            ],
        )
    )
    case.add_evidence(
        EvidenceItem(
            label="Wyrok rozwodowy",
            source_ref="wyrok-rozwodowy",
            proves=["rozwiązanie małżeństwa stron przez rozwód"],
            does_not=[
                "automatyczne unieważnienie wcześniejszych czynności dotyczących pojazdu",
                "przesądzenie odpowiedzialności karnej",
            ],
            weight=EvidenceWeight.CONTEXT,
            open_questions=[],
        )
    )
    case.add_evidence(
        EvidenceItem(
            label="Oświadczenie o miejscu przechowywania pojazdu",
            source_ref="oswiadczenie-mariusza-posesja",
            proves=[
                "stanowisko Mariusza, że pojazd jest na jego posesji i dostępny dla organów",
            ],
            does_not=["samodzielnego potwierdzenia faktu bez weryfikacji"],
            weight=EvidenceWeight.LOW,
            open_questions=[
                "czy organ zechce dokonać oględzin / potwierdzenia lokalizacji",
            ],
        )
    )

    b1 = LegalBasis(
        reference="art. 7 k.p.k.",
        note="swobodna ocena dowodów — nie dowolna",
    )
    b2 = LegalBasis(
        reference="art. 4 k.p.k.",
        note="zasada obiektywizmu",
    )
    b3 = LegalBasis(
        reference="art. 410 k.p.k.",
        note="całokształt ujawnionych okoliczności",
    )
    b4 = LegalBasis(
        reference="art. 167 k.p.k.",
        note="inicjatywa dowodowa",
    )
    b5 = LegalBasis(
        reference="[ORZECZNICTWO – DO UZUPEŁNIENIA PO WERYFIKACJI]",
        note="art. 7 i 410 k.p.k. — po weryfikacji sygnatur",
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
                "czy czynności Mariusza były podejmowane w oparciu o dokumenty i w przekonaniu o prawie do dysponowania pojazdem",
                "czy sam późniejszy spór wystarcza do przyjęcia znamion czynu zabronionego bez oceny całokształtu materiału",
                "czy należy oddzielić skutki cywilnoprawne darowizny od oceny karnej zachowania",
            ],
            assessment_points=[
                "Umowa, rejestracja i polisa OC tworzą jawny ciąg czynności.",
                "Rejestracja nie konstytuuje własności, ale potwierdza ocenę dokumentów przez organ administracji.",
                "Spór ujawnił się po rejestracji i ubezpieczeniu — chronologia ma znaczenie dla oceny zamiaru.",
                "Oryginał umowy jest w dyspozycji organów.",
                "Oświadczenie o posesji jest oświadczeniem strony.",
                "Brak podstaw do automatycznego przesądzenia znamion czynu bez wszechstronnej oceny (art. 7 i 410 k.p.k.).",
            ],
            outcomes=[
                "uwzględnienie całokształtu dokumentów przy ocenie zachowania Mariusza Brodziszewskiego",
                "oddzielenie oceny cywilnoprawnej darowizny od oceny karnej zamiaru",
                "dopuszczenie i przeprowadzenie dowodów z wskazanych dokumentów",
                "wszechstronne wyjaśnienie sprawy bez pochopnego przesądzania odpowiedzialności karnej",
                "przyjęcie niniejszego stanowiska do akt sprawy DS.3960.2025",
            ],
            closing_statement=(
                "Niniejsze stanowisko opiera się na dokumentach pozostających w dyspozycji "
                "składającego. Okoliczności wynikające wyłącznie z oświadczenia strony zostały "
                "oznaczone."
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
    out_dir = Path("output/cases/DS_3960_2025")
    out_dir.mkdir(parents=True, exist_ok=True)

    letter_ctx = LetterContext(
        sender_name="Mariusz Brodziszewski",
        place="Poznań",
        letter_date=date.today(),
        subject=(
            "Stanowisko procesowe wraz z analizą materiału dowodowego "
            "— pojazd Volkswagen Transporter"
        ),
        prosecutor_ref="DS.3960.2025",
        recipient_lines=["Prokuratura Rejonowa Poznań-Wilda"],
    )
    letter_text = CaseLetterRenderer().render(case, context=letter_ctx)
    letter_path = out_dir / "stanowisko_szkic.txt"
    letter_path.write_text(letter_text, encoding="utf-8")
    print("LETTER TXT:", letter_path.resolve())

    CaseDocxExporter().export(
        case,
        out_dir / "stanowisko_szkic.docx",
        context=letter_ctx,
    )
    print("LETTER DOCX:", (out_dir / "stanowisko_szkic.docx").resolve())

    dossier_ctx = DossierContext(
        author_name="Mariusz Brodziszewski",
        place="Poznań",
        dossier_date=date.today(),
        subject=(
            "Stanowisko procesowe wraz z analizą materiału dowodowego "
            "— pojazd Volkswagen Transporter"
        ),
        recipient_lines=["Prokuratura Rejonowa Poznań-Wilda"],
    )
    dossier_text = DossierRenderer().render(case, context=dossier_ctx)
    dossier_path = out_dir / "stanowisko_dossier.txt"
    dossier_path.write_text(dossier_text, encoding="utf-8")
    print("DOSSIER TXT:", dossier_path.resolve())
    print("Case summary:", case.summary())


if __name__ == "__main__":
    main()