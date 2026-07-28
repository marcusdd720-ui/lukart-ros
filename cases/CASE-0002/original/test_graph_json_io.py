from pathlib import Path

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode
from knowledge.serialization.json_io import GraphJsonIO


def test_save_empty_graph(tmp_path: Path):

    graph = KnowledgeGraph()

    file = tmp_path / "graph.json"

    GraphJsonIO().save(graph, file)

    assert file.exists()


def test_load_empty_graph(tmp_path: Path):

    graph = KnowledgeGraph()

    file = tmp_path / "graph.json"

    io = GraphJsonIO()

    io.save(graph, file)

    loaded = io.load(file)

    assert loaded.node_count() == 0
    assert loaded.edge_count() == 0


def test_roundtrip_single_node(tmp_path: Path):

    graph = KnowledgeGraph()

    graph.add_node(
        KnowledgeNode(
            id="A",
            name="Node A",
        )
    )

    file = tmp_path / "graph.json"

    io = GraphJsonIO()

    io.save(graph, file)

    loaded = io.load(file)

    assert loaded.node_count() == 1
    assert loaded.has_node("A")


def test_roundtrip_graph(tmp_path: Path):

    graph = KnowledgeGraph()

    graph.add_node(KnowledgeNode(id="A", name="A"))
    graph.add_node(KnowledgeNode(id="B", name="B"))

    graph.add_edge(
        KnowledgeEdge(
            source="A",
            target="B",
        )
    )

    file = tmp_path / "graph.json"

    io = GraphJsonIO()

    io.save(graph, file)

    loaded = io.load(file)

    assert loaded.node_count() == 2
    assert loaded.edge_count() == 1
