"""
Knowledge Ontology Repository

Abstract repository defining the persistence contract
for ontology concepts and relations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from core.models.ids import EntityId

from .concept import OntologyConcept
from .relation import Relation


class OntologyRepository(ABC):
    """
    Repository interface for ontology storage.
    """

    # ------------------------------------------------------------------
    # Concepts
    # ------------------------------------------------------------------

    @abstractmethod
    def add_concept(self, concept: OntologyConcept) -> None: ...

    @abstractmethod
    def update_concept(self, concept: OntologyConcept) -> None: ...

    @abstractmethod
    def remove_concept(self, concept_id: EntityId) -> None: ...

    @abstractmethod
    def get_concept(
        self,
        concept_id: EntityId,
    ) -> OntologyConcept | None: ...

    @abstractmethod
    def find_by_name(
        self,
        name: str,
    ) -> OntologyConcept | None: ...

    @abstractmethod
    def list_concepts(self) -> Iterable[OntologyConcept]: ...

    # ------------------------------------------------------------------
    # Relations
    # ------------------------------------------------------------------

    @abstractmethod
    def add_relation(self, relation: Relation) -> None: ...

    @abstractmethod
    def remove_relation(
        self,
        relation_id: EntityId,
    ) -> None: ...

    @abstractmethod
    def get_relation(
        self,
        relation_id: EntityId,
    ) -> Relation | None: ...

    @abstractmethod
    def list_relations(self) -> Iterable[Relation]: ...

    @abstractmethod
    def outgoing(
        self,
        source: EntityId,
    ) -> Iterable[Relation]: ...

    @abstractmethod
    def incoming(
        self,
        target: EntityId,
    ) -> Iterable[Relation]: ...

    # ------------------------------------------------------------------
    # General
    # ------------------------------------------------------------------

    @abstractmethod
    def clear(self) -> None: ...

    @abstractmethod
    def size(self) -> int: ...
