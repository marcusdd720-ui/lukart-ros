from __future__ import annotations

from knowledge.ontology.memory_repository import MemoryOntologyRepository
from knowledge.ontology.service import OntologyService


def test_create_concept() -> None:
    repository = MemoryOntologyRepository()

    service = OntologyService(repository)

    report = service.create_concept(
        name="Person",
        description="Human",
    )

    assert report.is_valid

    concept = service.find_concept("Person")

    assert concept is not None
    assert concept.name == "Person"
    assert concept.description == "Human"


def test_create_invalid_concept() -> None:
    repository = MemoryOntologyRepository()

    service = OntologyService(repository)

    report = service.create_concept(
        name="",
    )

    assert not report.is_valid


def test_create_relation() -> None:
    repository = MemoryOntologyRepository()

    service = OntologyService(repository)

    service.create_concept(name="Person")
    service.create_concept(name="Employee")

    person = service.find_concept("Person")
    employee = service.find_concept("Employee")

    assert person is not None
    assert employee is not None

    report = service.create_relation(
        source=person.id,
        target=employee.id,
        relation_type="IS_A",
    )

    assert report.is_valid

    relations = list(service.relations())

    assert len(relations) == 1


def test_repository_is_used() -> None:
    repository = MemoryOntologyRepository()

    service = OntologyService(repository)

    service.create_concept(name="Document")

    assert repository.size() == 1


def test_find_unknown_concept() -> None:
    repository = MemoryOntologyRepository()

    service = OntologyService(repository)

    assert service.find_concept("Unknown") is None
