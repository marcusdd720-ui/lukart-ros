"""
Knowledge Operating System (KOS)

File: knowledge/models/docx_export.py
Version: 1.0
Sprint: CASE-003

Export rendered case letter to Word (.docx).
Requires: pip install python-docx
"""

from __future__ import annotations

from pathlib import Path

from knowledge.models.case import Case, Decision
from knowledge.models.render import CaseLetterRenderer, LetterContext


class CaseDocxExporter:
    """Write a formal letter DOCX from Case + Decision."""

    def __init__(self, renderer: CaseLetterRenderer | None = None) -> None:
        self.renderer = renderer or CaseLetterRenderer()

    def export(
        self,
        case: Case,
        path: str | Path,
        *,
        decision: Decision | None = None,
        context: LetterContext | None = None,
    ) -> Path:
        try:
            from docx import Document
            from docx.enum.text import WD_LINE_SPACING
            from docx.shared import Pt
        except ImportError as exc:
            raise ImportError(
                "python-docx is required: pip install python-docx"
            ) from exc

        text = self.renderer.render(case, decision=decision, context=context)
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)

        doc = Document()
        style = doc.styles["Normal"]
        font = style.font
        font.name = "Times New Roman"
        font.size = Pt(12)

        for block in text.split("\n"):
            para = doc.add_paragraph(block)
            pf = para.paragraph_format
            pf.space_after = Pt(0)
            pf.space_before = Pt(0)
            pf.line_spacing_rule = WD_LINE_SPACING.SINGLE

        doc.save(str(output))
        return output
