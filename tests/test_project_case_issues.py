"""Tests for project_case_issues"""

from knowledge.graph import KnowledgeGraph
from knowledge.models.case import Case, Fact, LegalIssue
from knowledge.node import KnowledgeNode
from knowledge.project_case_issues import project_case_issues
from knowledge.types import NodeType


def test_project_case_issues_empty() -> None:
    g = KnowledgeGraph()
    case = Case(title="Empty")
    result = project_case_issues(g, case)
    assert result == []


def test_project_case_issues_creates_nodes() -> None:
    g = KnowledgeGraph()
    case = Case(title="Test")

    fact = Fact(statement="Darowizna dokonana")
    case.add_fact(fact)

    issue = LegalIssue(
        question="Czy darowizna skuteczna?",
        fact_ids=[fact.id],
    )
    case.add_issue(issue)

    # map domain fact → fake graph fact node
    fact_node = KnowledgeNode(id="fact:graph1", type=NodeType.FACT, name="F1")
    fact_node.validate()
    g.add_node(fact_node)

    created = project_case_issues(
        g,
        case,
        fact_id_map={fact.id: "fact:graph1"},
    )

    assert len(created) == 1
    assert g.has_node(created[0])