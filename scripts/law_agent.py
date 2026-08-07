"""
LawAgent v3 – legal link + domain chain checks via LegalQuery.

Does not mutate the graph.
Does not project nodes.
Does not invent authorities.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from knowledge.graph import KnowledgeGraph  # noqa: E402
from knowledge.legal_query import LegalQuery  # noqa: E402
from knowledge.types import NodeType  # noqa: E402


@dataclass(slots=True)
class LawFinding:
    severity: str
    code: str
    message: str


def review_case_law_links(
    graph: KnowledgeGraph,
    case_id: str,
    *,
    focus_statute_id: str | None = None,
) -> list[LawFinding]:
    findings: list[LawFinding] = []
    lq = LegalQuery(graph)

    if not graph.has_node(case_id):
        findings.append(
            LawFinding("ERROR", "LAW001", f"Case node missing in graph: {case_id}")
        )
        return findings

    statutes = lq.relies_on(case_id)
    authorities = lq.supported_by(case_id)
    issues = lq.issues()
    arguments = lq.arguments()
    facts = lq.facts()

    # --- classic case-level links ---
    if not statutes:
        findings.append(
            LawFinding("ERROR", "LAW002", "No RELIES_ON statutes linked to case.")
        )

    if not authorities:
        findings.append(
            LawFinding(
                "ERROR",
                "LAW004",
                "No SUPPORTED_BY case-law linked to case.",
            )
        )

    if focus_statute_id:
        interps = lq.interpretations_of(focus_statute_id)
        if not interps:
            findings.append(
                LawFinding(
                    "WARNING",
                    "LAW005",
                    f"No INTERPRETS edges for focus statute {focus_statute_id}.",
                )
            )

    # --- ISSUE bridge ---
    if not issues:
        findings.append(
            LawFinding(
                "WARNING",
                "LAW010",
                "No ISSUE nodes present in graph – LegalIssue bridge not projected yet.",
            )
        )
    else:
        without_basis = []
        without_facts = []
        for issue in issues:
            basis = lq.authorities_for_issue(issue.id)
            if not basis:
                without_basis.append(issue.id)
            raising = lq.facts_raising(issue.id)
            if not raising:
                without_facts.append(issue.id)

        if without_basis:
            findings.append(
                LawFinding(
                    "WARNING",
                    "LAW011",
                    f"{len(without_basis)} ISSUE node(s) have no RELIES_ON legal basis: "
                    f"{without_basis[:5]}",
                )
            )
        else:
            findings.append(
                LawFinding(
                    "INFO",
                    "LAW012",
                    f"All {len(issues)} ISSUE node(s) have RELIES_ON legal basis.",
                )
            )

        if without_facts:
            findings.append(
                LawFinding(
                    "WARNING",
                    "LAW013",
                    f"{len(without_facts)} ISSUE node(s) have no RAISES from FACT: "
                    f"{without_facts[:5]}",
                )
            )

    # --- ARGUMENT bridge ---
    if not arguments:
        findings.append(
            LawFinding(
                "WARNING",
                "LAW020",
                "No ARGUMENT nodes present in graph – Argument bridge not projected yet.",
            )
        )
    else:
        orphan_args = []
        for arg in arguments:
            targets = lq.issue_for_argument(arg.id)
            if not targets:
                orphan_args.append(arg.id)
        if orphan_args:
            findings.append(
                LawFinding(
                    "ERROR",
                    "LAW021",
                    f"{len(orphan_args)} ARGUMENT node(s) without ADVANCES: "
                    f"{orphan_args[:5]}",
                )
            )
        else:
            findings.append(
                LawFinding(
                    "INFO",
                    "LAW022",
                    f"All {len(arguments)} ARGUMENT node(s) have ADVANCES to ISSUE.",
                )
            )

    # --- FACT bridge (presence only; evidence link optional until domain fills evidence_ids) ---
    if not facts:
        findings.append(
            LawFinding(
                "WARNING",
                "LAW030",
                "No FACT nodes present in graph – Fact projection missing.",
            )
        )
    else:
        findings.append(
            LawFinding(
                "INFO",
                "LAW031",
                f"{len(facts)} FACT node(s) present in graph.",
            )
        )

    if not any(f.severity == "ERROR" for f in findings):
        findings.append(
            LawFinding(
                "INFO",
                "LAW000",
                f"OK: {len(statutes)} statutes, {len(authorities)} case-law, "
                f"{len(issues)} issues, {len(arguments)} arguments, {len(facts)} facts.",
            )
        )

    return findings


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
    parser = argparse.ArgumentParser(description="LawAgent – review graph legal links")
    parser.add_argument(
        "--case",
        default="DS_3960_2025",
        help="Case key from case_registry",
    )
    parser.add_argument(
        "--focus-statute",
        default=None,
        help="Optional statute node id for INTERPRETS check",
    )
    args = parser.parse_args()

    try:
        from knowledge.models.case_registry import get_spec

        spec = get_spec(args.case)
        ws = spec.open()
    except KeyError as exc:
        print(exc)
        return 2

    focus = args.focus_statute
    if focus is None and args.case == "DS_3960_2025":
        focus = "statute:kk:284:2"

    findings = review_case_law_links(
        ws.graph,
        ws.graph_case_id,
        focus_statute_id=focus,
    )
    print(format_report(findings, ws.graph_case_id))
    return 1 if any(f.severity == "ERROR" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())