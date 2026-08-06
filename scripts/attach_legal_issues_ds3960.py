"""
Attach LegalIssue objects to DS.3960.2025 case after build_case().
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from knowledge.models.case import Case, IssueStatus, LegalIssue


def attach_ds3960_issues(case: Case) -> Case:
    """Idempotent: skip if legal_issues already present."""
    if case.legal_issues:
        return case

    fact_ids = [f.id for f in case.facts]

    case.add_issue(
        LegalIssue(
            question=(
                "Czy czynności Mariusza Brodziszewskiego dotyczące pojazdu "
                "(rejestracja, OC, posiadanie) były podejmowane w oparciu o "
                "dokumenty i w przekonaniu o prawie do dysponowania pojazdem?"
            ),
            status=IssueStatus.OPEN,
            fact_ids=list(fact_ids),
            hypothesis=(
                "Przy umowie darowizny, rejestracji i polisie OC materiał "
                "wymaga oceny zamiaru i przekonania o prawie, a nie samego "
                "późniejszego sporu cywilnego."
            ),
            statute_refs=["art. 284 § 2 k.k.", "art. 7 k.p.k.", "art. 410 k.p.k."],
            case_law_refs=[],
            metadata={"case_key": "DS_3960_2025", "cluster": "intent_and_documents"},
        )
    )

    case.add_issue(
        LegalIssue(
            question=(
                "Czy sam późniejszy spór cywilny/rodzinny (wezwanie do wydania, "
                "rozwód) wystarcza do przyjęcia znamion czynu zabronionego bez "
                "wszechstronnej oceny całokształtu materiału?"
            ),
            status=IssueStatus.OPEN,
            fact_ids=list(fact_ids),
            hypothesis=(
                "Skutki cywilnoprawne darowizny należy oddzielić od oceny karnej "
                "zamiaru; spór o wydanie pojazdu nie przesądza automatycznie "
                "odpowiedzialności karnej."
            ),
            statute_refs=["art. 284 § 2 k.k.", "art. 7 k.p.k.", "art. 410 k.p.k."],
            case_law_refs=[],
            metadata={"case_key": "DS_3960_2025", "cluster": "civil_vs_criminal"},
        )
    )

    return case


def main() -> None:
    from scripts.build_case_ds_3960_2025 import build_case

    case = attach_ds3960_issues(build_case())
    print(case.summary())


if __name__ == "__main__":
    main()