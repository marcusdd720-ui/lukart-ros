"""
CaseWorkspace – single session object for a legal case.

Supports full run() or run(stage=...).
Snapshots: OPEN (start) → FREEZE (success end) → RELEASE (explicit).
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

STAGES = (
    "FACT",
    "LAW",
    "DOSSIER",
    "REVIEW",
    "OUTBOUND",
    "OPEN",
    "FREEZE",
    "RELEASE",
    "NOTE",
)


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
    focus_statute_id: str | None = None

    fact_ok: bool | None = None
    law_ok: bool | None = None
    review_ok: bool | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    _author_name: str = ""
    _place: str = ""
    _subject: str = ""
    _recipient_lines: list[str] | None = None

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
    def notes_dir(self) -> Path:
        return self.case_dir / "notes"

    @property
    def legal(self) -> LegalQuery:
        return LegalQuery(self.graph)

    def set_letter_context(
        self,
        *,
        author_name: str = "",
        place: str = "",
        subject: str = "",
        recipient_lines: list[str] | None = None,
    ) -> None:
        self._author_name = author_name
        self._place = place
        self._subject = subject
        self._recipient_lines = recipient_lines

    def build_authorities(
        self,
        *,
        focus_statute_id: str | None = None,
    ) -> AuthoritySection:
        focus = focus_statute_id or self.focus_statute_id
        section = build_authority_section(
            self.legal,
            self.graph_case_id,
            focus_statute_id=focus,
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
            author_name=author_name or self._author_name,
            place=place or self._place,
            dossier_date=dossier_date or date.today(),
            subject=subject or self._subject or self.case.display_title(),
            recipient_lines=(
                recipient_lines
                if recipient_lines is not None
                else self._recipient_lines
            ),
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

    def write_run_note(
        self,
        *,
        snapshot_status: str | None = None,
        outbound_files: list[Path] | None = None,
        dossier_txt: Path | None = None,
        dossier_docx: Path | None = None,
    ) -> Path:
        from knowledge.models.run_note import write_run_note

        return write_run_note(
            notes_dir=self.notes_dir,
            case_key=self.key,
            graph_case_id=self.graph_case_id,
            fact_ok=self.fact_ok,
            law_ok=self.law_ok,
            review_ok=self.review_ok,
            snapshot_path=self.last_snapshot_path,
            snapshot_status=snapshot_status,
            outbound_files=outbound_files,
            dossier_txt=dossier_txt,
            dossier_docx=dossier_docx,
        )

    def run_fact_agent(self) -> int:
        from scripts.fact_agent import format_report, review_case_facts

        findings = review_case_facts(self.case)
        print(format_report(self.case, findings))
        self.fact_ok = not any(f.severity == "ERROR" for f in findings)
        return 0 if self.fact_ok else 1

    def run_law_agent(self) -> int:
        from scripts.law_agent import format_report, review_case_law_links

        findings = review_case_law_links(
            self.graph,
            self.graph_case_id,
            focus_statute_id=self.focus_statute_id,
        )
        print(format_report(findings, self.graph_case_id))
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

        hint = (
            (self.case.signature or "").strip()
            or str(self.meta.get("signature", "")).strip()
            or self.key.replace("_", ".")
        )
        findings = review_text(text, signature_hint=hint)
        print(format_report(findings))
        self.review_ok = not any(f.severity == "ERROR" for f in findings)
        return 0 if self.review_ok else 1

    def save_snapshot(self, *, phase: str = "FREEZE") -> Path:
        from knowledge.models.case_snapshot import save_workspace_snapshot

        path = save_workspace_snapshot(self, repo_root=self.root, phase=phase)
        self.last_snapshot_path = path
        return path

    def run_stage(self, stage: str, *, export_docx: bool = True) -> int:
        name = stage.strip().upper()
        if name not in STAGES:
            print(f"Unknown stage: {stage!r}. Known: {', '.join(STAGES)}")
            return 2

        if name == "FACT":
            return self.run_fact_agent()
        if name == "LAW":
            return self.run_law_agent()

        if name == "DOSSIER":
            self.build_authorities()
            self.render_dossier(
                author_name=self._author_name,
                place=self._place,
                subject=self._subject,
                recipient_lines=self._recipient_lines,
                include_authorities=True,
            )
            path = self.export_dossier_txt()
            print("Saved:", path)
            if export_docx:
                try:
                    docx_path = self.export_dossier_docx()
                    print("Saved DOCX:", docx_path)
                except ImportError as exc:
                    print("DOCX skipped:", exc)
            return 0

        if name == "REVIEW":
            return self.run_review_agent()

        if name == "OUTBOUND":
            copied = self.sync_outbound()
            if copied:
                print("Outbound:")
                for path in copied:
                    print(" ", path)
            else:
                print("Outbound: (nothing copied)")
            return 0

        if name == "OPEN":
            path = self.save_snapshot(phase="OPEN")
            print("Snapshot OPEN:", path)
            return 0

        if name == "FREEZE":
            path = self.save_snapshot(phase="FREEZE")
            print("Snapshot FREEZE:", path)
            from knowledge.models.case_snapshot import CaseSnapshot

            print("Status:", CaseSnapshot.load(path).status)
            return 0

        if name == "RELEASE":
            from knowledge.models.case_snapshot import CaseSnapshot
            from knowledge.models.snapshot_validator import validate_snapshot

            # Prefer last freeze pointer if present
            freeze_ptr = self.output_dir / "snapshots" / "latest_freeze.json"
            if freeze_ptr.is_file():
                data = __import__("json").loads(
                    freeze_ptr.read_text(encoding="utf-8")
                )
                result = validate_snapshot(data)
                if not result.ready_to_publish:
                    print(result.report())
                    print("RELEASE blocked: freeze snapshot not READY_TO_PUBLISH")
                    return 1
            path = self.save_snapshot(phase="RELEASE")
            print("Snapshot RELEASE:", path)
            print("Status:", CaseSnapshot.load(path).status)
            return 0

        if name == "NOTE":
            status = None
            if self.last_snapshot_path and self.last_snapshot_path.is_file():
                from knowledge.models.case_snapshot import CaseSnapshot

                status = CaseSnapshot.load(self.last_snapshot_path).status
            note_path = self.write_run_note(
                snapshot_status=status,
                outbound_files=None,
                dossier_txt=self.output_dir
                / "stanowisko_dossier_with_authorities.txt",
                dossier_docx=self.output_dir
                / "stanowisko_dossier_with_authorities.docx",
            )
            print("Note:", note_path)
            return 0

        return 2

    def run(
        self,
        *,
        author_name: str = "",
        place: str = "",
        subject: str = "",
        recipient_lines: list[str] | None = None,
        stage: str | None = None,
        save_snapshot: bool = True,
        export_docx: bool = True,
        sync_outbound: bool = True,
        write_note: bool = True,
    ) -> int:
        self.set_letter_context(
            author_name=author_name,
            place=place,
            subject=subject,
            recipient_lines=recipient_lines,
        )

        if stage is not None:
            code = self.run_stage(stage, export_docx=export_docx)
            if code == 0:
                print(f"STAGE PASS: {stage.strip().upper()}")
            else:
                print(f"STAGE FAIL: {stage.strip().upper()}")
            return code

        dossier_txt: Path | None = None
        dossier_docx: Path | None = None
        outbound_files: list[Path] = []
        snapshot_status: str | None = None

        if save_snapshot:
            try:
                open_path = self.save_snapshot(phase="OPEN")
                print("Snapshot OPEN:", open_path)
            except Exception as exc:  # noqa: BLE001
                print("Snapshot OPEN error:", exc)

        if self.run_fact_agent() != 0:
            print("WORKSPACE FAIL: FactAgent")
            if save_snapshot:
                try:
                    p = self.save_snapshot(phase="FREEZE")
                    print("Snapshot FREEZE (failed run):", p)
                except Exception as exc:  # noqa: BLE001
                    print("Snapshot save error:", exc)
            return 1

        if self.run_law_agent() != 0:
            print("WORKSPACE FAIL: LawAgent")
            if save_snapshot:
                try:
                    p = self.save_snapshot(phase="FREEZE")
                    print("Snapshot FREEZE (failed run):", p)
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
        dossier_txt = self.export_dossier_txt()
        print("Saved:", dossier_txt)

        if export_docx:
            try:
                dossier_docx = self.export_dossier_docx()
                print("Saved DOCX:", dossier_docx)
            except ImportError as exc:
                print("DOCX skipped:", exc)

        if self.run_review_agent() != 0:
            print("WORKSPACE FAIL: ReviewAgent")
            if save_snapshot:
                try:
                    p = self.save_snapshot(phase="FREEZE")
                    print("Snapshot FREEZE (failed run):", p)
                except Exception as exc:  # noqa: BLE001
                    print("Snapshot save error:", exc)
            return 1

        if sync_outbound:
            outbound_files = self.sync_outbound()
            if outbound_files:
                print("Outbound:")
                for path in outbound_files:
                    print(" ", path)
            else:
                print("Outbound: (nothing copied)")

        if save_snapshot:
            snap_path = self.save_snapshot(phase="FREEZE")
            print("Snapshot FREEZE:", snap_path)
            from knowledge.models.case_snapshot import CaseSnapshot

            snapshot_status = CaseSnapshot.load(snap_path).status
            print("Status:", snapshot_status)

        if write_note:
            note_path = self.write_run_note(
                snapshot_status=snapshot_status,
                outbound_files=outbound_files,
                dossier_txt=dossier_txt,
                dossier_docx=dossier_docx,
            )
            print("Note:", note_path)

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
        focus_statute_id="statute:kk:284:2",
        meta={"signature": "DS.3960.2025"},
    )


def open_ii_kp_459_26() -> CaseWorkspace:
    from scripts.build_case_ii_kp_459_26 import build_case
    from scripts.link_case_ii_kp_459_26 import link_ii_kp_459_26

    case = build_case()
    graph, graph_case_id = link_ii_kp_459_26()
    return CaseWorkspace(
        key="II_Kp_459_26",
        graph_case_id=graph_case_id,
        case=case,
        graph=graph,
        focus_statute_id="statute:kpk:16",
        meta={
            "signature": "II Kp 459/26",
            "prosecutor_ref": "4057-0.Ds.2517.2025",
        },
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