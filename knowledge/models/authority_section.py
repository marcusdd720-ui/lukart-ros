"""
AuthoritySection – intermediate model between LegalQuery and text/DOCX renderers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from knowledge.legal_query import LegalQuery
from knowledge.node import KnowledgeNode


@dataclass(slots=True, frozen=True)
class AuthorityItem:
    """Single statute or case-law reference for pleadings."""

    id: str
    title: str
    citation: str = ""
    summary: str = ""
    kind: str = ""  # "statute" | "case_law"


@dataclass(slots=True, frozen=True)
class AuthoritySection:
    """
    Structured legal authorities for a case.

    Renderers (plain text / DOCX) consume this object – not the graph.
    """

    case_id: str
    statutes: tuple[AuthorityItem, ...] = field(default_factory=tuple)
    case_law: tuple[AuthorityItem, ...] = field(default_factory=tuple)
    interpretations: tuple[AuthorityItem, ...] = field(default_factory=tuple)
    focus_statute_id: str | None = None

    def to_plain_text(self) -> str:
        lines: list[str] = []
        lines.append("PODSTAWA PRAWNA I ORZECZNICTWO")
        lines.append("")

        lines.append("Przepisy, na których oparto stanowisko:")
        if not self.statutes:
            lines.append("1. (brak powiązań RELIES_ON w grafie)")
        else:
            for i, item in enumerate(self.statutes, 1):
                lines.append(f"{i}. {item.title}")
                if item.summary:
                    lines.append(f"   {item.summary}")
        lines.append("")

        lines.append("Orzecznictwo wspierające ocenę prawną:")
        if not self.case_law:
            lines.append("1. (brak powiązań SUPPORTED_BY w grafie)")
        else:
            for i, item in enumerate(self.case_law, 1):
                label = item.citation or item.title
                lines.append(f"{i}. {label}")
                if item.summary:
                    lines.append(f"   Teza: {item.summary}")
        lines.append("")

        if self.focus_statute_id is not None:
            lines.append("Wybrane interpretacje (przepis wiodący):")
            if not self.interpretations:
                lines.append("— (brak krawędzi INTERPRETS)")
            else:
                for item in self.interpretations:
                    if item.summary:
                        lines.append(f"— {item.title}: {item.summary}")
                    else:
                        lines.append(f"— {item.title}")

        return "\n".join(lines).rstrip() + "\n"


def _item_from_node(node: KnowledgeNode, *, kind: str) -> AuthorityItem:
    citation = str(node.metadata.get("signature") or node.metadata.get("article") or "")
    return AuthorityItem(
        id=node.id,
        title=node.name,
        citation=citation,
        summary=(node.description or "").strip(),
        kind=kind,
    )


def build_authority_section(
    legal_query: LegalQuery,
    case_id: str,
    *,
    focus_statute_id: str | None = "statute:kk:284:2",
) -> AuthoritySection:
    """Build AuthoritySection from graph relations for a case node."""
    statutes = tuple(
        _item_from_node(n, kind="statute") for n in legal_query.relies_on(case_id)
    )
    case_law = tuple(
        _item_from_node(n, kind="case_law") for n in legal_query.supported_by(case_id)
    )
    interpretations: tuple[AuthorityItem, ...] = ()
    if focus_statute_id:
        interpretations = tuple(
            _item_from_node(n, kind="case_law")
            for n in legal_query.interpretations_of(focus_statute_id)
        )

    return AuthoritySection(
        case_id=case_id,
        statutes=statutes,
        case_law=case_law,
        interpretations=interpretations,
        focus_statute_id=focus_statute_id,
    )