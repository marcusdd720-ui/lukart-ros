"""
Graph Validator tests.

Sprint GRAPH-009
"""

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.graph_validator import GraphValidator
from knowledge.node import KnowledgeNode


def test_valid_graph() -> None:

    graph = KnowledgeGraph()

    graph.add_node(KnowledgeNode(id="A", name="A"))

    graph.add_node(KnowledgeNode(id="B", name="B"))

    graph.add_edge(
        KnowledgeEdge(
            source="A",
            target="B",
        )
    )

    result = GraphValidator().validate(graph)

    assert result.valid
    assert len(result.issues) == 0


def test_unknown_source() -> None:

    graph = KnowledgeGraph()

    graph.add_node(KnowledgeNode(id="B", name="B"))

    graph.edges.append(
        KnowledgeEdge(
            source="A",
            target="B",
        )
    )

    result = GraphValidator().validate(graph)

    assert not result.valid

    assert any(issue.code == "UNKNOWN_SOURCE" for issue in result.issues)


def test_unknown_target() -> None:

    graph = KnowledgeGraph()

    graph.add_node(KnowledgeNode(id="A", name="A"))

    graph.edges.append(
        KnowledgeEdge(
            source="A",
            target="B",
        )
    )

    result = GraphValidator().validate(graph)

    assert not result.valid

    assert any(issue.code == "UNKNOWN_TARGET" for issue in result.issues)


def test_cycle_detected() -> None:

    graph = KnowledgeGraph()

    graph.add_node(KnowledgeNode(id="A", name="A"))

    graph.add_node(KnowledgeNode(id="B", name="B"))

    graph.add_edge(
        KnowledgeEdge(
            source="A",
            target="B",
        )
    )

    graph.add_edge(
        KnowledgeEdge(
            source="B",
            target="A",
        )
    )

    result = GraphValidator().validate(graph)

    assert not result.valid

    assert any(issue.code == "GRAPH_CYCLE" for issue in result.issues)


def test_empty_graph() -> None:

    graph = KnowledgeGraph()

    result = GraphValidator().validate(graph)

    assert result.valid
