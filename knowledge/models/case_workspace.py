"""
CaseWorkspace – single session object for a legal case.

Wires Case + KnowledgeGraph + LegalQuery + authorities + dossier + snapshot.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from knowledge.graph import KnowledgeGraph
from knowledge.legal_query import LegalQuery
from knowledge.models.authority_section import AuthoritySection, build_authority_section
from knowledge.models.case import Case
from knowledge.models.dossier_render import DossierContext, DossierRenderer


ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class CaseWorkspace:
    key: str
    graph_case_id: str
    case: Case
    graph: KnowledgeGraph
    root: Path = field(default_factory=lambda: ROOT)

    authorities: AuthoritySection | None = None
    dossier_text: str | None = None
    last_snapshot_path: Path | None = None

    fact_ok: bool | None = None
    law_ok: bool | None = None
    review_ok: bool | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def case_dir(self) -> Path:
        return self.root / "cases" / self.key

    @property
    def output_dir(self) -> Path:
        return self.root / "output" / "cases" / self.key

    @property
    def outbound_dir(self) -> Path:
        return self.case_dir / "outbound"

    @property
    def legal(self) -> LegalQuery:
        return LegalQuery(self.graph)

    def build_authorities(
        self,
        *,
        focus_statute_id: str | None = "statute:kk:284:2",
    ) -> AuthoritySection:
        section = build_authority_section(
            self.legal,
            self.graph_case_id,
            focus_statute_id=focus_statute_id,
        )
        self.authorities = section
        return section

    def render_dossier(
        self,
        *,
        author_name: str = "",
        place: str = "",
        dossier_date: date | None = None,
        subject: str = "",
        recipient_lines: list[str] | None = None,
        include_authorities: bool = True,
    ) -> str:
        if include_authorities and self.authorities is None:
            self.build_authorities()

        authorities_text = (
            self.authorities.to_plain_text()
            if include_authorities and self.authorities is not None
            else None
        )

        ctx = DossierContext(
            author_name=author_name,
            place=place,
            dossier_date=dossier_date or date.today(),
            subject=subject or self.case.display_title(),
            recipient_lines=recipient_lines,
            authorities_text=authorities_text,
        )
        text = DossierRenderer().render(self.case, context=ctx)
        self.dossier_text = text
        return text

    def export_dossier_txt(
        self, filename: str = "stanowisko_dossier_with_authorities.txt"
    ) -> Path:
        if self.dossier_text is None:
            self.render_dossier()
        assert self.dossier_text is not None
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / filename
        path.write_text(self.dossier_text, encoding="utf-8")
        return path.resolve()

    def export_dossier_docx(
        self, filename: str = "stanowisko_dossier_with_authorities.docx"
    ) -> Path:
        if self.dossier_text is None:
            self.render_dossier()
        assert self.dossier_text is not None
        try:
            from docx import Document
            from docx.enum.text import WD_LINE_SPACING
            from docx.shared import Pt
        except ImportError as exc:
            raise ImportError(
                "python-docx is required: pip install python-docx"
            ) from exc

        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / filename

        doc = Document()
        style = doc.styles["Normal"]
        style.font.name = "Times New Roman"
        style.font.size = Pt(12)

        for block in self.dossier_text.split("\n"):
            para = doc.add_paragraph(block)
            pf = para.paragraph_format
            pf.space_after = Pt(0)
            pf.space_before = Pt(0)
            pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
            for run in para.runs:
                run.font.name = "Times New Roman"
                run.font.size = Pt(12)

        doc.save(str(path))
        return path.resolve()

    def sync_outbound(
        self,
        *,
        filenames: list[str] | None = None,
    ) -> list[Path]:
        """
        Copy generated artifacts from output/cases/<key>/ into cases/<key>/outbound/.
        """
        names = filenames or [
            "stanowisko_dossier_with_authorities.txt",
            "stanowisko_dossier_with_authorities.docx",
            "authorities_from_graph.txt",
            "authorities_from_graph.docx",
        ]
        self.outbound_dir.mkdir(parents=True, exist_ok=True)
        copied: list[Path] = []
        for name in names:
            src = self.output_dir / name
            if not src.is_file():
                continue
            dest = self.outbound_dir / name
            shutil.copy2(src, dest)
            copied.append(dest.resolve())
        return copied

    def run_fact_agent(self) -> int:
        from scripts.fact_agent import format_report, review_case_facts

        findings = review_case_facts(self.case)
        print(format_report(self.case, findings))
        self.fact_ok = not any(f.severity == "ERROR" for f in findings)
        return 0 if self.fact_ok else 1

    def run_law_agent(self) -> int:
        from scripts.law_agent import format_report, review_case_law_links

        findings, _lq, cid = review_case_law_links(self.graph_case_id)
        print(format_report(findings, cid))
        self.law_ok = not any(f.severity == "ERROR" for f in findings)
        return 0 if self.law_ok else 1

    def run_review_agent(self, path: Path | None = None) -> int:
        from scripts.review_dossier import format_report, review_text

        if path is None:
            if self.dossier_text is None:
                self.render_dossier()
            text = self.dossier_text or ""
        else:
            text = path.read_text(encoding="utf-8")

        findings = review_text(text, signature_hint=self.key.replace("_", "."))
        print(format_report(findings))
        self.review_ok = not any(f.severity == "ERROR" for f in findings)
        return 0 if self.review_ok else 1

    def save_snapshot(self) -> Path:
        from knowledge.models.case_snapshot import save_workspace_snapshot

        path = save_workspace_snapshot(self, repo_root=self.root)
        self.last_snapshot_path = path
        return path

    def run(
        self,
        *,
        author_name: str = "",
        place: str = "",
        subject: str = "",
        recipient_lines: list[str] | None = None,
        save_snapshot: bool = True,
        export_docx: bool = True,
        sync_outbound: bool = True,
    ) -> int:
        """
        Fact → Law → authorities → dossier (txt/docx) → review → outbound → snapshot
        """
        if self.run_fact_agent() != 0:
            print("WORKSPACE FAIL: FactAgent")
            if save_snapshot:
                try:
                    p = self.save_snapshot()
                    print("Snapshot (failed run):", p)
                except Exception as exc:  # noqa: BLE001
                    print("Snapshot save error:", exc)
            return 1

        if self.run_law_agent() != 0:
            print("WORKSPACE FAIL: LawAgent")
            if save_snapshot:
                try:
                    p = self.save_snapshot()
                    print("Snapshot (failed run):", p)
                except Exception as exc:  # noqa: BLE001
                    print("Snapshot save error:", exc)
            return 1

        self.build_authorities()
        self.render_dossier(
            author_name=author_name,
            place=place,
            subject=subject,
            recipient_lines=recipient_lines,
            include_authorities=True,
        )
        out = self.export_dossier_txt()
        print("Saved:", out)

        if export_docx:
            try:
                docx_path = self.export_dossier_docx()
                print("Saved DOCX:", docx_path)
            except ImportError as exc:
                print("DOCX skipped:", exc)

        if self.run_review_agent() != 0:
            print("WORKSPACE FAIL: ReviewAgent")
            if save_snapshot:
                try:
                    p = self.save_snapshot()
                    print("Snapshot (failed run):", p)
                except Exception as exc:  # noqa: BLE001
                    print("Snapshot save error:", exc)
            return 1

        if sync_outbound:
            copied = self.sync_outbound()
            if copied:
                print("Outbound:")
                for path in copied:
                    print(" ", path)
            else:
                print("Outbound: (nothing copied)")

        if save_snapshot:
            snap_path = self.save_snapshot()
            print("Snapshot:", snap_path)
            from knowledge.models.case_snapshot import CaseSnapshot

            print("Status:", CaseSnapshot.load(snap_path).status)

        print("WORKSPACE PASS")
        return 0


def open_ds_3960() -> CaseWorkspace:
    from scripts.build_case_ds_3960_2025 import build_case
    from scripts.link_case_to_law import link_ds_3960

    case = build_case()
    graph, graph_case_id = link_ds_3960()
    return CaseWorkspace(
        key="DS_3960_2025",
        graph_case_id=graph_case_id,
        case=case,
        graph=graph,
        meta={"signature": "DS.3960.2025"},
    )


def main() -> int:
    ws = open_ds_3960()
    return ws.run(
        author_name="Mariusz Brodziszewski",
        place="Poznań",
        subject=(
            "Stanowisko procesowe wraz z analizą materiału dowodowego "
            "— pojazd Volkswagen Transporter"
        ),
        recipient_lines=["Prokuratura Rejonowa Poznań-Wilda"],
    )


if __name__ == "__main__":
    raise SystemExit(main())