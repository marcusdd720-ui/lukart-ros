"""
Ontology Factory.

Responsible for creating ontology domain objects.
"""

from __future__ import annotations

from knowledge.ontology.concept import OntologyConcept
from knowledge.ontology.relation import Relation


class OntologyFactory:
    """
    Factory responsible for creating ontology objects.
    """

    @staticmethod
    def create_concept(
        *,
        name: str,
        description: str = "",
    ) -> OntologyConcept:
        """
        Create ontology concept.
        """

        return OntologyConcept(
            name=name.strip(),
            description=description.strip(),
        )

    @staticmethod
    def create_relation(
        *,
        source,
        target,
        relation_type: str,
        confidence: float = 1.0,
    ) -> Relation:
        """
        Create ontology relation.
        """

        return Relation(
            source=source,
            target=target,
            relation_type=relation_type.strip(),
            confidence=confidence,
        )