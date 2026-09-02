"""Tests for project_legal_issue"""

from knowledge.graph import KnowledgeGraph
from knowledge.models.case import LegalIssue
from knowledge.node import KnowledgeNode
from knowledge.project_issue import project_legal_issue
from knowledge.types import EdgeType, NodeType


def test_project_creates_issue_node() -> None:
    g = KnowledgeGraph()
    issue = LegalIssue(
        question="Czy darowizna była skuteczna?",
        fact_ids=["dummy"],
    )
    node_id = project_legal_issue(g, issue)

    assert g.has_node(node_id)
    node = g.get_node(node_id)
    assert node is not None
    assert node.type == NodeType.ISSUE
    assert "darowizna" in node.name.lower()


def test_project_adds_raises_and_relies_on() -> None:
    g = KnowledgeGraph()

    fact = KnowledgeNode(id="fact:1", type=NodeType.FACT, name="Fact 1")
    fact.validate()
    g.add_node(fact)

    statute = KnowledgeNode(id="statute:kk:284:2", type=NodeType.STATUTE, name="284")
    statute.validate()
    g.add_node(statute)

    issue = LegalIssue(
        question="Czy zachodzi przywłaszczenie?",
        fact_ids=["dummy"],
    )
    issue_id = project_legal_issue(
        g,
        issue,
        fact_node_ids=["fact:1"],
        statute_node_ids=["statute:kk:284:2"],
    )

    raises = [e for e in g.edges if e.type == EdgeType.RAISES]
    relies_on = [e for e in g.edges if e.type == EdgeType.RELIES_ON]

    assert len(raises) == 1
    assert raises[0].source == "fact:1"
    assert raises[0].target == issue_id

    assert len(relies_on) == 1
    assert relies_on[0].source == issue_id
    assert relies_on[0].target == "statute:kk:284:2"
