"""Tests for LawAgent ISSUE awareness (CASE-011)"""

from knowledge.graph import KnowledgeGraph
from scripts.law_agent import LawFinding, review_case_law_links


def test_review_returns_list() -> None:
    g = KnowledgeGraph()
    findings = review_case_law_links(g, "nonexistent-case")
    assert isinstance(findings, list)
    assert any(f.code == "LAW001" for f in findings)


def test_law_finding_structure() -> None:
    f = LawFinding("WARNING", "LAW010", "test")
    assert f.severity == "WARNING"
    assert f.code == "LAW010"