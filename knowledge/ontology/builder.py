"""
Ontology Builder.

Fluent API for building ontology concepts.
"""

from __future__ import annotations

from .concept import OntologyConcept


class OntologyBuilder:
    """
    Fluent builder for OntologyConcept.
    """

    def __init__(self) -> None:
        self._concept = OntologyConcept(name="")

    def name(self, value: str) -> "OntologyBuilder":
        self._concept.name = value.strip()
        return self

    def description(self, value: str) -> "OntologyBuilder":
        self._concept.description = value.strip()
        return self

    def alias(self, value: str) -> "OntologyBuilder":
        self._concept.aliases.add(value)
        return self

    def property(self, key: str, value: object) -> "OntologyBuilder":
        self._concept.properties[key] = value
        return self

    def parent(self, parent_id) -> "OntologyBuilder":
        self._concept.parents.add(parent_id)
        return self

    def child(self, child_id) -> "OntologyBuilder":
        self._concept.children.add(child_id)
        return self

    def relation(self, relation_id) -> "OntologyBuilder":
        self._concept.relations.add(relation_id)
        return self

    def build(self) -> OntologyConcept:
        return self._concept