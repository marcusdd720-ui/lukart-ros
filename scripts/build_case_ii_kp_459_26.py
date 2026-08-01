"""Build case II Kp 459/26 and export letter (txt + docx)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from knowledge.models.case import (
    Case,
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
        title="Skarga na sposób wykonania obowiązku informacyjnego",
        signature="II Kp 459/26",
        metadata={
            "prosecutor_ref": "4057-0.Ds.2517.2025",
            "court": "Sąd Rejonowy w Wejherowie",
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
            "wysłła wiadomość e-mail ze służbowego adresu."
        ),
        status=FactStatus.SUPPORTED,
        source_refs=["email-2026-06-10"],
    )
    f3 = Fact(
        statement=(
            "W dniu 22.06.2026 r. wnoszący złożył skargę dotyczącą sposobu "
            "wykonania obowiązku informacyjnego, a nie autentyczności wiadomości "
            "ani prawa Sądu do udzielania pouczeń."
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
            "trudności komunikacyjne istotne dla standardu pouczeń."
        ),
        status=FactStatus.SUPPORTED,
        source_refs=["material-trudnosci-komunikacyjne"],
        confidence=0.9,
    )
    for fact in (f1, f2, f3, f4, f5):
        case.add_fact(fact)

    b1 = LegalBasis(
        reference="art. 16 § 1 k.p.k.",
        note="obowiązek informowania uczestników o uprawnieniach i obowiązkach",
    )
    b2 = LegalBasis(
        reference="art. 16 § 2–3 k.p.k.",
        note="sposób i zakres pouczeń; ochrona uczestnika nieprofesjonalnego",
    )
    b3 = LegalBasis(
        reference="uchwała SN I KZP 6/13",
        note="gwarancyjny charakter pouczeń",
    )
    for basis in (b1, b2, b3):
        case.add_legal_basis(basis)

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
            outcomes=[
                "ponowne rozpoznanie skargi w zakresie sposobu komunikacji",
                "wskazanie charakteru wiadomości e-mail z 10.06.2026 r.",
                "wskazanie skutków procesowych tej wiadomości",
                "odniesienie się do zgłoszonych trudności komunikacyjnych",
                "zapewnienie jednoznacznej komunikacji w dalszym toku sprawy",
                "przyjęcie niniejszego pisma do akt",
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
        subject=(
            "Wniosek o ponowne rozpoznanie skargi z 22.06.2026 r. "
            "— odpowiedź na pismo Prezesa z 23.07.2026 r."
        ),
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