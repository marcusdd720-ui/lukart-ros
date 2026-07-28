"""
Tests for Ontology domain model.
"""

from knowledge.ontology.concept import OntologyConcept
from knowledge.ontology.relation import Relation


def test_ontology_models() -> None:
    parent = OntologyConcept(
        name="Animal",
    )

    child = OntologyConcept(
        name="Dog",
        parents={parent.id},
    )

    relation = Relation(
        source=parent.id,
        target=child.id,
        relation_type="IS_A",
    )

    assert parent.name == "Animal"

    assert child.name == "Dog"

    assert child.parents == {parent.id}

    assert relation.source == parent.id

    assert relation.target == child.id

    assert relation.relation_type == "IS_A"

    assert relation.confidence == 1.0
