"""
Knowledge Operating System (KOS)

File: knowledge/relation.py
Version: 2.0
Sprint: F-012
Status: Stable
"""

from dataclasses import dataclass

from knowledge.relation_types import RelationType


@dataclass(slots=True)
class Relation:
    """Logical relation between two documents."""

    source: str

    target: str

    relation_type: RelationType

    confidence: float = 1.0

    evidence: str = ""

    def __str__(self):

        return (
            f"{self.source}"
            f" --[{self.relation_type.value}]--> "
            f"{self.target}"
        )