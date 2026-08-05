"""
CaseWorkspace – single session object for a legal case.

Wires Case + KnowledgeGraph + LegalQuery + authorities + dossier text.
Does not replace agents; orchestrates them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

from knowledge.graph import KnowledgeGraph
from knowledge.legal_query import LegalQuery
from knowledge.models.authority_section import AuthoritySection, build_authority_section
from knowledge.models.case import Case
from knowledge.models.dossier_render import DossierContext, DossierRenderer


ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class CaseWorkspace:
    """
    In-memory workspace for one case run.

    Paths point at lukart-ros layout:
      cases/<key>/...
      output/cases/<key>/...
    """

    key: str
    graph_case_id: str
    case: Case
    graph: KnowledgeGraph
    root: Path = field(default_factory=lambda: ROOT)

    authorities: AuthoritySection | None = None
    dossier_text: str | None = None

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

    def export_dossier_txt(self, filename: str = "stanowisko_dossier_with_authorities.txt") -> Path:
        if self.dossier_text is None:
            self.render_dossier()
        assert self.dossier_text is not None
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / filename
        path.write_text(self.dossier_text, encoding="utf-8")
        return path.resolve()

    def run_fact_agent(self) -> int:
        from scripts.fact_agent import review_case_facts, format_report

        findings = review_case_facts(self.case)
        print(format_report(self.case, findings))
        self.fact_ok = not any(f.severity == "ERROR" for f in findings)
        return 0 if self.fact_ok else 1

    def run_law_agent(self) -> int:
        from scripts.law_agent import review_case_law_links, format_report

        # Ensure current workspace graph is used: law_agent rebuilds its own graph.
        # For v0 we still call the script logic; FAIL if no links on *this* graph.
        findings, _lq, cid = review_case_law_links(self.graph_case_id)
        print(format_report(findings, cid))
        self.law_ok = not any(f.severity == "ERROR" for f in findings)
        return 0 if self.law_ok else 1

    def run_review_agent(self, path: Path | None = None) -> int:
        from scripts.review_dossier import review_text, format_report

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

    def run(
        self,
        *,
        author_name: str = "",
        place: str = "",
        subject: str = "",
        recipient_lines: list[str] | None = None,
    ) -> int:
        """
        Full pipeline on this workspace:
          Fact → Law → authorities → dossier → review
        """
        if self.run_fact_agent() != 0:
            print("WORKSPACE FAIL: FactAgent")
            return 1
        if self.run_law_agent() != 0:
            print("WORKSPACE FAIL: LawAgent")
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

        if self.run_review_agent() != 0:
            print("WORKSPACE FAIL: ReviewAgent")
            return 1

        print("WORKSPACE PASS")
        return 0


def open_ds_3960() -> CaseWorkspace:
    """Adapter for the existing DS.3960 builder + legal graph link."""
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