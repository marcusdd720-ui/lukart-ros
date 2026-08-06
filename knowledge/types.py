"""
Knowledge Operating System (KOS)
File: knowledge/types.py
Version: 1.3.0
Sprint: CASE-012

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

    # Domain bridge (CASE-011 / CASE-012)
    ISSUE = auto()
    ARGUMENT = auto()


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

    # Domain bridge (CASE-011 / CASE-012)
    RAISES = auto()      # Fact → Issue
    RESOLVES = auto()    # Issue → Statute / Law / Decision
    ADVANCES = auto()    # Argument → Issue


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