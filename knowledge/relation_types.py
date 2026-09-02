"""
Knowledge Operating System (KOS)

File: knowledge/relation_types.py
Version: 2.0
Sprint: F-012
Status: Stable
"""

from enum import StrEnum


class RelationType(StrEnum):
    """Supported relation types."""

    REFERENCES = "references"
    DEPENDS_ON = "depends_on"
    IMPLEMENTS = "implements"
    EXTENDS = "extends"
    RELATED_TO = "related_to"
    USES = "uses"
    DEFINES = "defines"
    CONTAINS = "contains"
    CITES = "cites"