"""
Knowledge Operating System (KOS)

File: knowledge/edge.py
Version: 1.0
Status: Stable
Sprint: F-006

Purpose:
Represents a relationship between two nodes
inside the Knowledge Graph.
"""

from dataclasses import dataclass, field
from uuid import uuid4

from knowledge.types import EdgeType


@dataclass(slots=True)
class KnowledgeEdge:
    """
    Represents a relationship between two nodes.
    """

    id: str = field(default_factory=lambda: str(uuid4()))

    source: str = ""
    target: str = ""

    type: EdgeType = EdgeType.REFERENCES

    description: str = ""

    def __str__(self) -> str:
        return (
            f"[{self.type}] "
            f"{self.source} -> {self.target}"
        )