"""
Knowledge Operating System (KOS)
File: knowledge/node.py
Version: 1.1
Sprint: GRAPH-018 / CASE-012
Status: Stable

Purpose:
Represents a node inside the Knowledge Graph.
"""

from dataclasses import dataclass, field
from uuid import uuid4

from knowledge.types import NodeType


@dataclass(slots=True)
class KnowledgeNode:
    """Represents a single node in the Knowledge Graph."""

    id: str = field(default_factory=lambda: str(uuid4()))
    type: NodeType = NodeType.DOCUMENT
    name: str = ""
    source: str = ""
    description: str = ""
    status: str = ""
    confidence: float = 1.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        """Validate basic node invariants."""
        if not self.id:
            raise ValueError("KnowledgeNode.id must not be empty")
        if not self.name:
            raise ValueError("KnowledgeNode.name must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("KnowledgeNode.confidence must be between 0 and 1")

    def __str__(self) -> str:
        return f"[{self.type}] {self.name} ({self.id})"
