"""Export an AuthoritySection to a Word document.

The exporter accepts an already-built graph and case identifier. It never
loads a real case, personal data, or case-specific builder from source code.
"""

from __future__ import annotations

from pathlib import Path

from knowledge.legal_query import LegalQuery
from knowledge.models.authority_section import build_authority_section


def export_authorities_docx(
    path: Path,
    *,
    graph,
    case_id: str,
) -> Path:
    try:
        from docx import Document
        from docx.enum.text import WD_LINE_SPACING
        from docx.shared import Pt
    except ImportError as exc:
        raise ImportError("python-docx is required: pip install python-docx") from exc

    section = build_authority_section(LegalQuery(graph), case_id)

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    def add_line(text: str = "", *, bold: bool = False) -> None:
        para = doc.add_paragraph()
        run = para.add_run(text)
        run.bold = bold
        run.font.name = "Times New Roman"
        run.font.size = Pt(12)
        pf = para.paragraph_format
        pf.space_after = Pt(0)
        pf.space_before = Pt(0)
        pf.line_spacing_rule = WD_LINE_SPACING.SINGLE

    add_line("PODSTAWA PRAWNA I ORZECZNICTWO", bold=True)
    add_line()
    add_line("Przepisy, na których oparto stanowisko:", bold=True)
    if not section.statutes:
        add_line("1. (brak)")
    else:
        for i, item in enumerate(section.statutes, 1):
            add_line(f"{i}. {item.title}")
            if item.summary:
                add_line(f"   {item.summary}")

    add_line()
    add_line("Orzecznictwo wspierające ocenę prawną:", bold=True)
    if not section.case_law:
        add_line("1. (brak)")
    else:
        for i, item in enumerate(section.case_law, 1):
            add_line(f"{i}. {item.citation or item.title}")
            if item.summary:
                add_line(f"   Teza: {item.summary}")

    add_line()
    add_line("Wybrane interpretacje (przepis wiodący):", bold=True)
    if not section.interpretations:
        add_line("— (brak)")
    else:
        for item in section.interpretations:
            if item.summary:
                add_line(f"— {item.title}: {item.summary}")
            else:
                add_line(f"— {item.title}")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path.resolve()
