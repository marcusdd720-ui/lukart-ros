"""
KOS Global Enumerations.

Shared enumerations used across the entire Knowledge Operating System.
"""

from __future__ import annotations

from enum import Enum, StrEnum


class LifecycleStatus(StrEnum):
    """
    Lifecycle state of a domain entity.
    """

    NEW = "new"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ProcessingStatus(StrEnum):
    """
    Processing pipeline status.
    """

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ValidationStatus(StrEnum):
    """
    Validation result.
    """

    UNKNOWN = "unknown"
    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"


class TruthStatus(StrEnum):
    """
    Truth assessment of extracted knowledge.
    """

    UNKNOWN = "unknown"
    CLAIMED = "claimed"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    REJECTED = "rejected"


class ConfidenceLevel(Enum):
    """
    Confidence buckets.
    """

    VERY_LOW = 0.20
    LOW = 0.40
    MEDIUM = 0.60
    HIGH = 0.80
    VERY_HIGH = 0.95


class Severity(StrEnum):
    """
    Severity of findings.
    """

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class KnowledgeType(StrEnum):
    """
    Main ontology objects.
    """

    FACT = "fact"
    CLAIM = "claim"
    EVIDENCE = "evidence"
    DECISION = "decision"
    LAW = "law"
    PERSON = "person"
    ORGANIZATION = "organization"
    DOCUMENT = "document"
    EVENT = "event"
    ARTIFACT = "artifact"


class RelationshipType(StrEnum):
    """
    Relations inside Knowledge Graph.
    """

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    REFERENCES = "references"
    DERIVES_FROM = "derives_from"
    CREATED_BY = "created_by"
    BELONGS_TO = "belongs_to"
    PART_OF = "part_of"
    RELATED_TO = "related_to"


class SourceType(StrEnum):
    """
    Origin of information.
    """

    USER = "user"
    DOCUMENT = "document"
    OCR = "ocr"
    EMAIL = "email"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DATABASE = "database"
    API = "api"
    AI = "ai"


class EventType(StrEnum):
    """
    Domain event category.
    """

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    VALIDATED = "validated"
    IMPORTED = "imported"
    EXPORTED = "exported"
