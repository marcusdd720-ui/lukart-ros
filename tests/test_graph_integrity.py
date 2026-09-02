"""Tests for Graph Integrity Gate."""

from knowledge.graph import KnowledgeGraph
from knowledge.graph_integrity import check_graph_integrity


def test_empty_graph_ok() -> None:
    graph = KnowledgeGraph()
    report = check_graph_integrity(graph)
    assert report.ok
