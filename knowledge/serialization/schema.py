"""
Knowledge Operating System (KOS)

Sprint GRAPH-014

Schema validation.
"""

from __future__ import annotations

from knowledge.serialization.exceptions import SchemaValidationError


class GraphSchemaValidator:
    """
    Validate serialized graph structure.
    """

    REQUIRED_ROOT_KEYS = {
        "nodes",
        "edges",
    }

    def validate(
        self,
        data: dict,
    ) -> None:

        if not isinstance(data, dict):
            raise SchemaValidationError("Serialized graph must be a dictionary.")

        missing = self.REQUIRED_ROOT_KEYS - set(data.keys())

        if missing:
            raise SchemaValidationError(f"Missing keys: {sorted(missing)}")

        if not isinstance(data["nodes"], list):
            raise SchemaValidationError("'nodes' must be a list.")

        if not isinstance(data["edges"], list):
            raise SchemaValidationError("'edges' must be a list.")
