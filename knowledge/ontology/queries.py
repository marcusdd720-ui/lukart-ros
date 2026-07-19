"""
Ontology query objects.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.models.ids import EntityId


@dataclass(slots=True, frozen=True)
class GetConceptQuery:
    concept_id: EntityId


@dataclass(slots=True, frozen=True)
class FindConceptByNameQuery:
    name: str


@dataclass(slots=True, frozen=True)
class ListConceptsQuery:
    pass


@dataclass(slots=True, frozen=True)
class ListRelationsQuery:
    pass