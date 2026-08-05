"""
LawAgent v0 – check that a case is linked to STATUTE / CASE_LAW in the graph.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from knowledge.legal_query import LegalQuery
from scripts.link_case_to_law import link_ds_3960


@dataclass(slots=True)
class LawFinding:
    severity: str
    code: str
    message: str


def review_case_law_links(case_id: str = "case:DS.3960.2025") -> tuple[list[LawFinding], LegalQuery, str]:
    graph, linked_id = link_ds_3960()
    cid = linked_id or case_id
    lq = LegalQuery(graph)
    findings: list[LawFinding] = []

    if not graph.has_node(cid):
        findings.append(
            LawFinding("ERROR", "LAW001", f"Case node missing in graph: {cid}")
        )
        return findings, lq, cid

    statutes = lq.relies_on(cid)
    authorities = lq.supported_by(cid)

    if not statutes:
        findings.append(
            LawFinding("ERROR", "LAW002", "No RELIES_ON statutes linked to case.")
        )
    elif len(statutes) < 2:
        findings.append(
            LawFinding(
                "WARNING",
                "LAW003",
                f"Only {len(statutes)} statute(s) linked – consider full legal basis.",
            )
        )

    if not authorities:
        findings.append(
            LawFinding(
                "ERROR",
                "LAW004",
                "No SUPPORTED_BY case-law linked to case.",
            )
        )

    # Focus article 284 for this criminal case
    interps = lq.interpretations_of("statute:kk:284:2")
    if not interps:
        findings.append(
            LawFinding(
                "WARNING",
                "LAW005",
                "No INTERPRETS edges for art. 284 § 2 in library.",
            )
        )

    if not findings:
        findings.append(
            LawFinding(
                "INFO",
                "LAW000",
                f"OK: {len(statutes)} statutes, {len(authorities)} case-law nodes.",
            )
        )

    return findings, lq, cid


def format_report(findings: list[LawFinding], case_id: str) -> str:
    errors = [f for f in findings if f.severity == "ERROR"]
    warnings = [f for f in findings if f.severity == "WARNING"]
    infos = [f for f in findings if f.severity == "INFO"]

    lines = [
        "LawAgent report",
        f"Case node: {case_id}",
        f"ERRORS:   {len(errors)}",
        f"WARNINGS: {len(warnings)}",
        f"INFO:     {len(infos)}",
        "",
    ]
    for label, group in (("ERRORS", errors), ("WARNINGS", warnings), ("INFO", infos)):
        if not group:
            continue
        lines.append(label)
        for f in group:
            lines.append(f"  [{f.code}] {f.message}")
        lines.append("")

    if errors:
        lines.append("RESULT: FAIL")
    elif warnings:
        lines.append("RESULT: PASS WITH WARNINGS")
    else:
        lines.append("RESULT: PASS")
    return "\n".join(lines)


def main() -> int:
    findings, _lq, cid = review_case_law_links()
    print(format_report(findings, cid))
    return 1 if any(f.severity == "ERROR" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())