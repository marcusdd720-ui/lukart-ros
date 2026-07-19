"""
Dijkstra tests.

Sprint GRAPH-007
"""

from knowledge.dijkstra import Dijkstra
from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode


def create_graph() -> KnowledgeGraph:

    graph = KnowledgeGraph()

    for node in ["A", "B", "C", "D", "E"]:

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
            target="E",
        )
    )

    graph.add_edge(
        KnowledgeEdge(
            source="D",
            target="E",
        )
    )

    return graph


def test_shortest_path() -> None:

    algorithm = Dijkstra(create_graph())

    path = algorithm.shortest_path(
        "A",
        "E",
    )

    assert path in (
        ["A", "C", "E"],
        ["A", "B", "D", "E"],
    )


def test_distance() -> None:

    algorithm = Dijkstra(create_graph())

    assert algorithm.distance(
        "A",
        "E",
    ) == 2


def test_unknown_source() -> None:

    algorithm = Dijkstra(create_graph())

    assert algorithm.shortest_path(
        "X",
        "E",
    ) == []


def test_unknown_target() -> None:

    algorithm = Dijkstra(create_graph())

    assert algorithm.shortest_path(
        "A",
        "X",
    ) == []


def test_unreachable() -> None:

    graph = create_graph()

    graph.add_node(
        KnowledgeNode(
            id="Z",
            name="Z",
        )
    )

    algorithm = Dijkstra(graph)

    assert algorithm.shortest_path(
        "A",
        "Z",
    ) == []

    assert algorithm.distance(
        "A",
        "Z",
    ) is None