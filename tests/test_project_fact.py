"""Tests for project_fact."""

from knowledge.graph import KnowledgeGraph
from knowledge.models.case import Fact, FactStatus
from knowledge.project_fact import fact_node_id, project_fact
from knowledge.types import NodeType


def test_fact_node_id_stable() -> None:
    assert fact_node_id("abc") == "fact:abc"
    assert fact_node_id("fact:abc") == "fact:abc"


def test_project_fact_creates_node() -> None:
    g = KnowledgeGraph()
    fact = Fact(statement="Umowa darowizny została sporządzona", status=FactStatus.SUPPORTED)
    nid = project_fact(g, fact)
    assert nid == f"fact:{fact.id}"
    assert g.has_node(nid)
    node = g.get_node(nid)
    assert node is not None
    assert node.type == NodeType.FACT


def test_project_fact_idempotent() -> None:
    g = KnowledgeGraph()
    fact = Fact(statement="Rejestracja pojazdu")
    a = project_fact(g, fact)
    b = project_fact(g, fact)
    assert a == b
    assert g.node_count() == 1
