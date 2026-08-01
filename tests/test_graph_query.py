"""Tests for knowledge.query.GraphQuery."""

from __future__ import annotations

import pytest

from knowledge.edge import KnowledgeEdge
from knowledge.graph import KnowledgeGraph
from knowledge.node import KnowledgeNode
from knowledge.query import GraphQuery
from knowledge.types import EdgeType, NodeType


def _sample_graph() -> KnowledgeGraph:
    graph = KnowledgeGraph()

    graph.add_node(
        KnowledgeNode(
            id="doc-1",
            name="Skarga",
            type=NodeType.DOCUMENT,
            status="ACTIVE",
            confidence=0.9,
            tags={"court", "primary"},
            metadata={"case": "II-Kp-459"},
        )
    )
    graph.add_node(
        KnowledgeNode(
            id="fact-1",
            name="Fakt A",
            type=NodeType.FACT,
            status="ACTIVE",
            confidence=0.8,
            tags={"evidence"},
        )
    )
    graph.add_node(
        KnowledgeNode(
            id="law-1",
            name="Art. 16 kpk",
            type=NodeType.LAW,
            status="ACTIVE",
            confidence=1.0,
        )
    )
    graph.add_node(
        KnowledgeNode(
            id="orphan-1",
            name="Osierocony",
            type=NodeType.CLAIM,
            status="DRAFT",
            confidence=0.5,
        )
    )

    graph.add_edge(
        KnowledgeEdge(
            id="e1",
            source="doc-1",
            target="fact-1",
            type=EdgeType.CONTAINS,
        )
    )
    graph.add_edge(
        KnowledgeEdge(
            id="e2",
            source="fact-1",
            target="law-1",
            type=EdgeType.REFERENCES,
        )
    )
    return graph


@pytest.fixture
def query() -> GraphQuery:
    return GraphQuery(_sample_graph())


def test_get_and_exists(query: GraphQuery) -> None:
    assert query.exists("doc-1") is True
    assert query.exists("missing") is False
    assert query.get("doc-1") is not None
    assert query.get("missing") is None


def test_require_raises(query: GraphQuery) -> None:
    with pytest.raises(KeyError):
        query.require("missing")


def test_find_by_name_and_type(query: GraphQuery) -> None:
    by_name = query.find_by_name("Skarga")
    assert len(by_name) == 1
    assert by_name[0].id == "doc-1"

    facts = query.find_by_type(NodeType.FACT)
    assert len(facts) == 1
    assert facts[0].id == "fact-1"

    facts_str = query.find_by_type("FACT")
    assert len(facts_str) == 1


def test_find_by_tag_and_status(query: GraphQuery) -> None:
    tagged = query.find_by_tag("court")
    assert len(tagged) == 1
    assert tagged[0].id == "doc-1"

    drafts = query.find_by_status("DRAFT")
    assert len(drafts) == 1
    assert drafts[0].id == "orphan-1"


def test_search_filters(query: GraphQuery) -> None:
    result = query.search(
        node_type=NodeType.DOCUMENT,
        tag="primary",
        confidence_min=0.85,
        metadata_key="case",
        metadata_value="II-Kp-459",
    )
    assert len(result) == 1
    assert result[0].id == "doc-1"

    empty = query.search(name_contains="zzz-not-found")
    assert empty == []


def test_first_one_limit_sort(query: GraphQuery) -> None:
    laws = query.find_by_type(NodeType.LAW)
    assert query.one(laws).id == "law-1"

    with pytest.raises(ValueError):
        query.one(query.find_by_type(NodeType.DOCUMENT) + laws)

    ordered = query.sort(query.graph.nodes.values(), key="name")
    assert ordered[0].name <= ordered[-1].name

    limited = query.limit(ordered, 2)
    assert len(limited) == 2


def test_neighbours_and_related(query: GraphQuery) -> None:
    succ = query.successors("doc-1")
    assert {n.id for n in succ} == {"fact-1"}

    pred = query.predecessors("law-1")
    assert {n.id for n in pred} == {"fact-1"}

    related = query.related("fact-1", direction="both")
    assert {n.id for n in related} == {"doc-1", "law-1"}


def test_path_and_descendants(query: GraphQuery) -> None:
    assert query.has_path("doc-1", "law-1") is True
    path = query.shortest_path("doc-1", "law-1")
    assert path == ["doc-1", "fact-1", "law-1"]

    desc = query.descendants("doc-1")
    assert {n.id for n in desc} == {"fact-1", "law-1"}

    anc = query.ancestors("law-1")
    assert {n.id for n in anc} == {"fact-1", "doc-1"}


def test_connected_component_and_isolated(query: GraphQuery) -> None:
    component = query.connected_component("doc-1")
    ids = {n.id for n in component}
    assert "doc-1" in ids
    assert "fact-1" in ids
    assert "law-1" in ids

    isolated = query.isolated()
    assert any(n.id == "orphan-1" for n in isolated)


def test_summary_and_refresh(query: GraphQuery) -> None:
    summary = query.summary()
    assert summary["nodes"] == 4
    assert summary["edges"] == 2
    assert "DOCUMENT" in summary["by_type"]

    query.graph.add_node(
        KnowledgeNode(id="x-1", name="Extra", type=NodeType.EVENT)
    )
    query.refresh()
    assert query.exists("x-1")
    assert query.count_nodes(NodeType.EVENT) == 1