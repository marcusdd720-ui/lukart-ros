"""
Connected Components tests.

Sprint: GRAPH-005
"""

from knowledge.connected_components import ConnectedComponents
from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode


def create_graph() -> KnowledgeGraph:

    graph = KnowledgeGraph()

    graph.add_node(KnowledgeNode(id="A", name="A"))
    graph.add_node(KnowledgeNode(id="B", name="B"))
    graph.add_node(KnowledgeNode(id="C", name="C"))
    graph.add_node(KnowledgeNode(id="D", name="D"))
    graph.add_node(KnowledgeNode(id="E", name="E"))

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
            source="D",
            target="E",
        )
    )

    return graph


def test_two_components() -> None:

    graph = create_graph()

    algorithm = ConnectedComponents(graph)

    components = algorithm.find()

    assert len(components) == 2

    component_sizes = sorted(len(c) for c in components)

    assert component_sizes == [2, 3]


def test_single_component() -> None:

    graph = KnowledgeGraph()

    graph.add_node(KnowledgeNode(id="A", name="A"))
    graph.add_node(KnowledgeNode(id="B", name="B"))

    graph.add_edge(
        KnowledgeEdge(
            source="A",
            target="B",
        )
    )

    algorithm = ConnectedComponents(graph)

    components = algorithm.find()

    assert len(components) == 1
    assert len(components[0]) == 2


def test_empty_graph() -> None:

    graph = KnowledgeGraph()

    algorithm = ConnectedComponents(graph)

    assert algorithm.find() == []


def test_isolated_nodes() -> None:

    graph = KnowledgeGraph()

    graph.add_node(KnowledgeNode(id="A", name="A"))
    graph.add_node(KnowledgeNode(id="B", name="B"))
    graph.add_node(KnowledgeNode(id="C", name="C"))

    algorithm = ConnectedComponents(graph)

    components = algorithm.find()

    assert len(components) == 3

    sizes = sorted(len(c) for c in components)

    assert sizes == [1, 1, 1]


def test_component_contains_nodes() -> None:

    graph = create_graph()

    algorithm = ConnectedComponents(graph)

    components = algorithm.find()

    merged = set()

    for component in components:
        merged.update(component)

    assert merged == {"A", "B", "C", "D", "E"}