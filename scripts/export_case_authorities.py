"""
K2.1 – Export legal authorities (statutes + SN theses) for a linked case.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from knowledge.legal_query import LegalQuery
from scripts.link_case_to_law import link_ds_3960


def export_authorities(case_id: str = "case:DS.3960.2025") -> str:
    graph, linked_id = link_ds_3960()
    if linked_id != case_id:
        case_id = linked_id

    lq = LegalQuery(graph)

    lines: list[str] = []
    lines.append("PODSTAWA PRAWNA I ORZECZNICTWO (z Knowledge Graph)")
    lines.append("")

    lines.append("I. Przepisy (RELIES_ON)")
    statutes = lq.relies_on(case_id)
    if not statutes:
        lines.append("  (brak)")
    else:
        for i, node in enumerate(statutes, 1):
            article = node.metadata.get("article", "")
            lines.append(f"  {i}. {node.name}" + (f" ({article})" if article else ""))
            if node.description:
                lines.append(f"     {node.description}")
    lines.append("")

    lines.append("II. Orzecznictwo (SUPPORTED_BY)")
    authorities = lq.supported_by(case_id)
    if not authorities:
        lines.append("  (brak)")
    else:
        for i, node in enumerate(authorities, 1):
            sig = node.metadata.get("signature", node.name)
            lines.append(f"  {i}. {sig}")
            thesis = (node.description or "").strip()
            if thesis:
                lines.append(f"     Teza: {thesis}")
    lines.append("")

    lines.append("III. Interpretacje art. 284 § 2 k.k. (biblioteka)")
    for node in lq.interpretations_of("statute:kk:284:2"):
        lines.append(f"  - {node.name}: {(node.description or '')[:160]}")

    return "\n".join(lines)


def main() -> None:
    text = export_authorities()
    print(text)

    out = Path("output") / "cases" / "DS_3960_2025" / "authorities_from_graph.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print("---")
    print("Saved:", out.resolve())


if __name__ == "__main__":
    main()