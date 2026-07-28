"""
Knowledge Operating System (KOS)

Sprint GRAPH-010B

Tests for OrphanNodesCheck.
"""

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode
from knowledge.validation.checks.orphan_nodes import OrphanNodesCheck
from knowledge.validation.result import ValidationResult


def test_graph_without_orphans() -> None:

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

    OrphanNodesCheck().validate(
        graph,
        result,
    )

    assert result.valid


def test_single_orphan() -> None:

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

    result = ValidationResult()

    OrphanNodesCheck().validate(
        graph,
        result,
    )

    assert not result.valid

    assert len(result.issues) == 1

    assert result.issues[0].code == "ORPHAN_NODE"

    assert "C" in result.issues[0].message


def test_empty_graph() -> None:

    graph = KnowledgeGraph()

    result = ValidationResult()

    OrphanNodesCheck().validate(
        graph,
        result,
    )

    assert result.valid


def test_single_node_graph() -> None:

    graph = KnowledgeGraph()

    graph.add_node(
        KnowledgeNode(
            id="A",
            name="A",
        )
    )

    result = ValidationResult()

    OrphanNodesCheck().validate(
        graph,
        result,
    )

    assert not result.valid

    assert result.issues[0].code == "ORPHAN_NODE"
