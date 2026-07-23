"""
Traversal tests.

Sprint: GRAPH-002
"""

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode
from knowledge.traversal import GraphTraversal


def create_graph() -> KnowledgeGraph:
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
            source="B",
            target="C",
        )
    )

    return graph


def test_neighbors() -> None:
    traversal = GraphTraversal(create_graph())

    neighbors = traversal.neighbors("A")

    assert len(neighbors) == 1
    assert neighbors[0].id == "B"


def test_has_path_true() -> None:
    traversal = GraphTraversal(create_graph())

    assert traversal.has_path("A", "C")


def test_has_path_false() -> None:
    traversal = GraphTraversal(create_graph())

    assert not traversal.has_path("C", "A")


def test_same_node() -> None:
    traversal = GraphTraversal(create_graph())

    assert traversal.has_path("A", "A")