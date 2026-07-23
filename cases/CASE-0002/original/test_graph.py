"""
Knowledge Operating System (KOS)

File: tests/test_graph.py
Version: 2.2
Sprint: GRAPH-016

Unit tests for KnowledgeGraph.
"""

from __future__ import annotations

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode


def create_node(node_id: str) -> KnowledgeNode:
    """Create test node."""

    return KnowledgeNode(id=node_id)


def create_edge(
    source: str,
    target: str,
) -> KnowledgeEdge:
    """Create test edge."""

    return KnowledgeEdge(
        source=source,
        target=target,
    )


def test_add_node() -> None:
    graph = KnowledgeGraph()

    node = create_node("A")

    graph.add_node(node)

    assert graph.node_count() == 1
    assert graph.has_node("A")
    assert graph.get_node("A") is node


def test_contains_node() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))

    assert graph.contains_node("A")
    assert not graph.contains_node("B")


def test_add_edge() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))
    graph.add_node(create_node("B"))

    graph.add_edge(
        create_edge("A", "B")
    )

    assert graph.edge_count() == 1
    assert graph.contains_edge("A", "B")


def test_add_edge_unknown_source() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("B"))

    try:
        graph.add_edge(
            create_edge("A", "B")
        )
    except KeyError:
        pass
    else:
        assert False


def test_add_edge_unknown_target() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))

    try:
        graph.add_edge(
            create_edge("A", "B")
        )
    except KeyError:
        pass
    else:
        assert False


def test_remove_edge() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))
    graph.add_node(create_node("B"))

    graph.add_edge(
        create_edge("A", "B")
    )

    assert graph.remove_edge("A", "B")
    assert graph.edge_count() == 0


def test_remove_missing_edge() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))
    graph.add_node(create_node("B"))

    assert graph.remove_edge("A", "B") is False

def test_neighbors() -> None:
    
    graph = KnowledgeGraph()
    node_a = create_node("A")
    node_b = create_node("B")
    node_c = create_node("C")

    graph.add_node(node_a)
    graph.add_node(node_b)
    graph.add_node(node_c)

    graph.add_edge(create_edge("A", "B"))
    graph.add_edge(create_edge("A", "C"))

    neighbors = graph.neighbors("A")

    assert len(neighbors) == 2
    assert node_b in neighbors
    assert node_c in neighbors


def test_successors() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))
    graph.add_node(create_node("B"))
    graph.add_node(create_node("C"))

    graph.add_edge(create_edge("A", "B"))
    graph.add_edge(create_edge("A", "C"))

    successors = graph.successors("A")

    assert len(successors) == 2


def test_predecessors() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))
    graph.add_node(create_node("B"))
    graph.add_node(create_node("C"))

    graph.add_edge(create_edge("A", "C"))
    graph.add_edge(create_edge("B", "C"))

    predecessors = graph.predecessors("C")

    assert len(predecessors) == 2


def test_degree() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))
    graph.add_node(create_node("B"))
    graph.add_node(create_node("C"))

    graph.add_edge(create_edge("A", "B"))
    graph.add_edge(create_edge("C", "B"))

    assert graph.degree("B") == 2
    assert graph.in_degree("B") == 2
    assert graph.out_degree("B") == 0


def test_has_path_direct() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))
    graph.add_node(create_node("B"))

    graph.add_edge(create_edge("A", "B"))

    assert graph.has_path("A", "B")


def test_has_path_indirect() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))
    graph.add_node(create_node("B"))
    graph.add_node(create_node("C"))

    graph.add_edge(create_edge("A", "B"))
    graph.add_edge(create_edge("B", "C"))

    assert graph.has_path("A", "C")


def test_has_path_missing() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))
    graph.add_node(create_node("B"))

    assert graph.has_path("A", "A")

def test_validate_integrity() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))
    graph.add_node(create_node("B"))

    graph.add_edge(create_edge("A", "B"))

    errors = graph.validate_integrity()

    assert errors == []
    assert graph.is_valid()


def test_remove_node_removes_edges() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))
    graph.add_node(create_node("B"))

    graph.add_edge(create_edge("A", "B"))

    graph.remove_node("A")

    assert not graph.has_node("A")
    assert graph.edge_count() == 0


def test_statistics() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))
    graph.add_node(create_node("B"))
    graph.add_node(create_node("C"))

    graph.add_edge(create_edge("A", "B"))

    stats = graph.statistics()

    assert stats["nodes"] == 3
    assert stats["edges"] == 1
    assert stats["connected_nodes"] == 2
    assert stats["isolated_nodes"] == 1


def test_copy() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))
    graph.add_node(create_node("B"))

    graph.add_edge(create_edge("A", "B"))

    copied = graph.copy()

    assert copied is not graph
    assert copied.nodes == graph.nodes
    assert copied.edges == graph.edges


def test_clear() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))
    graph.add_node(create_node("B"))

    graph.add_edge(create_edge("A", "B"))

    graph.clear()

    assert graph.node_count() == 0
    assert graph.edge_count() == 0


def test_len() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))
    graph.add_node(create_node("B"))

    assert len(graph) == 2


def test_contains_operator() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))

    assert "A" in graph
    assert "B" not in graph


def test_iter() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))
    graph.add_node(create_node("B"))

    ids = {node.id for node in graph}

    assert ids == {"A", "B"}


def test_str_and_repr() -> None:
    graph = KnowledgeGraph()

    graph.add_node(create_node("A"))

    text = str(graph)
    debug = repr(graph)

    assert "KnowledgeGraph" in text
    assert "nodes=1" in text

    assert "KnowledgeGraph" in debug
    assert "nodes=1" in debug
