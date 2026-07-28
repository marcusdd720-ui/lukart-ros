"""
Tests for OntologyValidator.
"""

from __future__ import annotations

from knowledge.ontology.concept import OntologyConcept
from knowledge.ontology.relation import Relation
from knowledge.ontology.validator import OntologyValidator


def test_valid_concept() -> None:
    validator = OntologyValidator()

    concept = OntologyConcept(
        name="Person",
    )

    report = validator.validate_concept(concept)

    assert report.is_valid


def test_empty_concept_name() -> None:
    validator = OntologyValidator()

    concept = OntologyConcept(
        name="",
    )

    report = validator.validate_concept(concept)

    assert not report.is_valid


def test_valid_relation() -> None:
    validator = OntologyValidator()

    source = OntologyConcept(name="Animal")
    target = OntologyConcept(name="Dog")

    relation = Relation(
        source=source.id,
        target=target.id,
        relation_type="IS_A",
    )

    report = validator.validate_relation(relation)

    assert report.is_valid


def test_self_relation_warning() -> None:
    validator = OntologyValidator()

    concept = OntologyConcept(
        name="Person",
    )

    relation = Relation(
        source=concept.id,
        target=concept.id,
        relation_type="RELATED_TO",
    )

    report = validator.validate_relation(relation)

    assert report.is_valid
    assert len(report.messages) == 1
    assert report.messages[0].code == "SELF_REFERENCE"


def test_invalid_confidence() -> None:
    validator = OntologyValidator()

    source = OntologyConcept(name="Animal")
    target = OntologyConcept(name="Dog")

    relation = Relation(
        source=source.id,
        target=target.id,
        relation_type="IS_A",
        confidence=2.0,
    )

    report = validator.validate_relation(relation)

    assert not report.is_valid


def test_negative_confidence() -> None:
    validator = OntologyValidator()

    source = OntologyConcept(name="Animal")
    target = OntologyConcept(name="Dog")

    relation = Relation(
        source=source.id,
        target=target.id,
        relation_type="IS_A",
        confidence=-0.5,
    )

    report = validator.validate_relation(relation)

    assert not report.is_valid
