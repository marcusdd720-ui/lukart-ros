"""Tests for Graph Integrity Gate."""

from knowledge.graph import KnowledgeGraph
from knowledge.graph_integrity import check_graph_integrity
from knowledge.models.case_workspace import open_ds_3960


def test_ds3960_integrity_pass() -> None:
    ws = open_ds_3960()
    report = check_graph_integrity(ws.graph, ws.case)
    print(report.report())
    assert report.ok


def test_empty_graph_ok() -> None:
    g = KnowledgeGraph()
    report = check_graph_integrity(g)
    assert report.ok