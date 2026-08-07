"""
Build case II Kp 459/26 — skarga na sposób wykonania obowiązku informacyjnego.

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
    Decision,
    DecisionKind,
    EvidenceItem,
    EvidenceWeight,
    Fact,
    FactStatus,
    LegalBasis,
    LegalIssue,
    Party,
)
from knowledge.models.registry import CaseRegistry

CASE_KEY = "II_Kp_459_26"
CASE_SIGNATURE = "II Kp 459/26"
CASE_TITLE = "Skarga na sposób wykonania obowiązku informacyjnego"
CASE_SUBJECT = (
    "odpowiedzi z dnia 23 lipca 2026 r. na skargę z dnia 22 czerwca 2026 r."
)

APPLICANT_NAME = "Arkadiusz Mielewczyk"
AUTHORITY_NAME = "Prezes Sądu Rejonowego w Wejherowie"
PROSECUTOR_REF = "4057-0.Ds.2517.2025"
PLACE = "Wejherowo"
RECIPIENT_LINES = (
    "Prezes Sądu Rejonowego w Wejherowie",
    "SSR Beata Czabotar-Magulska",
    "Sąd Rejonowy w Wejherowie",
    "ul. Wniebowstąpienia 4",
    "84-200 Wejherowo",
)
OUTPUT_DIR = ROOT / "output" / "cases" / CASE_KEY


def build_case() -> Case:
    case = Case(
        title=CASE_TITLE,
        signature=CASE_SIGNATURE,
        metadata={
            "prosecutor_ref": PROSECUTOR_REF,
            "court": "Sąd Rejonowy w Wejherowie",
            "graph_case_id": "case:II_Kp_459_26",
            "case_key": CASE_KEY,
        },
    )
    R = CaseRegistry()

    _add_parties(case)
    _add_evidence(case, R)
    _add_facts(case, R)
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
            name=AUTHORITY_NAME,
            role="authority",
            metadata={
                "address": [
                    "SSR Beata Czabotar-Magulska",
                    "Sąd Rejonowy w Wejherowie",
                    "ul. Wniebowstąpienia 4",
                    "84-200 Wejherowo",
                ]
            },
        )
    )


def _add_evidence(case: Case, R: CaseRegistry) -> None:
    specs: list[tuple[str, EvidenceItem]] = [
        (
            "email_2026_05_25",
            EvidenceItem(
                label="Wiadomość e-mail z 25.05.2026 r.",
                source_ref="email-2026-05-25",
                proves=["skierowanie prośby o konsultację/interwencję"],
                does_not=["rozstrzygnięcie standardu pouczenia"],
                weight=EvidenceWeight.MEDIUM,
                open_questions=[],
            ),
        ),
        (
            "email_2026_06_10",
            EvidenceItem(
                label="Wiadomość e-mail sędziego referenta z 10.06.2026 r.",
                source_ref="email-2026-06-10",
                proves=[
                    "wysłanie wiadomości ze służbowego adresu",
                    "fakt komunikacji sędziego referenta z wnoszącym",
                ],
                does_not=[
                    "automatyczne uznanie pouczenia za prawidłowe",
                    "rozstrzygnięcie, czy forma była dostosowana do adresata",
                ],
                weight=EvidenceWeight.HIGH,
                open_questions=[
                    "czy treść była jednoznaczna dla osoby bez pełnomocnika",
                ],
            ),
        ),
        (
            "skarga_2026_06_22",
            EvidenceItem(
                label="Skarga z 22.06.2026 r.",
                source_ref="skarga-2026-06-22",
                proves=[
                    "złożenie skargi na sposób wykonania obowiązku informacyjnego"
                ],
                does_not=["rozstrzygnięcie skargi"],
                weight=EvidenceWeight.HIGH,
                open_questions=[],
            ),
        ),
        (
            "odpowiedz_prezesa_2026_07_23",
            EvidenceItem(
                label="Odpowiedź Prezesa Sądu z 23.07.2026 r.",
                source_ref="pismo-prezesa-2026-07-23",
                proves=["udzielenie odpowiedzi na skargę"],
                does_not=[
                    "automatyczne uznanie, że standard pouczenia został oceniony merytorycznie",
                ],
                weight=EvidenceWeight.HIGH,
                open_questions=[
                    "czy odpowiedź odnosi się do standardu komunikacji, czy tylko do kompetencji organu",
                ],
            ),
        ),
        (
            "trudnosci_komunikacyjne",
            EvidenceItem(
                label="Dokumentacja trudności komunikacyjnych",
                source_ref="material-trudnosci-komunikacyjne",
                proves=[
                    "działanie bez profesjonalnego pełnomocnika",
                    "zgłaszanie trudności komunikacyjnych istotnych dla standardu pouczeń",
                ],
                does_not=["samodzielne przesądzenie skutków procesowych"],
                weight=EvidenceWeight.MEDIUM,
                open_questions=[],
            ),
        ),
    ]
    for slug, item in specs:
        case.add_evidence(item)
        R.add_evidence(slug, item)


def _add_facts(case: Case, R: CaseRegistry) -> None:
    specs: list[tuple[str, Fact]] = [
        (
            "email_prosba",
            Fact(
                statement=(
                    "W dniu 25.05.2026 r. wnoszący skierował wiadomość e-mail "
                    "z prośbą o konsultację/interwencję."
                ),
                status=FactStatus.SUPPORTED,
                source_refs=[R.E("email_2026_05_25").source_ref],
                evidence_ids=R.E_ids("email_2026_05_25"),
            ),
        ),
        (
            "email_referent",
            Fact(
                statement=(
                    "W dniu 10.06.2026 r. sędzia referent SSR Magdalena Cichańska "
                    "wysłała wiadomość e-mail ze służbowego adresu."
                ),
                status=FactStatus.SUPPORTED,
                source_refs=[R.E("email_2026_06_10").source_ref],
                evidence_ids=R.E_ids("email_2026_06_10"),
            ),
        ),
        (
            "skarga",
            Fact(
                statement=(
                    "W dniu 22.06.2026 r. wnoszący złożył skargę dotyczącą sposobu "
                    "wykonania obowiązku informacyjnego."
                ),
                status=FactStatus.SUPPORTED,
                source_refs=[R.E("skarga_2026_06_22").source_ref],
                evidence_ids=R.E_ids("skarga_2026_06_22"),
            ),
        ),
        (
            "odpowiedz_prezesa",
            Fact(
                statement=(
                    "W dniu 23.07.2026 r. Prezes Sądu Rejonowego w Wejherowie "
                    "udzielił odpowiedzi na skargę."
                ),
                status=FactStatus.SUPPORTED,
                source_refs=[R.E("odpowiedz_prezesa_2026_07_23").source_ref],
                evidence_ids=R.E_ids("odpowiedz_prezesa_2026_07_23"),
            ),
        ),
        (
            "trudnosci_bez_pelnomocnika",
            Fact(
                statement=(
                    "Wnoszący działa bez profesjonalnego pełnomocnika i zgłaszał "
                    "trudności komunikacyjne istotne dla standardu pouczeń; Sąd "
                    "dysponował tą wiedzą przed wiadomością z 10.06.2026 r."
                ),
                status=FactStatus.SUPPORTED,
                source_refs=[R.E("trudnosci_komunikacyjne").source_ref],
                evidence_ids=R.E_ids("trudnosci_komunikacyjne"),
                confidence=0.9,
            ),
        ),
    ]
    for slug, fact in specs:
        case.add_fact(fact)
        R.add_fact(slug, fact)


def _add_legal_bases(case: Case, R: CaseRegistry) -> None:
    specs: list[tuple[str, LegalBasis]] = [
        (
            "art_16_1_kpk",
            LegalBasis(
                reference="art. 16 § 1 k.p.k.",
                note=(
                    "brak pouczenia albo pouczenie mylne nie może wywoływać "
                    "ujemnych skutków procesowych"
                ),
            ),
        ),
        (
            "art_16_2_3_kpk",
            LegalBasis(
                reference="art. 16 § 2–3 k.p.k.",
                note=(
                    "informowanie w miarę potrzeby; dostosowanie pouczenia "
                    "do osoby nieporadnej"
                ),
            ),
        ),
        (
            "sn_i_kzp_6_13",
            LegalBasis(
                reference="uchwała SN I KZP 6/13",
                note="gwarancyjny charakter art. 16 k.p.k.",
            ),
        ),
    ]
    for slug, basis in specs:
        case.add_legal_basis(basis)
        R.add_legal(slug, basis)


def _add_issues(case: Case, R: CaseRegistry) -> None:
    specs: list[tuple[str, LegalIssue]] = [
        (
            "standard_pouczenia",
            LegalIssue(
                question=(
                    "Czy treść i forma wiadomości e-mail z 10.06.2026 r. były "
                    "jednoznaczne oraz dostosowane do sytuacji adresata działającego "
                    "bez profesjonalnego pełnomocnika i zgłaszającego trudności komunikacyjne?"
                ),
                fact_ids=R.F_ids(
                    "email_referent",
                    "trudnosci_bez_pelnomocnika",
                    "email_prosba",
                ),
                legal_basis_ids=R.L_ids(
                    "art_16_1_kpk",
                    "art_16_2_3_kpk",
                    "sn_i_kzp_6_13",
                ),
                hypothesis=(
                    "Standard art. 16 k.p.k. wymaga zrozumiałości i dostosowania "
                    "pouczenia do konkretnego uczestnika, nie tylko formalnego "
                    "wysłania informacji."
                ),
                statute_refs=["art. 16 § 1 k.p.k.", "art. 16 § 2–3 k.p.k."],
                case_law_refs=["uchwała SN I KZP 6/13"],
            ),
        ),
        (
            "zakres_odpowiedzi_prezesa",
            LegalIssue(
                question=(
                    "Czy odpowiedź Prezesa Sądu z 23.07.2026 r. odnosi się do standardu "
                    "wykonania obowiązku informacyjnego, czy ogranicza się jedynie do "
                    "stwierdzenia kompetencji organu i autentyczności korespondencji?"
                ),
                fact_ids=R.F_ids(
                    "skarga",
                    "odpowiedz_prezesa",
                    "email_referent",
                    "trudnosci_bez_pelnomocnika",
                ),
                legal_basis_ids=R.L_ids(
                    "art_16_1_kpk",
                    "art_16_2_3_kpk",
                    "sn_i_kzp_6_13",
                ),
                hypothesis=(
                    "Uprawnienie organu do pouczania i standard wykonania tego obowiązku "
                    "to dwa odrębne zagadnienia prawne; odpowiedź koncentruje się na pierwszym."
                ),
                statute_refs=["art. 16 § 1 k.p.k.", "art. 16 § 2–3 k.p.k."],
                case_law_refs=["uchwała SN I KZP 6/13"],
            ),
        ),
    ]
    for slug, issue in specs:
        case.add_issue(issue)
        R.add_issue(slug, issue)


def _add_arguments(case: Case, R: CaseRegistry) -> None:
    specs: list[tuple[str, Argument]] = [
        (
            "arg_standard_pouczenia",
            Argument(
                issue_id=R.I_id("standard_pouczenia"),
                claim=(
                    "Treść i forma wiadomości z 10.06.2026 r. nie spełniały standardu "
                    "zrozumiałości i dostosowania do sytuacji adresata działającego "
                    "bez pełnomocnika i zgłaszającego trudności komunikacyjne."
                ),
                support_fact_ids=R.F_ids(
                    "email_referent",
                    "trudnosci_bez_pelnomocnika",
                    "email_prosba",
                ),
                legal_basis_ids=R.L_ids(
                    "art_16_1_kpk",
                    "art_16_2_3_kpk",
                    "sn_i_kzp_6_13",
                ),
                status=ArgumentStatus.ADVANCED,
            ),
        ),
        (
            "arg_zakres_odpowiedzi",
            Argument(
                issue_id=R.I_id("zakres_odpowiedzi_prezesa"),
                claim=(
                    "Odpowiedź Prezesa z 23.07.2026 r. ogranicza się do kompetencji organu "
                    "i autentyczności korespondencji, pomijając standard wykonania "
                    "obowiązku informacyjnego."
                ),
                support_fact_ids=R.F_ids(
                    "skarga",
                    "odpowiedz_prezesa",
                    "email_referent",
                    "trudnosci_bez_pelnomocnika",
                ),
                legal_basis_ids=R.L_ids(
                    "art_16_1_kpk",
                    "art_16_2_3_kpk",
                    "sn_i_kzp_6_13",
                ),
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
                "Wnoszący nie kwestionuje autentyczności wiadomości z 10.06.2026 r. "
                "ani prawa Sądu do udzielania pouczeń. Kwestionuje wyłącznie sposób "
                "wykonania obowiązku informacyjnego: jednoznaczność komunikatu oraz "
                "dostosowanie formy do udokumentowanych trudności komunikacyjnych "
                "adresata działającego bez profesjonalnego pełnomocnika. "
                "Wnosi o ponowne rozpoznanie skargi w tym zakresie."
            ),
            fact_ids=R.F_ids(
                "email_prosba",
                "email_referent",
                "skarga",
                "odpowiedz_prezesa",
                "trudnosci_bez_pelnomocnika",
            ),
            legal_basis_ids=R.L_ids(
                "art_16_1_kpk",
                "art_16_2_3_kpk",
                "sn_i_kzp_6_13",
            ),
            issue_ids=R.I_ids(
                "standard_pouczenia",
                "zakres_odpowiedzi_prezesa",
            ),
            argument_ids=R.A_ids(
                "arg_standard_pouczenia",
                "arg_zakres_odpowiedzi",
            ),
            scope_not_challenged=[
                "autentyczność wiadomości e-mail z dnia 10 czerwca 2026 r.",
                "fakt jej wysłania przez sędziego referenta",
                "wykorzystanie służbowego adresu poczty elektronicznej Sądu",
                "uprawnienie Sądu do udzielania pouczeń wynikających z przepisów prawa",
            ],
            issues=[
                "czy treść i forma wiadomości z 10.06.2026 r. były jednoznaczne i dostosowane do sytuacji adresata",
                "czy odpowiedź Prezesa z 23.07.2026 r. odnosi się do standardu komunikacji, a nie tylko do kompetencji organu",
            ],
            assessment_points=[
                "Odpowiedź z 23.07.2026 r. koncentruje się na autentyczności korespondencji i formalnej podstawie pouczenia.",
                "Brak oceny jednoznaczności komunikatu oraz skutków procesowych.",
                "Brak odniesienia do trudności komunikacyjnych w świetle art. 16 § 3 k.p.k.",
                "Uprawnienie organu i standard obowiązku informacyjnego to dwa odrębne zagadnienia prawne.",
            ],
            outcomes=[
                "ponowne rozpoznanie skargi z 22.06.2026 r. w zakresie sposobu wykonania obowiązku informacyjnego",
                "wskazanie charakteru wiadomości e-mail z 10.06.2026 r.",
                "wskazanie skutków procesowych tej wiadomości",
                "wskazanie, czy uwzględniono trudności komunikacyjne i brak pełnomocnika",
                "jednoznaczna komunikacja w dalszym toku sprawy",
                "przyjęcie niniejszego pisma do akt wraz z załącznikami",
            ],
            closing_statement=(
                "Zależy mi na spokojnym i zgodnym z prawem wyjaśnieniu sytuacji. "
                "Nie kwestionuję autorytetu Sądu ani kompetencji sędziego referenta."
            ),
            attachments=[
                "kopia skargi z dnia 22 czerwca 2026 r.",
                "kopia odpowiedzi Prezesa Sądu z dnia 23 lipca 2026 r.",
                "wydruk wiadomości e-mail z dnia 10 czerwca 2026 r.",
                "dokumentacja potwierdzająca trudności komunikacyjne",
            ],
        )
    )


def main() -> int:
    from datetime import date

    from knowledge.models.docx_export import CaseDocxExporter
    from knowledge.models.render import CaseLetterRenderer, LetterContext

    case = build_case()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ctx = LetterContext(
        sender_name=APPLICANT_NAME,
        place=PLACE,
        letter_date=date(2026, 7, 28),
        subject=CASE_SUBJECT,
        prosecutor_ref=PROSECUTOR_REF,
        recipient_lines=list(RECIPIENT_LINES),
    )
    txt_path = OUTPUT_DIR / "pismo.txt"
    txt_path.write_text(
        CaseLetterRenderer().render(case, context=ctx),
        encoding="utf-8",
    )
    print("TXT:", txt_path.resolve())

    try:
        CaseDocxExporter().export(case, OUTPUT_DIR / "pismo.docx", context=ctx)
        print("DOCX:", (OUTPUT_DIR / "pismo.docx").resolve())
    except ImportError as exc:
        print("DOCX skipped:", exc)

    print("Case summary:", case.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())