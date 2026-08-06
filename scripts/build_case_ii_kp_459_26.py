"""Build case II Kp 459/26 and export letter (txt + docx)."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from knowledge.models.case import (
    Argument,
    ArgumentStatus,
    Case,
    Decision,
    DecisionKind,
    Fact,
    FactStatus,
    LegalBasis,
    LegalIssue,
    Party,
)
from knowledge.models.docx_export import CaseDocxExporter
from knowledge.models.render import CaseLetterRenderer, LetterContext


def build_case() -> Case:
    case = Case(
        title="Skarga na sposób wykonania obowiązku informacyjnego",
        signature="II Kp 459/26",
        metadata={
            "prosecutor_ref": "4057-0.Ds.2517.2025",
            "court": "Sąd Rejonowy w Wejherowie",
            "graph_case_id": "case:II_Kp_459_26",
        },
    )

    case.add_party(
        Party(
            name="Arkadiusz Mielewczyk",
            role="applicant",
            metadata={"acts_without_counsel": True},
        )
    )
    case.add_party(
        Party(
            name="Prezes Sądu Rejonowego w Wejherowie",
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

    f1 = Fact(
        statement=(
            "W dniu 25.05.2026 r. wnoszący skierował wiadomość e-mail "
            "z prośbą o konsultację/interwencję."
        ),
        status=FactStatus.SUPPORTED,
        source_refs=["email-2026-05-25"],
    )
    f2 = Fact(
        statement=(
            "W dniu 10.06.2026 r. sędzia referent SSR Magdalena Cichańska "
            "wysłała wiadomość e-mail ze służbowego adresu."
        ),
        status=FactStatus.SUPPORTED,
        source_refs=["email-2026-06-10"],
    )
    f3 = Fact(
        statement=(
            "W dniu 22.06.2026 r. wnoszący złożył skargę dotyczącą sposobu "
            "wykonania obowiązku informacyjnego."
        ),
        status=FactStatus.SUPPORTED,
        source_refs=["skarga-2026-06-22"],
    )
    f4 = Fact(
        statement=(
            "W dniu 23.07.2026 r. Prezes Sądu Rejonowego w Wejherowie "
            "udzielił odpowiedzi na skargę."
        ),
        status=FactStatus.SUPPORTED,
        source_refs=["pismo-prezesa-2026-07-23"],
    )
    f5 = Fact(
        statement=(
            "Wnoszący działa bez profesjonalnego pełnomocnika i zgłaszał "
            "trudności komunikacyjne istotne dla standardu pouczeń; Sąd "
            "dysponował tą wiedzą przed wiadomością z 10.06.2026 r."
        ),
        status=FactStatus.SUPPORTED,
        source_refs=["material-trudnosci-komunikacyjne"],
        confidence=0.9,
    )
    for fact in (f1, f2, f3, f4, f5):
        case.add_fact(fact)

    b1 = LegalBasis(
        reference="art. 16 § 1 k.p.k.",
        note="brak pouczenia albo pouczenie mylne nie może wywoływać ujemnych skutków procesowych",
    )
    b2 = LegalBasis(
        reference="art. 16 § 2–3 k.p.k.",
        note="informowanie w miarę potrzeby; dostosowanie pouczenia do osoby nieporadnej",
    )
    b3 = LegalBasis(
        reference="uchwała SN I KZP 6/13",
        note="gwarancyjny charakter art. 16 k.p.k.",
    )
    for basis in (b1, b2, b3):
        case.add_legal_basis(basis)

    # ----- LegalIssues (CASE-011) -----
    issue1 = LegalIssue(
        question=(
            "Czy treść i forma wiadomości e-mail z 10.06.2026 r. były "
            "jednoznaczne oraz dostosowane do sytuacji adresata działającego "
            "bez profesjonalnego pełnomocnika i zgłaszającego trudności komunikacyjne?"
        ),
        fact_ids=[f2.id, f5.id, f1.id],
        legal_basis_ids=[b1.id, b2.id, b3.id],
        hypothesis=(
            "Standard art. 16 k.p.k. wymaga zrozumiałości i dostosowania "
            "pouczenia do konkretnego uczestnika, nie tylko formalnego wysłania informacji."
        ),
        statute_refs=["art. 16 § 1 k.p.k.", "art. 16 § 2–3 k.p.k."],
        case_law_refs=["uchwała SN I KZP 6/13"],
    )
    issue2 = LegalIssue(
        question=(
            "Czy odpowiedź Prezesa Sądu z 23.07.2026 r. odnosi się do standardu "
            "wykonania obowiązku informacyjnego, czy ogranicza się jedynie do "
            "stwierdzenia kompetencji organu i autentyczności korespondencji?"
        ),
        fact_ids=[f3.id, f4.id, f2.id, f5.id],
        legal_basis_ids=[b1.id, b2.id, b3.id],
        hypothesis=(
            "Uprawnienie organu do pouczania i standard wykonania tego obowiązku "
            "to dwa odrębne zagadnienia prawne; odpowiedź koncentruje się na pierwszym."
        ),
        statute_refs=["art. 16 § 1 k.p.k.", "art. 16 § 2–3 k.p.k."],
        case_law_refs=["uchwała SN I KZP 6/13"],
    )

    for issue in (issue1, issue2):
        case.add_issue(issue)

    # ----- Arguments (CASE-012) -----
    arg1 = Argument(
        issue_id=issue1.id,
        claim=(
            "Treść i forma wiadomości z 10.06.2026 r. nie spełniały standardu "
            "zrozumiałości i dostosowania do sytuacji adresata działającego "
            "bez pełnomocnika i zgłaszającego trudności komunikacyjne."
        ),
        support_fact_ids=[f2.id, f5.id, f1.id],
        legal_basis_ids=[b1.id, b2.id, b3.id],
        status=ArgumentStatus.ADVANCED,
    )
    arg2 = Argument(
        issue_id=issue2.id,
        claim=(
            "Odpowiedź Prezesa z 23.07.2026 r. ogranicza się do kompetencji organu "
            "i autentyczności korespondencji, pomijając standard wykonania "
            "obowiązku informacyjnego."
        ),
        support_fact_ids=[f3.id, f4.id, f2.id, f5.id],
        legal_basis_ids=[b1.id, b2.id, b3.id],
        status=ArgumentStatus.ADVANCED,
    )

    for arg in (arg1, arg2):
        case.add_argument(arg)

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
            fact_ids=[f1.id, f2.id, f3.id, f4.id, f5.id],
            legal_basis_ids=[b1.id, b2.id, b3.id],
            issue_ids=[issue1.id, issue2.id],
            argument_ids=[arg1.id, arg2.id],
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
    return case


def main() -> None:
    case = build_case()
    ctx = LetterContext(
        sender_name="Arkadiusz Mielewczyk",
        place="Wejherowo",
        letter_date=date(2026, 7, 28),
        subject="odpowiedzi z dnia 23 lipca 2026 r. na skargę z dnia 22 czerwca 2026 r.",
        prosecutor_ref="4057-0.Ds.2517.2025",
        recipient_lines=[
            "Prezes Sądu Rejonowego w Wejherowie",
            "SSR Beata Czabotar-Magulska",
            "Sąd Rejonowy w Wejherowie",
            "ul. Wniebowstąpienia 4",
            "84-200 Wejherowo",
        ],
    )

    out_dir = Path("output/cases/II_Kp_459_26")
    out_dir.mkdir(parents=True, exist_ok=True)

    text = CaseLetterRenderer().render(case, context=ctx)
    txt_path = out_dir / "pismo.txt"
    txt_path.write_text(text, encoding="utf-8")
    print("TXT:", txt_path.resolve())

    docx_path = CaseDocxExporter().export(
        case,
        out_dir / "pismo.docx",
        context=ctx,
    )
    print("DOCX:", docx_path.resolve())
    print("Case summary:", case.summary())


if __name__ == "__main__":
    main()