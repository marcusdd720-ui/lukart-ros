"""
Knowledge Operating System (KOS)
File: knowledge/types.py
Version: 1.1
Sprint: K1.2

Core domain types for KOS / Knowledge Graph.
"""

from enum import StrEnum, auto


class NodeType(StrEnum):
    DOCUMENT = auto()
    PRINCIPLE = auto()
    EVIDENCE = auto()
    CASE = auto()
    ACTOR = auto()
    EVENT = auto()

    FACT = auto()
    CLAIM = auto()
    LAW = auto()
    DECISION = auto()

    # Legal knowledge (K1)
    STATUTE = auto()
    CASE_LAW = auto()


class EdgeType(StrEnum):
    """Types of relationships between nodes."""

    REFERENCES = auto()
    DEPENDS_ON = auto()
    SUPPORTS = auto()
    CONTRADICTS = auto()
    CONTAINS = auto()

    # Legal / argumentative (K1)
    INTERPRETS = auto()
    APPLIES = auto()
    RELIES_ON = auto()
    SUPPORTED_BY = auto()
    CITES = auto()


class Severity(StrEnum):
    """Validation severity levels."""

    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    FATAL = auto()


class DocumentStatus(StrEnum):
    """Lifecycle status of documents."""

    DRAFT = auto()
    REVIEW = auto()
    APPROVED = auto()
    ARCHIVED = auto()