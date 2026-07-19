"""
Knowledge Graph tests.

File: tests/test_graph.py
Sprint: GRAPH-001
"""

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode


def test_graph_initially_empty() -> None:
    graph = KnowledgeGraph()

    assert graph.node_count() == 0
    assert graph.edge_count() == 0


def test_add_node() -> None:
    graph = KnowledgeGraph()

    node = KnowledgeNode(
        id="person",
        name="Person",
    )

    graph.add_node(node)

    assert graph.node_count() == 1
    assert graph.has_node("person")
    assert graph.get_node("person") is node


def test_add_two_nodes() -> None:
    graph = KnowledgeGraph()

    graph.add_node(
        KnowledgeNode(
            id="person",
            name="Person",
        )
    )

    graph.add_node(
        KnowledgeNode(
            id="company",
            name="Company",
        )
    )

    assert graph.node_count() == 2


def test_add_edge() -> None:
    graph = KnowledgeGraph()

    graph.add_node(
        KnowledgeNode(
            id="person",
            name="Person",
        )
    )

    graph.add_node(
        KnowledgeNode(
            id="company",
            name="Company",
        )
    )

    edge = KnowledgeEdge(
        source="person",
        target="company",
    )

    graph.add_edge(edge)

    assert graph.edge_count() == 1


def test_unknown_node_returns_none() -> None:
    graph = KnowledgeGraph()

    assert graph.get_node("missing") is None


def test_has_node_false() -> None:
    graph = KnowledgeGraph()

    assert graph.has_node("missing") is False


def test_graph_string() -> None:
    graph = KnowledgeGraph()

    assert str(graph) == "KnowledgeGraph(nodes=0, edges=0)"


def test_remove_node() -> None:
    graph = KnowledgeGraph()

    node = KnowledgeNode(
        id="person",
        name="Person",
    )

    graph.add_node(node)

    graph.remove_node("person")

    assert graph.node_count() == 0
    assert graph.get_node("person") is None


def test_clear_graph() -> None:
    graph = KnowledgeGraph()

    graph.add_node(
        KnowledgeNode(
            id="a",
            name="A",
        )
    )

    graph.add_node(
        KnowledgeNode(
            id="b",
            name="B",
        )
    )

    graph.clear()

    assert graph.node_count() == 0
    assert graph.edge_count() == 0


def test_neighbors() -> None:
    graph = KnowledgeGraph()

    graph.add_node(
        KnowledgeNode(
            id="a",
            name="A",
        )
    )

    graph.add_node(
        KnowledgeNode(
            id="b",
            name="B",
        )
    )

    graph.add_edge(
        KnowledgeEdge(
            source="a",
            target="b",
        )
    )

    neighbors = graph.neighbors("a")

    assert len(neighbors) == 1
    assert neighbors[0].id == "b"