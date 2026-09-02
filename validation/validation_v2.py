"""Validation 2.0: independent structural and graph validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from knowledge.graph import KnowledgeGraph


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    """One deterministic validation finding."""

    code: str
    message: str


@dataclass(slots=True)
class ValidationReport:
    """Deterministic validation report with explicit pass/fail semantics."""

    findings: list[ValidationFinding] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.findings

    def add(self, code: str, message: str) -> None:
        self.findings.append(ValidationFinding(code=code, message=message))


class ValidationEngineV2:
    """Run independent project and graph validation checks."""

    required_directories = ("core", "knowledge", "validation", "tests")

    def validate_project(self, project: Path) -> ValidationReport:
        report = ValidationReport()
        for directory in self.required_directories:
            candidate = project / directory
            if not candidate.is_dir():
                report.add("MISSING_DIRECTORY", f"Required directory is missing: {directory}")
        return report

    def validate_graph(self, graph: KnowledgeGraph) -> ValidationReport:
        report = ValidationReport()
        report.findings.extend(
            ValidationFinding("GRAPH_INTEGRITY", message)
            for message in graph.validate_integrity()
        )
        for edge in graph.edges:
            if not edge.source or not edge.target:
                report.add("EDGE_ENDPOINT", "Graph edge endpoints must not be empty")
            if not 0.0 <= edge.confidence <= 1.0:
                report.add(
                    "EDGE_CONFIDENCE",
                    f"Graph edge confidence must be between 0 and 1: {edge.id}",
                )
        return report

    def validate(
        self,
        project: Path,
        graph: KnowledgeGraph | None = None,
    ) -> ValidationReport:
        report = self.validate_project(project)
        if graph is not None:
            report.findings.extend(self.validate_graph(graph).findings)
        return report
