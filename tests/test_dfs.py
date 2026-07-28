"""
Depth First Search tests.

Sprint: GRAPH-004
"""

from knowledge.dfs import DepthFirstSearch
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

    dfs = DepthFirstSearch(create_graph())

    nodes = dfs.reachable_nodes("A")

    assert nodes[0] == "A"
    assert "B" in nodes
    assert "C" in nodes
    assert "D" in nodes
    assert len(nodes) == 4


def test_has_path_true() -> None:

    dfs = DepthFirstSearch(create_graph())

    assert dfs.has_path(
        "A",
        "D",
    )


def test_has_path_false() -> None:

    dfs = DepthFirstSearch(create_graph())

    assert not dfs.has_path(
        "D",
        "A",
    )


def test_unknown_node() -> None:

    dfs = DepthFirstSearch(create_graph())

    assert not dfs.has_path(
        "X",
        "A",
    )


def test_empty_result() -> None:

    dfs = DepthFirstSearch(create_graph())

    assert dfs.reachable_nodes("X") == []
