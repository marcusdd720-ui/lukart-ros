"""
Knowledge Operating System (KOS)
File: knowledge/node.py
Version: 1.0
Sprint: F-006
Status: Stable

Purpose:
Represents a node inside the Knowledge Graph.
"""

from dataclasses import dataclass, field
from uuid import uuid4

from knowledge.types import NodeType


@dataclass(slots=True)
class KnowledgeNode:
    """
    Represents a single node in the Knowledge Graph.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    type: NodeType = NodeType.DOCUMENT
    name: str = ""
    source: str = ""
    description: str = ""

    def __str__(self) -> str:
        return f"[{self.type}] {self.name} ({self.id})"
