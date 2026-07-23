"""
Tests for OntologyBuilder.
"""

from __future__ import annotations

from knowledge.ontology.builder import OntologyBuilder


def test_build_concept() -> None:
    concept = (
        OntologyBuilder()
        .name("Person")
        .description("Human being")
        .build()
    )

    assert concept.name == "Person"
    assert concept.description == "Human being"


def test_add_alias() -> None:
    concept = (
        OntologyBuilder()
        .name("Person")
        .alias("Human")
        .build()
    )

    assert "Human" in concept.aliases


def test_add_property() -> None:
    concept = (
        OntologyBuilder()
        .name("Person")
        .property("age", "int")
        .build()
    )

    assert concept.properties["age"] == "int"


def test_add_parent() -> None:
    parent = OntologyBuilder().name("Animal").build()

    child = (
        OntologyBuilder()
        .name("Dog")
        .parent(parent.id)
        .build()
    )

    assert parent.id in child.parents


def test_add_child() -> None:
    child = OntologyBuilder().name("Dog").build()

    parent = (
        OntologyBuilder()
        .name("Animal")
        .child(child.id)
        .build()
    )

    assert child.id in parent.children


def test_add_relation() -> None:
    relation_id = object()

    concept = (
        OntologyBuilder()
        .name("Person")
        .relation(relation_id)
        .build()
    )

    assert relation_id in concept.relations


def test_trim_name() -> None:
    concept = (
        OntologyBuilder()
        .name("   Person   ")
        .build()
    )

    assert concept.name == "Person"