"""
Ontology Application Service.
"""

from __future__ import annotations

from .factory import OntologyFactory
from .concept import OntologyConcept
from .relation import Relation
from .report import ValidationReport
from .repository import OntologyRepository
from .validator import OntologyValidator


class OntologyService:
    """
    High-level API for ontology operations.

    Coordinates validation, creation and persistence.
    """

    def __init__(
        self,
        repository: OntologyRepository,
        validator: OntologyValidator | None = None,
    ) -> None:

        self._repository = repository
        self._validator = validator or OntologyValidator()

    @property
    def repository(self) -> OntologyRepository:
        """
        Read-only access to repository.
        """
        return self._repository

    def create_concept(
        self,
        **kwargs,
    ) -> ValidationReport:

        concept = OntologyFactory.create_concept(**kwargs)

        return self.add_concept(concept)

    def add_concept(
        self,
        concept: OntologyConcept,
    ) -> ValidationReport:

        report = self._validator.validate_concept(concept)

        if report.is_valid:
            self._repository.add_concept(concept)

        return report

    def create_relation(
        self,
        **kwargs,
    ) -> ValidationReport:

        relation = OntologyFactory.create_relation(**kwargs)

        return self.add_relation(relation)

    def add_relation(
        self,
        relation: Relation,
    ) -> ValidationReport:

        report = self._validator.validate_relation(relation)

        if report.is_valid:
            self._repository.add_relation(relation)

        return report

    def get_concept(self, concept_id):
        return self._repository.get_concept(concept_id)

    def get_relation(self, relation_id):
        return self._repository.get_relation(relation_id)

    def find_concept(self, name: str):
        return self._repository.find_by_name(name)

    def find_by_name(self, name: str):
        """
        Alias for repository lookup.
        """
        return self.find_concept(name)

    def concepts(self):
        return self._repository.list_concepts()

    def relations(self):
        return self._repository.list_relations()