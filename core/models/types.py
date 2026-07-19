"""
KOS - Shared Type Definitions

This module contains common type aliases and protocols used across
the Knowledge Operating System.

The goal is to keep domain models independent from implementation
details while providing a single source of truth for shared types.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol, TypeAlias
from uuid import UUID

# ============================================================================
# Primitive aliases
# ============================================================================

Timestamp: TypeAlias = datetime

JsonPrimitive: TypeAlias = str | int | float | bool | None

JsonValue: TypeAlias = (
    JsonPrimitive
    | list["JsonValue"]
    | dict[str, "JsonValue"]
)

Metadata: TypeAlias = dict[str, JsonValue]

Tags: TypeAlias = set[str]

Attributes: TypeAlias = dict[str, JsonValue]

Labels: TypeAlias = dict[str, str]

PathLike: TypeAlias = str | Path

Headers: TypeAlias = Mapping[str, str]

# ============================================================================
# Confidence
# ============================================================================

ConfidenceScore: TypeAlias = float

# ============================================================================
# Hashes
# ============================================================================

HashValue: TypeAlias = str

Checksum: TypeAlias = str

# ============================================================================
# MIME
# ============================================================================

MimeType: TypeAlias = str

Encoding: TypeAlias = str

# ============================================================================
# Generic identifiers
# ============================================================================

Identifier: TypeAlias = UUID

# ============================================================================
# Generic dictionaries
# ============================================================================

JsonDict: TypeAlias = dict[str, JsonValue]

ObjectDict: TypeAlias = dict[str, Any]

# ============================================================================
# Status literals
# ============================================================================

ProcessingStatus: TypeAlias = Literal[
    "new",
    "queued",
    "processing",
    "completed",
    "failed",
]

ValidationStatus: TypeAlias = Literal[
    "unknown",
    "valid",
    "invalid",
]

# ============================================================================
# Protocols
# ============================================================================


class Identifiable(Protocol):
    """Object exposing UUID identifier."""

    id: UUID


class Timestamped(Protocol):
    """Object exposing creation timestamp."""

    created_at: datetime


class Named(Protocol):
    """Object exposing a human-readable name."""

    name: str


class Serializable(Protocol):
    """Protocol for serializable domain objects."""

    def to_dict(self) -> JsonDict:
        """Return object representation."""


# ============================================================================
# Constants
# ============================================================================

DEFAULT_ENCODING: Encoding = "utf-8"

UNKNOWN_MIME: MimeType = "application/octet-stream"