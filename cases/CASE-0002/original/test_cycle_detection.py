"""
Cycle Detection tests.

Sprint GRAPH-008
"""

from knowledge.cycle_detection import CycleDetection
from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode


def create_acyclic_graph() -> KnowledgeGraph:

    graph = KnowledgeGraph()

    for node in ["A", "B", "C", "D"]:
        graph.add_node(
            KnowledgeNode(
                id=node,
                name=node,
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
            source="C",
            target="D",
        )
    )

    return graph


def create_cyclic_graph() -> KnowledgeGraph:

    graph = create_acyclic_graph()

    graph.add_edge(
        KnowledgeEdge(
            source="D",
            target="A",
        )
    )

    return graph


def test_acyclic_graph() -> None:

    algorithm = CycleDetection(create_acyclic_graph())

    assert algorithm.has_cycle() is False


def test_cycle_exists() -> None:

    algorithm = CycleDetection(create_cyclic_graph())

    assert algorithm.has_cycle() is True


def test_empty_graph() -> None:

    graph = KnowledgeGraph()

    algorithm = CycleDetection(graph)

    assert algorithm.has_cycle() is False


def test_single_node() -> None:

    graph = KnowledgeGraph()

    graph.add_node(
        KnowledgeNode(
            id="A",
            name="A",
        )
    )

    algorithm = CycleDetection(graph)

    assert algorithm.has_cycle() is False


def test_self_loop() -> None:

    graph = KnowledgeGraph()

    graph.add_node(
        KnowledgeNode(
            id="A",
            name="A",
        )
    )

    graph.add_edge(
        KnowledgeEdge(
            source="A",
            target="A",
        )
    )

    algorithm = CycleDetection(graph)

    assert algorithm.has_cycle() is True


def test_two_node_cycle() -> None:

    graph = KnowledgeGraph()

    graph.add_node(
        KnowledgeNode(
            id="A",
            name="A",
        )
    )

    graph.add_node(
        KnowledgeNode(
            id="B",
            name="B",
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
            target="A",
        )
    )

    algorithm = CycleDetection(graph)

    assert algorithm.has_cycle() is True
