from pathlib import Path

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode
from knowledge.types import EdgeType, NodeType
from validation.validation_v2 import ValidationEngineV2


def test_project_validation_passes_for_required_structure(tmp_path: Path) -> None:
    for directory in ("core", "knowledge", "validation", "tests"):
        (tmp_path / directory).mkdir()

    report = ValidationEngineV2().validate_project(tmp_path)

    assert report.passed
    assert report.findings == []


def test_project_validation_reports_missing_directory(tmp_path: Path) -> None:
    for directory in ("core", "knowledge", "validation"):
        (tmp_path / directory).mkdir()

    report = ValidationEngineV2().validate_project(tmp_path)

    assert not report.passed
    assert report.findings == [
        type(report.findings[0])(
            code="MISSING_DIRECTORY",
            message="Required directory is missing: tests",
        )
    ]


def test_graph_validation_passes_for_valid_graph() -> None:
    graph = KnowledgeGraph()
    graph.add_node(KnowledgeNode(id="a", type=NodeType.FACT, name="A"))
    graph.add_node(KnowledgeNode(id="b", type=NodeType.ISSUE, name="B"))
    graph.add_edge(KnowledgeEdge(source="a", target="b", type=EdgeType.RAISES, confidence=0.8))

    report = ValidationEngineV2().validate_graph(graph)

    assert report.passed


def test_graph_validation_reports_invalid_confidence() -> None:
    graph = KnowledgeGraph()
    graph.add_node(KnowledgeNode(id="a", type=NodeType.FACT, name="A"))
    graph.add_node(KnowledgeNode(id="b", type=NodeType.ISSUE, name="B"))
    edge = KnowledgeEdge(source="a", target="b", type=EdgeType.RAISES, confidence=1.0)
    graph.add_edge(edge)
    edge.confidence = 1.5

    report = ValidationEngineV2().validate_graph(graph)

    assert not report.passed
    assert any(finding.code == "EDGE_CONFIDENCE" for finding in report.findings)


def test_combined_validation_is_fail_closed() -> None:
    graph = KnowledgeGraph()
    graph.add_node(KnowledgeNode(id="a", type=NodeType.FACT, name="A"))

    report = ValidationEngineV2().validate(Path("/missing/project"), graph)

    assert not report.passed
    assert any(finding.code == "MISSING_DIRECTORY" for finding in report.findings)
