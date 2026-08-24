"""Validation of the persisted KnowledgeGraph wire format."""

from __future__ import annotations

from knowledge.serialization.exceptions import SchemaValidationError


class GraphSchemaValidator:
    """Validate the minimum, versioned graph envelope."""

    REQUIRED_ROOT_KEYS = {"schema_version", "nodes", "edges"}
    CURRENT_SCHEMA_VERSION = "1.0.0"

    def validate(self, data: dict) -> None:
        if not isinstance(data, dict):
            raise SchemaValidationError("Serialized graph must be a dictionary.")
        missing = self.REQUIRED_ROOT_KEYS - set(data.keys())
        if missing:
            raise SchemaValidationError(f"Missing keys: {sorted(missing)}")
        version = data["schema_version"]
        if not isinstance(version, str) or not version.strip():
            raise SchemaValidationError("'schema_version' must be a non-empty string.")
        if version != self.CURRENT_SCHEMA_VERSION:
            raise SchemaValidationError(
                f"Unsupported schema version: {version}; expected {self.CURRENT_SCHEMA_VERSION}."
            )
        if not isinstance(data["nodes"], list):
            raise SchemaValidationError("'nodes' must be a list.")
        if not isinstance(data["edges"], list):
            raise SchemaValidationError("'edges' must be a list.")
