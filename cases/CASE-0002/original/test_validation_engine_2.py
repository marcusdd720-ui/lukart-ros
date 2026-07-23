from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode
from knowledge.validation.validator import ValidationEngine


def test_validation_engine_valid_graph():

    graph = KnowledgeGraph()

    graph.add_node(KnowledgeNode(id="A", name="A"))
    graph.add_node(KnowledgeNode(id="B", name="B"))

    graph.add_edge(
        KnowledgeEdge(
            source="A",
            target="B",
        )
    )

    result = ValidationEngine().validate(graph)

    assert result.valid


def test_validation_engine_cycle():

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

    result = ValidationEngine().validate(graph)

    assert not result.valid

    assert any(
        issue.code == "GRAPH_CYCLE"
        for issue in result.issues
    )