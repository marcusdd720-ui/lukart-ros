"""
Integration tests for the Ontology module.
"""

from __future__ import annotations

from knowledge.ontology.factory import OntologyFactory
from knowledge.ontology.memory_repository import MemoryOntologyRepository
from knowledge.ontology.service import OntologyService
from knowledge.ontology.validator import OntologyValidator


def create_service() -> OntologyService:
    repository = MemoryOntologyRepository()
    validator = OntologyValidator()

    return OntologyService(
        repository=repository,
        validator=validator,
    )


def test_full_concept_flow() -> None:
    service = create_service()

    report = service.create_concept(
        name="Person",
        description="Human being",
    )

    assert report.is_valid

    concept = service.find_by_name("Person")

    assert concept is not None
    assert concept.name == "Person"
    assert concept.description == "Human being"


def test_invalid_concept_is_not_saved() -> None:
    service = create_service()

    report = service.create_concept(
        name="",
        description="Invalid",
    )

    assert not report.is_valid

    assert service.find_by_name("") is None


def test_create_relation_between_concepts() -> None:
    service = create_service()

    service.create_concept(name="Animal")
    service.create_concept(name="Dog")

    animal = service.find_by_name("Animal")
    dog = service.find_by_name("Dog")

    assert animal is not None
    assert dog is not None

    report = service.create_relation(
        source=animal.id,
        target=dog.id,
        relation_type="IS_A",
    )

    assert report.is_valid


def test_repository_size_after_operations() -> None:
    service = create_service()

    service.create_concept(name="Animal")
    service.create_concept(name="Dog")
    service.create_concept(name="Cat")

    repository = service.repository

    assert repository.size() == 3


def test_factory_and_service_work_together() -> None:
    service = create_service()

    concept = OntologyFactory.create_concept(
        name="Vehicle",
        description="Transport",
    )

    report = service.add_concept(concept)

    assert report.is_valid

    loaded = service.find_by_name("Vehicle")

    assert loaded is not None
    assert loaded.name == "Vehicle"
