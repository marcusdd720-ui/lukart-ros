"""
Tests for MemoryOntologyRepository.
"""

from __future__ import annotations

import pytest

from knowledge.ontology.concept import OntologyConcept
from knowledge.ontology.memory_repository import MemoryOntologyRepository
from knowledge.ontology.relation import Relation


@pytest.fixture
def repository() -> MemoryOntologyRepository:
    return MemoryOntologyRepository()


def test_repository_initially_empty(
    repository: MemoryOntologyRepository,
) -> None:
    assert repository.size() == 0


def test_create_and_get_concept(
    repository: MemoryOntologyRepository,
) -> None:
    concept = OntologyConcept(
        name="Person",
    )

    repository.add_concept(concept)

    stored = repository.get_concept(concept.id)

    assert stored is not None
    assert stored.id == concept.id
    assert stored.name == "Person"


def test_repository_size_after_insert(
    repository: MemoryOntologyRepository,
) -> None:
    repository.add_concept(
        OntologyConcept(name="A"),
    )

    repository.add_concept(
        OntologyConcept(name="B"),
    )

    assert repository.size() == 2


def test_remove_concept(
    repository: MemoryOntologyRepository,
) -> None:
    concept = OntologyConcept(
        name="Person",
    )

    repository.add_concept(concept)

    repository.remove_concept(concept.id)

    assert repository.get_concept(concept.id) is None

    assert repository.size() == 0


def test_clear_repository(
    repository: MemoryOntologyRepository,
) -> None:
    repository.add_concept(
        OntologyConcept(name="A"),
    )

    repository.add_concept(
        OntologyConcept(name="B"),
    )

    repository.clear()

    assert repository.size() == 0


def test_add_relation(
    repository: MemoryOntologyRepository,
) -> None:
    parent = OntologyConcept(name="Animal")

    child = OntologyConcept(
        name="Dog",
    )

    repository.add_concept(parent)
    repository.add_concept(child)

    relation = Relation(
        source=parent.id,
        target=child.id,
        relation_type="IS_A",
    )

    repository.add_relation(relation)

    stored = repository.get_relation(
        relation.id,
    )

    assert stored is relation
