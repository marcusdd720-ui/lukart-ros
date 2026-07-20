"""
Knowledge Operating System (KOS)

Sprint GRAPH-014

Serialization exceptions.
"""


class SchemaValidationError(ValueError):
    """Raised when serialized graph schema is invalid."""