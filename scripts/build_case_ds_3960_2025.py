"""
Build case DS.3960.2025 — VW Transporter / Mariusz Brodziszewski.

Pure domain factory with CaseRegistry slug mapping.
No I/O. No renderer imports at module level.

  build_case()  → Case
  main()        → optional CLI export
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from knowledge.models.case import (
    Argument,
    ArgumentStatus,
    Case,
    CaseStatus,
    Decision,
    DecisionKind,
    EvidenceItem,
    EvidenceWeight,
    Fact,
    FactStatus,
    LegalBasis,
    LegalIssue,
    Party,
    TimelineEvent,
)
from knowledge.models.registry import CaseRegistry

CASE_KEY = "DS_3960_2025"
CASE_SIGNATURE = "DS.3960.2025"
CASE_TITLE = "Stanowisko procesowe wraz z analizą materiału dowodowego"
CASE_WORKING_TITLE = "VW Transporter – czynności po umowie darowizny"
CASE_SUBJECT = (
    "Stanowisko procesowe wraz z analizą materiału dowodowego "
    "— pojazd Volkswagen Transporter"
)

VEHICLE_MAKE = "Volkswagen Transporter"
VEHICLE_REG = "PZ2V467"
VEHICLE_VIN = "WV1ZZZ7HZDH008410"

APPLICANT_NAME = "Mariusz Brodziszewski"
OTHER_PARTY_NAME = "Katarzyna Anna Brodziszewska"
AUTHORITY_NAME = "Prokuratura Rejonowa Poznań-Wilda"
PLACE = "Poznań"
RECIPIENT_LINES = (AUTHORITY_NAME,)
OUTPUT_DIR = ROOT / "output" / "cases" / CASE_KEY


def build_case() -> Case:
    case = Case(
        title=CASE_TITLE,
        working_title=CASE_WORKING_TITLE,
        signature=CASE_SIGNATURE,
        status=CaseStatus.INTAKE,
        metadata={
            "prosecutor_ref": CASE_SIGNATURE,
            "vehicle": VEHICLE_MAKE,
            "reg": VEHICLE_REG,
            "vin": VEHICLE_VIN,
            "contact_sylwia": "Sylwia Grochowska",
            "case_key": CASE_KEY,
        },
    )
    R = CaseRegistry()

    _add_parties(case)
    _add_evidence(case, R)
    _add_facts(case, R)
    _add_timeline(case, R)
    _add_legal_bases(case, R)
    _add_issues(case, R)
    _add_arguments(case, R)
    _add_decision(case, R)
    return case


def _add_parties(case: Case) -> None:
    case.add_party(
        Party(
            name=APPLICANT_NAME,
            role="applicant",
            metadata={"acts_without_counsel": True},
        )
    )
    case.add_party(
        Party(
            name=OTHER_PARTY_NAME,
            role="other_party",
            metadata={"relation": "former_spouse"},
        )
    )
    case.add_party(
        Party(
            name=AUTHORITY_NAME,
            role="authority",
            metadata={"case_ref": CASE_SIGNATURE},
        )
    )


def _add_evidence(case: Case, R: CaseRegistry) -> None:
    specs: list[tuple[str, EvidenceItem]] = [
        (
            "umowa_darowizny",
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
            ),
        ),
        (
            "dowod_rejestracyjny",
            EvidenceItem(
                label="Dowód rejestracyjny",
                source_ref="dowod-rejestracyjny",
                proves=[
                    "dokonanie rejestracji pojazdu przez organ administracji",
                    f"wpisanie {APPLICANT_NAME} w dowodzie rejestracyjnym",
                ],
                does_not=[
                    "konstytutywne nabycie własności w rozumieniu prawa cywilnego",
                    "rozstrzygnięcie sporu karnego",
                ],
                weight=EvidenceWeight.HIGH,
                open_questions=[
                    "na podstawie jakiego kompletu dokumentów organ dokonał wpisu",
                ],
            ),
        ),
        (
            "polisa_oc",
            EvidenceItem(
                label="Polisa OC",
                source_ref="polisa-oc",
                proves=[
                    "zawarcie obowiązkowego ubezpieczenia OC dla pojazdu",
                    "wykonywanie czynności charakterystycznych dla bieżącego dysponowania pojazdem",
                ],
                does_not=["prawo własności", "brak sporu pomiędzy stronami"],
                weight=EvidenceWeight.MEDIUM,
                open_questions=[],
            ),
        ),
        (
            "notatka_policji",
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
            ),
        ),
        (
            "wezwanie_wydania",
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
            ),
        ),
        (
            "wyrok_rozwodowy",
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
            ),
        ),
        (
            "oswiadczenie_posesja",
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
            ),
        ),
    ]
    for slug, item in specs:
        case.add_evidence(item)
        R.add_evidence(slug, item)


def _add_facts(case: Case, R: CaseRegistry) -> None:
    specs: list[tuple[str, Fact]] = [
        (
            "darowizna_pojazdu",
            Fact(
                statement=(
                    f"Sporządzono pisemną umowę darowizny pojazdu marki {VEHICLE_MAKE} "
                    f"pomiędzy {OTHER_PARTY_NAME} jako darczyńcą a {APPLICANT_NAME} "
                    f"jako obdarowanym; dokument identyfikuje pojazd (w tym VIN {VEHICLE_VIN})."
                ),
                status=FactStatus.SUPPORTED,
                source_refs=[R.E("umowa_darowizny").source_ref],
                evidence_ids=R.E_ids("umowa_darowizny"),
            ),
        ),
        (
            "rejestracja_pojazdu",
            Fact(
                statement=(
                    "W dniu 31.05.2025 r. właściwy organ administracji dokonał rejestracji "
                    f"pojazdu z wpisem {APPLICANT_NAME} jako właściciela w dowodzie "
                    "rejestracyjnym (czynność administracyjna; nie przesądza sama przez się "
                    "skuteczności nabycia własności w rozumieniu prawa cywilnego)."
                ),
                status=FactStatus.SUPPORTED,
                source_refs=[R.E("dowod_rejestracyjny").source_ref],
                evidence_ids=R.E_ids("dowod_rejestracyjny"),
            ),
        ),
        (
            "polisa_oc",
            Fact(
                statement=(
                    "Dla przedmiotowego pojazdu zawarto umowę obowiązkowego ubezpieczenia OC."
                ),
                status=FactStatus.SUPPORTED,
                source_refs=[R.E("polisa_oc").source_ref],
                evidence_ids=R.E_ids("polisa_oc"),
            ),
        ),
        (
            "zabezpieczenie_umowy",
            Fact(
                statement=(
                    "Funkcjonariusze Policji zabezpieczyli oryginał umowy darowizny; dokument "
                    "pozostaje w dyspozycji organów prowadzących postępowanie."
                ),
                status=FactStatus.SUPPORTED,
                source_refs=[R.E("notatka_policji").source_ref],
                evidence_ids=R.E_ids("notatka_policji"),
            ),
        ),
        (
            "wezwanie_wydania",
            Fact(
                statement=(
                    f"W dniu 07.07.2025 r. sporządzono wezwanie skierowane do {APPLICANT_NAME} "
                    "do wydania pojazdu — dokument potwierdza istnienie sporu "
                    "co do prawa do dysponowania pojazdem."
                ),
                status=FactStatus.SUPPORTED,
                source_refs=[R.E("wezwanie_wydania").source_ref],
                evidence_ids=R.E_ids("wezwanie_wydania"),
            ),
        ),
        (
            "rozwod",
            Fact(
                statement=(
                    f"Małżeństwo {APPLICANT_NAME} i {OTHER_PARTY_NAME} zostało "
                    "rozwiązane przez rozwód (okoliczność wynikająca z odpisu wyroku; znaczenie "
                    "prawne dla oceny wcześniejszych czynności nie jest tu przesądzane)."
                ),
                status=FactStatus.SUPPORTED,
                source_refs=[R.E("wyrok_rozwodowy").source_ref],
                evidence_ids=R.E_ids("wyrok_rozwodowy"),
            ),
        ),
        (
            "posesja_oswiadczenie",
            Fact(
                statement=(
                    f"{APPLICANT_NAME} oświadcza, że pojazd pozostaje na jego posesji, "
                    "nie został ukryty, zbyty ani przekazany osobom trzecim i jest dostępny "
                    "dla organów prowadzących postępowanie."
                ),
                status=FactStatus.SUPPORTED,
                source_refs=[R.E("oswiadczenie_posesja").source_ref],
                evidence_ids=R.E_ids("oswiadczenie_posesja"),
                confidence=0.85,
                metadata={"kind": "party_statement"},
            ),
        ),
    ]
    for slug, fact in specs:
        case.add_fact(fact)
        R.add_fact(slug, fact)


def _add_timeline(case: Case, R: CaseRegistry) -> None:
    specs: list[tuple[str, TimelineEvent]] = [
        (
            "t_umowa",
            TimelineEvent(
                date_label="31.05.2025",
                sort_key="2025-05-31",
                event=f"Sporządzenie umowy darowizny {VEHICLE_MAKE}",
                source=R.E("umowa_darowizny").source_ref,
                evidence_ids=R.E_ids("umowa_darowizny"),
                procedural_meaning=(
                    "Dokument stanowiący podstawę dalszych czynności; "
                    "nie przesądza skuteczności cywilnoprawnej."
                ),
            ),
        ),
        (
            "t_rejestracja",
            TimelineEvent(
                date_label="31.05.2025",
                sort_key="2025-05-31-b",
                event=f"Rejestracja pojazdu na {APPLICANT_NAME}",
                source=R.E("dowod_rejestracyjny").source_ref,
                evidence_ids=R.E_ids("dowod_rejestracyjny"),
                procedural_meaning=(
                    "Czynność administracyjna na podstawie przedstawionych dokumentów."
                ),
            ),
        ),
        (
            "t_oc",
            TimelineEvent(
                date_label="po rejestracji",
                sort_key="2025-06-01",
                event="Zawarcie obowiązkowego ubezpieczenia OC",
                source=R.E("polisa_oc").source_ref,
                evidence_ids=R.E_ids("polisa_oc"),
                procedural_meaning="Jawne wykonywanie obowiązków związanych z pojazdem.",
            ),
        ),
        (
            "t_wezwanie",
            TimelineEvent(
                date_label="07.07.2025",
                sort_key="2025-07-07",
                event="Wezwanie do wydania pojazdu",
                source=R.E("wezwanie_wydania").source_ref,
                evidence_ids=R.E_ids("wezwanie_wydania"),
                procedural_meaning="Ujawnienie sporu pomiędzy stronami.",
            ),
        ),
        (
            "t_policja",
            TimelineEvent(
                date_label="wg dokumentacji Policji",
                sort_key="2025-07-08",
                event="Zabezpieczenie oryginału umowy darowizny",
                source=R.E("notatka_policji").source_ref,
                evidence_ids=R.E_ids("notatka_policji"),
                procedural_meaning=(
                    "Oryginał w dyspozycji organów — możliwa bezpośrednia ocena."
                ),
            ),
        ),
        (
            "t_rozwod",
            TimelineEvent(
                date_label="12.05.2026",
                sort_key="2026-05-12",
                event="Rozwód stron",
                source=R.E("wyrok_rozwodowy").source_ref,
                evidence_ids=R.E_ids("wyrok_rozwodowy"),
                procedural_meaning=(
                    "Zdarzenie po czynnościach dotyczących pojazdu; tło konfliktu, "
                    "nie przesłanka automatycznej bezprawności."
                ),
            ),
        ),
        (
            "t_posesja",
            TimelineEvent(
                date_label="stan na dzień stanowiska",
                sort_key="2099-01-01",
                event="Pojazd na posesji Mariusza (oświadczenie)",
                source=R.E("oswiadczenie_posesja").source_ref,
                evidence_ids=R.E_ids("oswiadczenie_posesja"),
                procedural_meaning=(
                    "Oświadczenie strony; podlega ocenie łącznie z dokumentami."
                ),
            ),
        ),
    ]
    for slug, event in specs:
        case.add_timeline_event(event)
        R.add_timeline(slug, event)


def _add_legal_bases(case: Case, R: CaseRegistry) -> None:
    specs: list[tuple[str, LegalBasis]] = [
        (
            "art_7_kpk",
            LegalBasis(
                reference="art. 7 k.p.k.",
                note="swobodna ocena dowodów — nie dowolna",
            ),
        ),
        (
            "art_4_kpk",
            LegalBasis(
                reference="art. 4 k.p.k.",
                note="zasada obiektywizmu",
            ),
        ),
        (
            "art_410_kpk",
            LegalBasis(
                reference="art. 410 k.p.k.",
                note="całokształt ujawnionych okoliczności",
            ),
        ),
        (
            "art_167_kpk",
            LegalBasis(
                reference="art. 167 k.p.k.",
                note="inicjatywa dowodowa",
            ),
        ),
    ]
    for slug, basis in specs:
        case.add_legal_basis(basis)
        R.add_legal(slug, basis)


def _add_issues(case: Case, R: CaseRegistry) -> None:
    specs: list[tuple[str, LegalIssue]] = [
        (
            "zamiar_i_dokumenty",
            LegalIssue(
                question=(
                    f"Czy czynności {APPLICANT_NAME} dotyczące pojazdu "
                    "były podejmowane w oparciu o dokumenty i w przekonaniu "
                    "o przysługującym prawie do dysponowania pojazdem?"
                ),
                fact_ids=R.F_ids(
                    "darowizna_pojazdu",
                    "rejestracja_pojazdu",
                    "polisa_oc",
                    "zabezpieczenie_umowy",
                    "posesja_oswiadczenie",
                ),
                legal_basis_ids=R.L_ids("art_7_kpk", "art_410_kpk"),
                hypothesis=(
                    "Jawny ciąg: umowa → rejestracja → polisa OC + oświadczenie "
                    "o posesji wskazują na działanie w oparciu o dokumenty."
                ),
                statute_refs=["art. 7 k.p.k.", "art. 410 k.p.k."],
            ),
        ),
        (
            "spor_nie_znamiona",
            LegalIssue(
                question=(
                    "Czy sam późniejszy spór (wezwanie do wydania pojazdu) "
                    "wystarcza do przyjęcia znamion czynu zabronionego "
                    "bez oceny całokształtu materiału dowodowego?"
                ),
                fact_ids=R.F_ids(
                    "wezwanie_wydania",
                    "darowizna_pojazdu",
                    "rejestracja_pojazdu",
                    "polisa_oc",
                    "zabezpieczenie_umowy",
                ),
                legal_basis_ids=R.L_ids("art_7_kpk", "art_410_kpk"),
                hypothesis=(
                    "Spór ujawnił się po rejestracji i ubezpieczeniu. "
                    "Sam fakt wezwania nie przesądza znamion."
                ),
                statute_refs=["art. 7 k.p.k.", "art. 410 k.p.k."],
            ),
        ),
        (
            "cywilne_vs_karne",
            LegalIssue(
                question=(
                    "Czy należy oddzielić skutki cywilnoprawne darowizny "
                    f"od oceny karnej zachowania {APPLICANT_NAME}?"
                ),
                fact_ids=R.F_ids(
                    "darowizna_pojazdu",
                    "rejestracja_pojazdu",
                    "rozwod",
                ),
                legal_basis_ids=R.L_ids("art_7_kpk", "art_4_kpk", "art_410_kpk"),
                hypothesis=(
                    "Rejestracja i umowa mają znaczenie dowodowe, "
                    "ale nie przesądzają automatycznie odpowiedzialności karnej."
                ),
                statute_refs=["art. 7 k.p.k.", "art. 4 k.p.k.", "art. 410 k.p.k."],
            ),
        ),
    ]
    for slug, issue in specs:
        case.add_issue(issue)
        R.add_issue(slug, issue)


def _add_arguments(case: Case, R: CaseRegistry) -> None:
    specs: list[tuple[str, Argument]] = [
        (
            "arg_zamiar",
            Argument(
                issue_id=R.I_id("zamiar_i_dokumenty"),
                claim=(
                    f"Czynności {APPLICANT_NAME} (umowa, rejestracja, OC, posiadanie) "
                    "były podejmowane w oparciu o dokumenty i w przekonaniu o prawie "
                    "do dysponowania pojazdem."
                ),
                support_fact_ids=R.F_ids(
                    "darowizna_pojazdu",
                    "rejestracja_pojazdu",
                    "polisa_oc",
                    "zabezpieczenie_umowy",
                    "posesja_oswiadczenie",
                ),
                legal_basis_ids=R.L_ids("art_7_kpk", "art_410_kpk"),
                status=ArgumentStatus.ADVANCED,
            ),
        ),
        (
            "arg_spor",
            Argument(
                issue_id=R.I_id("spor_nie_znamiona"),
                claim=(
                    "Sam fakt późniejszego sporu (wezwanie do wydania) nie wystarcza "
                    "do przyjęcia znamion czynu zabronionego bez oceny całokształtu materiału."
                ),
                support_fact_ids=R.F_ids(
                    "wezwanie_wydania",
                    "darowizna_pojazdu",
                    "rejestracja_pojazdu",
                    "polisa_oc",
                    "zabezpieczenie_umowy",
                ),
                legal_basis_ids=R.L_ids("art_7_kpk", "art_410_kpk"),
                status=ArgumentStatus.ADVANCED,
            ),
        ),
        (
            "arg_cywilne_karne",
            Argument(
                issue_id=R.I_id("cywilne_vs_karne"),
                claim=(
                    "Skutki cywilnoprawne darowizny należy oddzielić od oceny karnej "
                    "zachowania; rejestracja i umowa mają znaczenie dowodowe, "
                    "ale nie przesądzają automatycznie odpowiedzialności karnej."
                ),
                support_fact_ids=R.F_ids(
                    "darowizna_pojazdu",
                    "rejestracja_pojazdu",
                    "rozwod",
                ),
                legal_basis_ids=R.L_ids("art_7_kpk", "art_4_kpk", "art_410_kpk"),
                status=ArgumentStatus.ADVANCED,
            ),
        ),
    ]
    for slug, arg in specs:
        case.add_argument(arg)
        R.add_argument(slug, arg)


def _add_decision(case: Case, R: CaseRegistry) -> None:
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
            fact_ids=R.F_ids(
                "darowizna_pojazdu",
                "rejestracja_pojazdu",
                "polisa_oc",
                "zabezpieczenie_umowy",
                "wezwanie_wydania",
                "rozwod",
                "posesja_oswiadczenie",
            ),
            legal_basis_ids=R.L_ids(
                "art_7_kpk",
                "art_4_kpk",
                "art_410_kpk",
                "art_167_kpk",
            ),
            issue_ids=R.I_ids(
                "zamiar_i_dokumenty",
                "spor_nie_znamiona",
                "cywilne_vs_karne",
            ),
            argument_ids=R.A_ids(
                "arg_zamiar",
                "arg_spor",
                "arg_cywilne_karne",
            ),
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
                "Jawna rejestracja pojazdu na własne nazwisko oraz zawarcie umowy OC są obiektywnie sprzeczne z typowym sposobem działania osoby dążącej do przywłaszczenia.",
            ],
            outcomes=[
                f"uwzględnienie całokształtu dokumentów przy ocenie zachowania {APPLICANT_NAME}",
                "oddzielenie oceny cywilnoprawnej darowizny od oceny karnej zamiaru",
                "dopuszczenie i przeprowadzenie dowodów z wskazanych dokumentów",
                "wszechstronne wyjaśnienie sprawy bez pochopnego przesądzania odpowiedzialności karnej",
                f"przyjęcie niniejszego stanowiska do akt sprawy {CASE_SIGNATURE}",
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


def main() -> int:
    from datetime import date

    from knowledge.models.docx_export import CaseDocxExporter
    from knowledge.models.dossier_render import DossierContext, DossierRenderer
    from knowledge.models.render import CaseLetterRenderer, LetterContext

    case = build_case()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    letter_ctx = LetterContext(
        sender_name=APPLICANT_NAME,
        place=PLACE,
        letter_date=date.today(),
        subject=CASE_SUBJECT,
        prosecutor_ref=CASE_SIGNATURE,
        recipient_lines=list(RECIPIENT_LINES),
    )
    letter_path = OUTPUT_DIR / "stanowisko_szkic.txt"
    letter_path.write_text(
        CaseLetterRenderer().render(case, context=letter_ctx),
        encoding="utf-8",
    )
    print("LETTER TXT:", letter_path.resolve())

    try:
        CaseDocxExporter().export(
            case,
            OUTPUT_DIR / "stanowisko_szkic.docx",
            context=letter_ctx,
        )
        print("LETTER DOCX:", (OUTPUT_DIR / "stanowisko_szkic.docx").resolve())
    except ImportError as exc:
        print("LETTER DOCX skipped:", exc)

    dossier_ctx = DossierContext(
        author_name=APPLICANT_NAME,
        place=PLACE,
        dossier_date=date.today(),
        subject=CASE_SUBJECT,
        recipient_lines=list(RECIPIENT_LINES),
    )
    dossier_path = OUTPUT_DIR / "stanowisko_dossier.txt"
    dossier_path.write_text(
        DossierRenderer().render(case, context=dossier_ctx),
        encoding="utf-8",
    )
    print("DOSSIER TXT:", dossier_path.resolve())
    print("Case summary:", case.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())