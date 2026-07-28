"""
Breadth First Search tests.

Sprint: GRAPH-003
"""

from knowledge.bfs import BreadthFirstSearch
from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode


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

    return graph


def test_reachable_nodes() -> None:
    bfs = BreadthFirstSearch(create_graph())

    reachable = bfs.reachable_nodes("A")

    assert reachable == [
        "A",
        "B",
        "C",
        "D",
    ]


def test_shortest_path() -> None:
    bfs = BreadthFirstSearch(create_graph())

    path = bfs.shortest_path(
        "A",
        "D",
    )

    assert path == [
        "A",
        "B",
        "D",
    ]


def test_unknown_source() -> None:
    bfs = BreadthFirstSearch(create_graph())

    assert (
        bfs.shortest_path(
            "X",
            "D",
        )
        == []
    )


def test_unknown_target() -> None:
    bfs = BreadthFirstSearch(create_graph())

    assert (
        bfs.shortest_path(
            "A",
            "X",
        )
        == []
    )


def test_unreachable_node() -> None:

    graph = create_graph()

    graph.add_node(
        KnowledgeNode(
            id="Z",
            name="Z",
        )
    )

    bfs = BreadthFirstSearch(graph)

    assert (
        bfs.shortest_path(
            "A",
            "Z",
        )
        == []
    )
