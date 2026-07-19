"""
Ontology command objects.

Commands represent requests that modify ontology state.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.models.ids import EntityId
from core.models.shared.metadata import Metadata


@dataclass(slots=True, frozen=True)
class CreateConceptCommand:
    """
    Create a new ontology concept.
    """

    name: str
    description: str = ""
    metadata: Metadata | None = None


@dataclass(slots=True, frozen=True)
class UpdateConceptCommand:
    """
    Update an existing concept.
    """

    concept_id: EntityId

    name: str | None = None

    description: str | None = None

    metadata: Metadata | None = None


@dataclass(slots=True, frozen=True)
class DeleteConceptCommand:
    """
    Remove concept from ontology.
    """

    concept_id: EntityId


@dataclass(slots=True, frozen=True)
class CreateRelationCommand:
    """
    Create ontology relation.
    """

    source: EntityId

    target: EntityId

    relation_type: str

    confidence: float = 1.0

    metadata: Metadata | None = None


@dataclass(slots=True, frozen=True)
class DeleteRelationCommand:
    """
    Delete ontology relation.
    """

    relation_id: EntityId