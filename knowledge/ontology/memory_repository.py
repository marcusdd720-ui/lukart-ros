"""
In-memory implementation of OntologyRepository.

Useful for tests, prototypes and small knowledge bases.
"""

from __future__ import annotations

from collections.abc import Iterable

from core.models.ids import EntityId

from .concept import OntologyConcept
from .relation import Relation
from .repository import OntologyRepository


class MemoryOntologyRepository(OntologyRepository):
    """
    Volatile in-memory ontology repository.
    """

    def __init__(self) -> None:
        self._concepts: dict[EntityId, OntologyConcept] = {}
        self._relations: dict[EntityId, Relation] = {}

    # ------------------------------------------------------------------
    # Concepts
    # ------------------------------------------------------------------

    def add_concept(self, concept: OntologyConcept) -> None:
        self._concepts[concept.id] = concept

    def update_concept(self, concept: OntologyConcept) -> None:
        self._concepts[concept.id] = concept

    def remove_concept(self, concept_id: EntityId) -> None:
        self._concepts.pop(concept_id, None)

    def get_concept(
        self,
        concept_id: EntityId,
    ) -> OntologyConcept | None:
        return self._concepts.get(concept_id)

    def find_by_name(
        self,
        name: str,
    ) -> OntologyConcept | None:
        lookup = name.casefold()

        for concept in self._concepts.values():
            if concept.name.casefold() == lookup:
                return concept

        return None

    def list_concepts(self) -> Iterable[OntologyConcept]:
        return self._concepts.values()

    # ------------------------------------------------------------------
    # Relations
    # ------------------------------------------------------------------

    def add_relation(self, relation: Relation) -> None:
        self._relations[relation.id] = relation

    def remove_relation(
        self,
        relation_id: EntityId,
    ) -> None:
        self._relations.pop(relation_id, None)

    def get_relation(
        self,
        relation_id: EntityId,
    ) -> Relation | None:
        return self._relations.get(relation_id)

    def list_relations(self) -> Iterable[Relation]:
        return self._relations.values()

    def outgoing(
        self,
        source: EntityId,
    ) -> Iterable[Relation]:
        return (
            relation
            for relation in self._relations.values()
            if relation.source == source
        )

    def incoming(
        self,
        target: EntityId,
    ) -> Iterable[Relation]:
        return (
            relation
            for relation in self._relations.values()
            if relation.target == target
        )

    # ------------------------------------------------------------------
    # General
    # ------------------------------------------------------------------

    def clear(self) -> None:
        self._concepts.clear()
        self._relations.clear()

    def size(self) -> int:
        return len(self._concepts)