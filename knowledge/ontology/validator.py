"""
Ontology validator.
"""

from __future__ import annotations

from .concept import OntologyConcept
from .relation import Relation
from .report import ValidationReport


class OntologyValidator:
    """
    Performs ontology validation.
    """

    def validate_concept(
        self,
        concept: OntologyConcept,
    ) -> ValidationReport:

        report = ValidationReport()

        if not concept.name.strip():
            report.add_error(
                "CONCEPT_NAME_EMPTY",
                "Concept name cannot be empty.",
            )

        if len(concept.name) > 256:
            report.add_error(
                "CONCEPT_NAME_TOO_LONG",
                "Concept name exceeds maximum length.",
            )

        if not concept.id:
            report.add_error(
                "CONCEPT_ID_MISSING",
                "Concept identifier missing.",
            )

        if not concept.aliases:
            report.add_info(
                "NO_ALIASES",
                "Concept has no aliases.",
            )

        return report

    def validate_relation(
        self,
        relation: Relation,
    ) -> ValidationReport:

        report = ValidationReport()

        if relation.source == relation.target:
            report.add_warning(
                "SELF_REFERENCE",
                "Relation points to itself.",
            )

        if relation.confidence < 0.0:
            report.add_error(
                "NEGATIVE_CONFIDENCE",
                "Confidence cannot be negative.",
            )

        if relation.confidence > 1.0:
            report.add_error(
                "CONFIDENCE_TOO_HIGH",
                "Confidence cannot exceed 1.0.",
            )

        if not relation.relation_type:
            report.add_error(
                "RELATION_TYPE_EMPTY",
                "Relation type missing.",
            )

        return report