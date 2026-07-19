"""
Ontology specific exceptions.
"""

from __future__ import annotations

from core.models.shared.exceptions import DomainError


class OntologyError(DomainError):
    """
    Base ontology exception.
    """

    code = "ONTOLOGY_ERROR"


class ConceptAlreadyExistsError(OntologyError):
    """
    Raised when concept already exists.
    """

    code = "CONCEPT_ALREADY_EXISTS"


class ConceptNotFoundError(OntologyError):
    """
    Raised when concept cannot be found.
    """

    code = "CONCEPT_NOT_FOUND"


class RelationAlreadyExistsError(OntologyError):
    """
    Raised when relation already exists.
    """

    code = "RELATION_ALREADY_EXISTS"


class RelationNotFoundError(OntologyError):
    """
    Raised when relation cannot be found.
    """

    code = "RELATION_NOT_FOUND"


class CircularTaxonomyError(OntologyError):
    """
    Raised when taxonomy cycle is detected.
    """

    code = "CIRCULAR_TAXONOMY"


class OntologyValidationError(OntologyError):
    """
    Raised when ontology validation fails.
    """

    code = "ONTOLOGY_VALIDATION_ERROR"