"""
Export full DS.3960 dossier (with graph authorities VI.A) to Word DOCX.
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
    try:
        from docx import Document
        from docx.enum.text import WD_LINE_SPACING
        from docx.shared import Pt
    except ImportError as exc:
        raise ImportError("python-docx is required: pip install python-docx") from exc

    case = build_case()
    graph, case_node_id = link_ds_3960()
    section = build_authority_section(LegalQuery(graph), case_node_id)

    ctx = DossierContext(
        author_name="Mariusz Brodziszewski",
        place="Poznań",
        dossier_date=date.today(),
        subject=(
            "Stanowisko procesowe wraz z analizą materiału dowodowego "
            "— pojazd Volkswagen Transporter"
        ),
        recipient_lines=["Prokuratura Rejonowa Poznań-Wilda"],
        authorities_text=section.to_plain_text(),
    )
    text = DossierRenderer().render(case, context=ctx)

    out_dir = Path("output") / "cases" / "DS_3960_2025"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "stanowisko_dossier_with_authorities.docx"

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    for block in text.split("\n"):
        para = doc.add_paragraph(block)
        pf = para.paragraph_format
        pf.space_after = Pt(0)
        pf.space_before = Pt(0)
        pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
        for run in para.runs:
            run.font.name = "Times New Roman"
            run.font.size = Pt(12)

    doc.save(str(path))
    print("Saved:", path.resolve())
    print("VI.A:", "OK" if "VI.A. ORZECZNICTWO" in text else "MISSING")


if __name__ == "__main__":
    main()