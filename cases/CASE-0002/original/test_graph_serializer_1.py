from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode

from knowledge.serialization.serializer import GraphSerializer


def test_empty_graph():

    graph = KnowledgeGraph()

    data = GraphSerializer().serialize(graph)

    assert data["nodes"] == []

    assert data["edges"] == []


def test_single_node():

    graph = KnowledgeGraph()

    graph.add_node(
        KnowledgeNode(
            id="A",
            name="Node A",
        )
    )

    data = GraphSerializer().serialize(graph)

    assert len(data["nodes"]) == 1

    assert data["nodes"][0]["id"] == "A"


def test_single_edge():

    graph = KnowledgeGraph()

    graph.add_node(
        KnowledgeNode(id="A", name="A")
    )

    graph.add_node(
        KnowledgeNode(id="B", name="B")
    )

    graph.add_edge(
        KnowledgeEdge(
            source="A",
            target="B",
        )
    )

    data = GraphSerializer().serialize(graph)

    assert len(data["edges"]) == 1

    assert data["edges"][0]["source"] == "A"

    assert data["edges"][0]["target"] == "B"


def test_node_and_edge_count():

    graph = KnowledgeGraph()

    for node in ["A", "B", "C"]:

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

    data = GraphSerializer().serialize(graph)

    assert len(data["nodes"]) == 3

    assert len(data["edges"]) == 2