"""
Export DS.3960 dossier with AuthoritySection (graph) injected into section VI.A.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from knowledge.legal_query import LegalQuery
from knowledge.models.authority_section import build_authority_section
from knowledge.models.dossier_render import DossierContext, DossierRenderer
from scripts.build_case_ds_3960_2025 import build_case
from scripts.link_case_to_law import link_ds_3960


def main() -> None:
    case = build_case()
    graph, case_node_id = link_ds_3960()
    section = build_authority_section(LegalQuery(graph), case_node_id)
    authorities_text = section.to_plain_text()

    out_dir = Path("output") / "cases" / "DS_3960_2025"
    out_dir.mkdir(parents=True, exist_ok=True)

    ctx = DossierContext(
        author_name="Mariusz Brodziszewski",
        place="Poznań",
        dossier_date=date.today(),
        subject=(
            "Stanowisko procesowe wraz z analizą materiału dowodowego "
            "— pojazd Volkswagen Transporter"
        ),
        recipient_lines=["Prokuratura Rejonowa Poznań-Wilda"],
        authorities_text=authorities_text,
    )

    text = DossierRenderer().render(case, context=ctx)
    path = out_dir / "stanowisko_dossier_with_authorities.txt"
    path.write_text(text, encoding="utf-8")

    print("Saved:", path.resolve())
    if "VI.A. ORZECZNICTWO" in text:
        print("Section VI.A: OK")
    else:
        print("Section VI.A: MISSING")
    if "V KK 391/14" in text or "IV KK 283/16" in text:
        print("SN theses: OK")
    else:
        print("SN theses: check graph link")


if __name__ == "__main__":
    main()