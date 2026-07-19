"""
KOS - Value Object

Base class for immutable Value Objects.

Unlike Entities, Value Objects are identified
by their values, not by identity.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValueObject:
    """
    Base class for immutable Value Objects.

    Equality is value-based.
    """

    pass