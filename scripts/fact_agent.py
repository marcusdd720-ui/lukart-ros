"""
FactAgent v1 – evidence hygiene on Case.facts (no LLM).

Does not import any specific case builder.
CLI may load a case via CaseSpec registry.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from knowledge.models.case import Case, FactStatus


@dataclass(slots=True)
class FactFinding:
    severity: str
    code: str
    fact_id: str
    message: str


def review_case_facts(case: Case) -> list[FactFinding]:
    findings: list[FactFinding] = []

    if not case.facts:
        findings.append(
            FactFinding(
                severity="ERROR",
                code="FACT000",
                fact_id="-",
                message="Case has no facts.",
            )
        )
        return findings

    for fact in case.facts:
        fid = fact.id[:8]
        statement = (fact.statement or "").strip()

        if not statement:
            findings.append(
                FactFinding("ERROR", "FACT001", fid, "Empty fact statement.")
            )
            continue

        if len(statement) < 20:
            findings.append(
                FactFinding(
                    "WARNING",
                    "FACT002",
                    fid,
                    f"Very short statement ({len(statement)} chars).",
                )
            )

        if not fact.source_refs:
            kind = str(fact.metadata.get("kind", ""))
            if kind == "party_statement":
                findings.append(
                    FactFinding(
                        "INFO",
                        "FACT003",
                        fid,
                        "Party statement without document source_refs (allowed if marked).",
                    )
                )
            else:
                findings.append(
                    FactFinding(
                        "ERROR",
                        "FACT004",
                        fid,
                        "Fact has no source_refs (evidence link missing).",
                    )
                )

        if fact.status == FactStatus.UNVERIFIED and fact.source_refs:
            findings.append(
                FactFinding(
                    "INFO",
                    "FACT005",
                    fid,
                    "Has sources but status is still UNVERIFIED.",
                )
            )

        if fact.status == FactStatus.REJECTED:
            findings.append(
                FactFinding(
                    "WARNING",
                    "FACT006",
                    fid,
                    "Fact marked REJECTED – should not drive decision without note.",
                )
            )

    return findings


def format_report(case: Case, findings: list[FactFinding]) -> str:
    errors = [f for f in findings if f.severity == "ERROR"]
    warnings = [f for f in findings if f.severity == "WARNING"]
    infos = [f for f in findings if f.severity == "INFO"]

    lines = [
        "FactAgent report",
        f"Case: {case.display_title()}",
        f"Facts: {len(case.facts)}",
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
            lines.append(f"  [{f.code}] fact={f.fact_id} – {f.message}")
        lines.append("")

    if errors:
        lines.append("RESULT: FAIL")
    elif warnings:
        lines.append("RESULT: PASS WITH WARNINGS")
    else:
        lines.append("RESULT: PASS")
    return "\n".join(lines)


def _load_case(case_key: str) -> Case:
    from knowledge.models.case_registry import get_spec

    spec = get_spec(case_key)
    ws = spec.open()
    return ws.case


def main() -> int:
    parser = argparse.ArgumentParser(description="FactAgent – review Case.facts")
    parser.add_argument(
        "--case",
        default="DS_3960_2025",
        help="Case key from case_registry (default: DS_3960_2025)",
    )
    args = parser.parse_args()

    try:
        case = _load_case(args.case)
    except KeyError as exc:
        print(exc)
        return 2

    findings = review_case_facts(case)
    print(format_report(case, findings))
    return 1 if any(f.severity == "ERROR" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())