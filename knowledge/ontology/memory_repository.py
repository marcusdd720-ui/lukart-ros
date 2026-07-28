"""
In-memory implementation of OntologyRepository.

Useful for tests, prototypes and small knowledge bases.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from core.models.ids import EntityId

from .concept import OntologyConcept
from .relation import Relation
from .repository import OntologyRepository


class MemoryOntologyRepository(OntologyRepository):
    """
    Volatile in-memory ontology repository.

    Features
    --------
    - O(1) concept lookup by id
    - O(1) relation lookup by id
    - O(1) outgoing relation lookup
    - O(1) incoming relation lookup
    """

    def __init__(self) -> None:
        self._concepts: dict[EntityId, OntologyConcept] = {}
        self._relations: dict[EntityId, Relation] = {}

        self._outgoing_index: dict[EntityId, set[EntityId]] = defaultdict(set)
        self._incoming_index: dict[EntityId, set[EntityId]] = defaultdict(set)

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

        self._outgoing_index[relation.source].add(relation.id)
        self._incoming_index[relation.target].add(relation.id)

    def remove_relation(
        self,
        relation_id: EntityId,
    ) -> None:
        relation = self._relations.pop(relation_id, None)

        if relation is None:
            return

        self._outgoing_index[relation.source].discard(relation.id)
        self._incoming_index[relation.target].discard(relation.id)

        if not self._outgoing_index[relation.source]:
            del self._outgoing_index[relation.source]

        if not self._incoming_index[relation.target]:
            del self._incoming_index[relation.target]

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
        for relation_id in self._outgoing_index.get(source, ()):
            relation = self._relations.get(relation_id)

            if relation is not None:
                yield relation

    def incoming(
        self,
        target: EntityId,
    ) -> Iterable[Relation]:
        for relation_id in self._incoming_index.get(target, ()):
            relation = self._relations.get(relation_id)

            if relation is not None:
                yield relation

    # ------------------------------------------------------------------
    # General
    # ------------------------------------------------------------------

    def clear(self) -> None:
        self._concepts.clear()
        self._relations.clear()
        self._outgoing_index.clear()
        self._incoming_index.clear()

    def size(self) -> int:
        return len(self._concepts)

    def relation_count(self) -> int:
        return len(self._relations)

    def __len__(self) -> int:
        return self.size()
