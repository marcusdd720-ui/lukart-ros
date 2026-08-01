"""
Knowledge Operating System (KOS)
File: knowledge/types.py
Version: 1.0
Sprint: F-006
Status: Stable

Purpose:
Defines the core domain types used throughout the KOS.
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


class EdgeType(StrEnum):
    """Types of relationships between nodes."""

    REFERENCES = auto()
    DEPENDS_ON = auto()
    SUPPORTS = auto()
    CONTRADICTS = auto()
    CONTAINS = auto()


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
