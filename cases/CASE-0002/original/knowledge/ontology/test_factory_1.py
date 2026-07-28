"""
Tests for OntologyFactory.
"""

from knowledge.ontology.factory import OntologyFactory


def test_create_concept() -> None:
    concept = OntologyFactory.create_concept(
        name="Person",
        description="Human",
    )

    assert concept.name == "Person"
    assert concept.description == "Human"


def test_trim_concept_values() -> None:
    concept = OntologyFactory.create_concept(
        name="  Person  ",
        description="  Human  ",
    )

    assert concept.name == "Person"
    assert concept.description == "Human"


def test_create_relation() -> None:
    concept_a = OntologyFactory.create_concept(
        name="Animal",
    )

    concept_b = OntologyFactory.create_concept(
        name="Dog",
    )

    relation = OntologyFactory.create_relation(
        source=concept_a.id,
        target=concept_b.id,
        relation_type="IS_A",
    )

    assert relation.source == concept_a.id
    assert relation.target == concept_b.id
    assert relation.relation_type == "IS_A"
    assert relation.confidence == 1.0


def test_trim_relation_type() -> None:
    concept_a = OntologyFactory.create_concept(
        name="Animal",
    )

    concept_b = OntologyFactory.create_concept(
        name="Dog",
    )

    relation = OntologyFactory.create_relation(
        source=concept_a.id,
        target=concept_b.id,
        relation_type="  IS_A  ",
    )

    assert relation.relation_type == "IS_A"
