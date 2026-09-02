from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.relation_layer import RelationLayer, RelationLayerError
from knowledge.node import KnowledgeNode
from knowledge.types import EdgeType, NodeType


def _graph() -> KnowledgeGraph:
    graph = KnowledgeGraph()
    graph.add_node(KnowledgeNode(id="a", type=NodeType.FACT, name="A"))
    graph.add_node(KnowledgeNode(id="b", type=NodeType.ISSUE, name="B"))
    return graph


def test_add_relation_validates_and_inserts_typed_edge() -> None:
    layer = RelationLayer(_graph())

    edge = layer.add("a", "b", EdgeType.RAISES, description="raises issue", confidence=0.8)

    assert edge.source == "a"
    assert edge.target == "b"
    assert edge.type == EdgeType.RAISES
    assert edge.description == "raises issue"
    assert edge.confidence == 0.8
    assert layer.has("a", "b", EdgeType.RAISES)


def test_ensure_is_idempotent_for_same_typed_relation() -> None:
    graph = _graph()
    layer = RelationLayer(graph)
    first = layer.add("a", "b", EdgeType.RAISES)
    second = layer.add("a", "b", EdgeType.RAISES, description="later")

    assert second is first
    assert graph.edge_count() == 1


def test_same_endpoints_allow_different_relation_types() -> None:
    graph = _graph()
    layer = RelationLayer(graph)

    raises = layer.add("a", "b", EdgeType.RAISES)
    references = layer.add("a", "b", EdgeType.REFERENCES)

    assert raises is not references
    assert graph.edge_count() == 2
    assert layer.has("a", "b", EdgeType.RAISES)
    assert layer.has("a", "b", EdgeType.REFERENCES)


def test_unknown_source_is_rejected() -> None:
    layer = RelationLayer(_graph())

    try:
        layer.add("missing", "b", EdgeType.RAISES)
    except RelationLayerError as exc:
        assert str(exc) == "Unknown relation source: missing"
    else:
        raise AssertionError("expected RelationLayerError")


def test_unknown_target_is_rejected() -> None:
    layer = RelationLayer(_graph())

    try:
        layer.add("a", "missing", EdgeType.RAISES)
    except RelationLayerError as exc:
        assert str(exc) == "Unknown relation target: missing"
    else:
        raise AssertionError("expected RelationLayerError")


def test_invalid_edge_is_rejected_by_relation_layer() -> None:
    layer = RelationLayer(_graph())
    invalid = KnowledgeEdge(source="a", target="b", type=EdgeType.RAISES, confidence=1.1)

    try:
        layer.ensure(invalid)
    except RelationLayerError as exc:
        assert "confidence must be between 0 and 1" in str(exc)
    else:
        raise AssertionError("expected RelationLayerError")


def test_get_and_outgoing_preserve_typed_relations() -> None:
    graph = _graph()
    layer = RelationLayer(graph)
    layer.add("a", "b", EdgeType.RAISES)
    layer.add("a", "b", EdgeType.REFERENCES)

    raises = layer.get("a", "b", EdgeType.RAISES)
    outgoing = layer.outgoing("a")
    typed = layer.outgoing("a", EdgeType.REFERENCES)

    assert raises is not None
    assert len(outgoing) == 2
    assert len(typed) == 1
    assert typed[0].type == EdgeType.REFERENCES
