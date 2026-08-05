"""
Render legal authorities block from Knowledge Graph (LegalQuery).

Used by dossier / letter pipelines. No I/O – pure text.
"""

from __future__ import annotations

from knowledge.legal_query import LegalQuery


def render_authorities_block(
    legal_query: LegalQuery,
    case_id: str,
    *,
    statute_focus_id: str | None = "statute:kk:284:2",
) -> str:
    """
    Build markdown-ish plain text section:
      - RELIES_ON statutes
      - SUPPORTED_BY case law + theses
      - optional interpretations of a focus statute
    """
    lines: list[str] = []

    lines.append("PODSTAWA PRAWNA I ORZECZNICTWO")
    lines.append("")

    lines.append("Przepisy, na których oparto stanowisko:")
    statutes = legal_query.relies_on(case_id)
    if not statutes:
        lines.append("1. (brak powiązań RELIES_ON w grafie)")
    else:
        for i, node in enumerate(statutes, 1):
            lines.append(f"{i}. {node.name}")
            if node.description:
                lines.append(f"   {node.description}")
    lines.append("")

    lines.append("Orzecznictwo wspierające ocenę prawną:")
    authorities = legal_query.supported_by(case_id)
    if not authorities:
        lines.append("1. (brak powiązań SUPPORTED_BY w grafie)")
    else:
        for i, node in enumerate(authorities, 1):
            sig = node.metadata.get("signature") or node.name
            lines.append(f"{i}. {sig}")
            thesis = (node.description or "").strip()
            if thesis:
                lines.append(f"   Teza: {thesis}")
    lines.append("")

    if statute_focus_id:
        focus = legal_query.q.get(statute_focus_id)
        label = focus.name if focus is not None else statute_focus_id
        lines.append(f"Wybrane interpretacje ({label}):")
        interpretations = legal_query.interpretations_of(statute_focus_id)
        if not interpretations:
            lines.append("— (brak krawędzi INTERPRETS)")
        else:
            for node in interpretations:
                thesis = (node.description or "").strip()
                lines.append(f"— {node.name}: {thesis}" if thesis else f"— {node.name}")

    return "\n".join(lines).rstrip() + "\n"