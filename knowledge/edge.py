"""
Knowledge Operating System (KOS)

File: knowledge/edge.py
Version: 1.1
Status: Stable
Sprint: GRAPH-018 / CASE-012

Purpose:
Represents a relationship between two nodes inside the Knowledge Graph.
"""

from dataclasses import dataclass, field
from uuid import uuid4

from knowledge.types import EdgeType


@dataclass(slots=True)
class KnowledgeEdge:
    """Represents a relationship between two nodes."""

    id: str = field(default_factory=lambda: str(uuid4()))
    source: str = ""
    target: str = ""
    type: EdgeType = EdgeType.REFERENCES
    description: str = ""
    confidence: float = 1.0

    def validate(self) -> None:
        """Validate basic edge invariants."""
        if not self.source:
            raise ValueError("KnowledgeEdge.source must not be empty")
        if not self.target:
            raise ValueError("KnowledgeEdge.target must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("KnowledgeEdge.confidence must be between 0 and 1")

    def __str__(self) -> str:
        return f"[{self.type}] {self.source} -> {self.target}"
