"""
Topological Sort tests.

Sprint: GRAPH-006
"""

import pytest

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode
from knowledge.topological_sort import TopologicalSort


def create_graph() -> KnowledgeGraph:

    graph = KnowledgeGraph()

    graph.add_node(KnowledgeNode(id="A", name="A"))
    graph.add_node(KnowledgeNode(id="B", name="B"))
    graph.add_node(KnowledgeNode(id="C", name="C"))
    graph.add_node(KnowledgeNode(id="D", name="D"))

    graph.add_edge(
        KnowledgeEdge(
            source="A",
            target="B",
        )
    )

    graph.add_edge(
        KnowledgeEdge(
            source="A",
            target="C",
        )
    )

    graph.add_edge(
        KnowledgeEdge(
            source="B",
            target="D",
        )
    )

    graph.add_edge(
        KnowledgeEdge(
            source="C",
            target="D",
        )
    )

    return graph


def test_topological_sort() -> None:

    algorithm = TopologicalSort(create_graph())

    order = algorithm.sort()

    assert len(order) == 4

    assert order.index("A") < order.index("B")
    assert order.index("A") < order.index("C")
    assert order.index("B") < order.index("D")
    assert order.index("C") < order.index("D")


def test_empty_graph() -> None:

    graph = KnowledgeGraph()

    algorithm = TopologicalSort(graph)

    assert algorithm.sort() == []


def test_single_node() -> None:

    graph = KnowledgeGraph()

    graph.add_node(
        KnowledgeNode(
            id="A",
            name="A",
        )
    )

    algorithm = TopologicalSort(graph)

    assert algorithm.sort() == ["A"]


def test_cycle_detection() -> None:

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

    algorithm = TopologicalSort(graph)

    with pytest.raises(ValueError):
        algorithm.sort()


def test_disconnected_graph() -> None:

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

    algorithm = TopologicalSort(graph)

    order = algorithm.sort()

    assert len(order) == 3

    assert order.index("A") < order.index("B")
