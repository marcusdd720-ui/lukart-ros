"""Tests for ISSUE / RAISES / RESOLVES in types.py 1.2.0"""

from knowledge.types import NodeType, EdgeType


def test_node_type_issue_exists() -> None:
    assert NodeType.ISSUE
    assert "ISSUE" in NodeType.__members__


def test_edge_type_raises_and_resolves_exist() -> None:
    assert EdgeType.RAISES
    assert EdgeType.RESOLVES
    assert "RAISES" in EdgeType.__members__
    assert "RESOLVES" in EdgeType.__members__