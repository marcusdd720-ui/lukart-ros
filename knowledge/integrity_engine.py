"""
IntegrityEngine — enterprise quality gate for case export.

Levels:
  PASS    — no findings of concern
  WARNING — export allowed, issues recorded
  BLOCK   — export must not proceed

Combines:
  - Graph structure (GRAPH00x)
  - Domain coverage (facts↔evidence, issues↔facts/law, arguments↔facts)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum, auto

from knowledge.graph import KnowledgeGraph
from knowledge.graph_integrity import GraphFinding, Severity, check_graph_integrity
from knowledge.models.case import Case


class IntegrityLevel(StrEnum):
    PASS = auto()
    WARNING = auto()
    BLOCK = auto()


class ExportStatus(StrEnum):
    READY = auto()
    READY_WITH_WARNINGS = auto()
    BLOCKED = auto()


@dataclass(slots=True)
class IntegrityFinding:
    level: IntegrityLevel
    code: str
    message: str


@dataclass(slots=True)
class IntegrityReport:
    findings: list[IntegrityFinding] = field(default_factory=list)
    graph_ok: bool = True
    level: IntegrityLevel = IntegrityLevel.PASS
    export_status: ExportStatus = ExportStatus.READY

    @property
    def blocks(self) -> list[IntegrityFinding]:
        return [f for f in self.findings if f.level == IntegrityLevel.BLOCK]

    @property
    def warnings(self) -> list[IntegrityFinding]:
        return [f for f in self.findings if f.level == IntegrityLevel.WARNING]

    def report(self) -> str:
        lines = [
            "IntegrityEngine",
            f"LEVEL:          {self.level.name}",
            f"EXPORT STATUS:  {self.export_status.name}",
            f"BLOCKS:         {len(self.blocks)}",
            f"WARNINGS:       {len(self.warnings)}",
            f"GRAPH OK:       {self.graph_ok}",
            "",
        ]
        for label, group in (("BLOCKS", self.blocks), ("WARNINGS", self.warnings)):
            if not group:
                continue
            lines.append(label)
            for f in group:
                lines.append(f"  [{f.code}] {f.message}")
            lines.append("")
        lines.append(f"RESULT: {self.level.name}")
        return "\n".join(lines)


def _map_graph_finding(gf: GraphFinding) -> IntegrityFinding:
    if gf.severity == Severity.ERROR:
        level = IntegrityLevel.BLOCK
    elif gf.severity == Severity.WARNING:
        level = IntegrityLevel.WARNING
    else:
        level = IntegrityLevel.PASS
    return IntegrityFinding(level=level, code=gf.code, message=gf.message)


def _domain_coverage(case: Case) -> list[IntegrityFinding]:
    findings: list[IntegrityFinding] = []

    facts_without_evidence = [
        f.id for f in case.facts if not (f.evidence_ids or f.source_refs)
    ]
    if facts_without_evidence:
        findings.append(
            IntegrityFinding(
                IntegrityLevel.WARNING,
                "COV001",
                f"{len(facts_without_evidence)} fact(s) without evidence_ids/source_refs",
            )
        )

    issues_without_facts = [i.id for i in case.legal_issues if not i.fact_ids]
    if issues_without_facts:
        findings.append(
            IntegrityFinding(
                IntegrityLevel.BLOCK,
                "COV002",
                f"{len(issues_without_facts)} issue(s) without facts",
            )
        )

    issues_without_law = [
        i.id
        for i in case.legal_issues
        if not (i.statute_refs or i.case_law_refs or i.legal_basis_ids)
    ]
    if issues_without_law:
        findings.append(
            IntegrityFinding(
                IntegrityLevel.WARNING,
                "COV003",
                f"{len(issues_without_law)} issue(s) without legal basis refs",
            )
        )

    args_without_facts = [
        a.id for a in case.arguments if not a.support_fact_ids
    ]
    if args_without_facts:
        findings.append(
            IntegrityFinding(
                IntegrityLevel.BLOCK,
                "COV004",
                f"{len(args_without_facts)} argument(s) without support facts",
            )
        )

    if not case.decisions:
        findings.append(
            IntegrityFinding(
                IntegrityLevel.WARNING,
                "COV005",
                "Case has no Decision — dossier render will fail",
            )
        )

    if case.facts and not case.evidence_items:
        findings.append(
            IntegrityFinding(
                IntegrityLevel.WARNING,
                "COV006",
                "Facts present but evidence_items empty",
            )
        )

    return findings


def run_integrity(
    graph: KnowledgeGraph,
    case: Case,
) -> IntegrityReport:
    """
    Full integrity gate.

    BLOCK  → export must not proceed
    WARNING → export allowed with recorded issues
    PASS   → clean
    """
    findings: list[IntegrityFinding] = []

    graph_report = check_graph_integrity(graph, case)
    graph_ok = graph_report.ok
    for gf in graph_report.findings:
        if gf.severity == Severity.INFO:
            continue
        findings.append(_map_graph_finding(gf))

    findings.extend(_domain_coverage(case))

    has_block = any(f.level == IntegrityLevel.BLOCK for f in findings)
    has_warn = any(f.level == IntegrityLevel.WARNING for f in findings)

    if has_block:
        level = IntegrityLevel.BLOCK
        export_status = ExportStatus.BLOCKED
    elif has_warn:
        level = IntegrityLevel.WARNING
        export_status = ExportStatus.READY_WITH_WARNINGS
    else:
        level = IntegrityLevel.PASS
        export_status = ExportStatus.READY

    return IntegrityReport(
        findings=findings,
        graph_ok=graph_ok,
        level=level,
        export_status=export_status,
    )


class IntegrityEngine:
    """Thin facade for workspace / CI."""

    @staticmethod
    def run(graph: KnowledgeGraph, case: Case) -> IntegrityReport:
        return run_integrity(graph, case)