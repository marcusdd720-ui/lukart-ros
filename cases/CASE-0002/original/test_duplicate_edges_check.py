"""
Knowledge Operating System (KOS)

Sprint GRAPH-010B

Tests for DuplicateEdgesCheck.
"""

from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode
from knowledge.edge import KnowledgeEdge

from knowledge.validation.result import ValidationResult
from knowledge.validation.checks.duplicate_edges import DuplicateEdgesCheck


def test_unique_edges() -> None:

    graph = KnowledgeGraph()

    graph.add_node(KnowledgeNode(id="A", name="A"))
    graph.add_node(KnowledgeNode(id="B", name="B"))

    graph.add_edge(
        KnowledgeEdge(
            source="A",
            target="B",
        )
    )

    result = ValidationResult()

    DuplicateEdgesCheck().validate(
        graph,
        result,
    )

    assert result.valid


def test_duplicate_edge() -> None:

    graph = KnowledgeGraph()

    graph.add_node(KnowledgeNode(id="A", name="A"))
    graph.add_node(KnowledgeNode(id="B", name="B"))

    edge = KnowledgeEdge(
        source="A",
        target="B",
    )

    graph.add_edge(edge)
    graph.add_edge(edge)

    result = ValidationResult()

    DuplicateEdgesCheck().validate(
        graph,
        result,
    )

    assert not result.valid

    assert len(result.issues) == 1

    assert result.issues[0].code == "DUPLICATE_EDGE"


def test_multiple_duplicate_edges() -> None:

    graph = KnowledgeGraph()

    graph.add_node(KnowledgeNode(id="A", name="A"))
    graph.add_node(KnowledgeNode(id="B", name="B"))
    graph.add_node(KnowledgeNode(id="C", name="C"))

    graph.add_edge(
        KnowledgeEdge(
            source="A",
            target="B",
        )
    )

    graph.add_edge(
        KnowledgeEdge(
            source="A",
            target="B",
        )
    )

    graph.add_edge(
        KnowledgeEdge(
            source="B",
            target="C",
        )
    )

    graph.add_edge(
        KnowledgeEdge(
            source="B",
            target="C",
        )
    )

    result = ValidationResult()

    DuplicateEdgesCheck().validate(
        graph,
        result,
    )

    assert len(result.issues) == 2


def test_empty_graph() -> None:

    graph = KnowledgeGraph()

    result = ValidationResult()

    DuplicateEdgesCheck().validate(
        graph,
        result,
    )

    assert result.valid