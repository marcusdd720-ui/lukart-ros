"""Tests for ISSUE helpers in LegalQuery (CASE-011)"""

from knowledge.legal_query import LegalQuery
from knowledge.types import EdgeType, NodeType


def test_legal_query_has_issue_methods() -> None:
    # only checks that methods exist and are callable
    assert hasattr(LegalQuery, "issues")
    assert hasattr(LegalQuery, "issues_raised_by")
    assert hasattr(LegalQuery, "facts_raising")
    assert hasattr(LegalQuery, "resolves")
    assert hasattr(LegalQuery, "resolved_by")


def test_edge_and_node_types_available() -> None:
    assert NodeType.ISSUE
    assert EdgeType.RAISES
    assert EdgeType.RESOLVES