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
from typing import Any, Literal, Protocol
from uuid import UUID

# ============================================================================
# Primitive aliases
# ============================================================================

type Timestamp = datetime

type JsonPrimitive = str | int | float | bool | None

type JsonValue = JsonPrimitive | list[JsonValue] | dict[str, JsonValue]

type Metadata = dict[str, JsonValue]
type Tags = set[str]
type Attributes = dict[str, JsonValue]
type Labels = dict[str, str]
type PathLike = str | Path
type Headers = Mapping[str, str]

# ============================================================================
# Confidence
# ============================================================================

type ConfidenceScore = float

# ============================================================================
# Hashes
# ============================================================================

type HashValue = str
type Checksum = str

# ============================================================================
# MIME
# ============================================================================

type MimeType = str
type Encoding = str

# ============================================================================
# Generic identifiers
# ============================================================================

type Identifier = UUID

# ============================================================================
# Generic dictionaries
# ============================================================================

type JsonDict = dict[str, JsonValue]
type ObjectDict = dict[str, Any]

# ============================================================================
# Status literals
# ============================================================================

type ProcessingStatus = Literal[
    "new",
    "queued",
    "processing",
    "completed",
    "failed",
]

type ValidationStatus = Literal[
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
