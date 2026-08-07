"""
Graph Integrity Gate.

Machine-readable checks for domain ↔ graph consistency.
Codes:
  GRAPH001 dangling edge
  GRAPH002 argument without ADVANCES to issue
  GRAPH003 issue without RAISES from fact
  GRAPH004 domain ↔ graph count drift
  GRAPH000 OK summary
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, auto

from knowledge.graph import KnowledgeGraph
from knowledge.models.case import Case
from knowledge.types import EdgeType, NodeType


class Severity(StrEnum):
    INFO = auto()
    WARNING = auto()
    ERROR = auto()


@dataclass(slots=True)
class GraphFinding:
    severity: Severity
    code: str
    message: str


@dataclass(slots=True)
class GraphIntegrityReport:
    findings: list[GraphFinding]

    @property
    def ok(self) -> bool:
        return not any(f.severity == Severity.ERROR for f in self.findings)

    @property
    def errors(self) -> list[GraphFinding]:
        return [f for f in self.findings if f.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[GraphFinding]:
        return [f for f in self.findings if f.severity == Severity.WARNING]

    def report(self) -> str:
        lines = [
            "GraphIntegrity",
            f"ERRORS:   {len(self.errors)}",
            f"WARNINGS: {len(self.warnings)}",
            "",
        ]
        for label, group in (("ERRORS", self.errors), ("WARNINGS", self.warnings)):
            if not group:
                continue
            lines.append(label)
            for f in group:
                lines.append(f"  [{f.code}] {f.message}")
            lines.append("")
        lines.append("RESULT: PASS" if self.ok else "RESULT: FAIL")
        return "\n".join(lines)


def check_graph_integrity(
    graph: KnowledgeGraph,
    case: Case | None = None,
) -> GraphIntegrityReport:
    findings: list[GraphFinding] = []

    # GRAPH001 – dangling edges
    for e in graph.edges:
        if not graph.has_node(e.source):
            findings.append(
                GraphFinding(
                    Severity.ERROR,
                    "GRAPH001",
                    f"Dangling edge source missing: {e.source} --{e.type.name}--> {e.target}",
                )
            )
        if not graph.has_node(e.target):
            findings.append(
                GraphFinding(
                    Severity.ERROR,
                    "GRAPH001",
                    f"Dangling edge target missing: {e.source} --{e.type.name}--> {e.target}",
                )
            )

    issues = [n for n in graph if n.type == NodeType.ISSUE]
    arguments = [n for n in graph if n.type == NodeType.ARGUMENT]
    facts = [n for n in graph if n.type == NodeType.FACT]

    raises = [e for e in graph.edges if e.type == EdgeType.RAISES]
    advances = [e for e in graph.edges if e.type == EdgeType.ADVANCES]

    issue_ids_with_raises = {e.target for e in raises}
    arg_ids_with_advances = {e.source for e in advances}

    # GRAPH003 – issue without RAISES
    for issue in issues:
        if issue.id not in issue_ids_with_raises:
            findings.append(
                GraphFinding(
                    Severity.WARNING,
                    "GRAPH003",
                    f"ISSUE without RAISES from FACT: {issue.id}",
                )
            )

    # GRAPH002 – argument without ADVANCES
    for arg in arguments:
        if arg.id not in arg_ids_with_advances:
            findings.append(
                GraphFinding(
                    Severity.ERROR,
                    "GRAPH002",
                    f"ARGUMENT without ADVANCES to ISSUE: {arg.id}",
                )
            )

    # Domain ↔ graph count drift
    if case is not None:
        if len(facts) != len(case.facts):
            findings.append(
                GraphFinding(
                    Severity.WARNING,
                    "GRAPH004",
                    f"Fact count drift: domain={len(case.facts)} graph={len(facts)}",
                )
            )
        if len(issues) != len(case.legal_issues):
            findings.append(
                GraphFinding(
                    Severity.ERROR,
                    "GRAPH004",
                    f"Issue count drift: domain={len(case.legal_issues)} graph={len(issues)}",
                )
            )
        if len(arguments) != len(case.arguments):
            findings.append(
                GraphFinding(
                    Severity.ERROR,
                    "GRAPH004",
                    f"Argument count drift: domain={len(case.arguments)} graph={len(arguments)}",
                )
            )

    if not any(f.severity in (Severity.ERROR, Severity.WARNING) for f in findings):
        findings.append(
            GraphFinding(
                Severity.INFO,
                "GRAPH000",
                f"OK: facts={len(facts)} issues={len(issues)} args={len(arguments)} "
                f"raises={len(raises)} advances={len(advances)}",
            )
        )

    return GraphIntegrityReport(findings=findings)