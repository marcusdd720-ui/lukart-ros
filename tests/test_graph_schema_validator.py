import pytest

from knowledge.serialization.exceptions import SchemaValidationError
from knowledge.serialization.schema import GraphSchemaValidator


def test_valid_schema() -> None:
    GraphSchemaValidator().validate(
        {"schema_version": "1.0.0", "nodes": [], "edges": []}
    )


def test_missing_schema_version() -> None:
    with pytest.raises(SchemaValidationError):
        GraphSchemaValidator().validate({"nodes": [], "edges": []})


def test_unsupported_schema_version() -> None:
    with pytest.raises(SchemaValidationError, match="Unsupported schema version"):
        GraphSchemaValidator().validate(
            {"schema_version": "9.9.9", "nodes": [], "edges": []}
        )


def test_missing_nodes() -> None:
    with pytest.raises(SchemaValidationError):
        GraphSchemaValidator().validate({"schema_version": "1.0.0", "edges": []})


def test_missing_edges() -> None:
    with pytest.raises(SchemaValidationError):
        GraphSchemaValidator().validate({"schema_version": "1.0.0", "nodes": []})


def test_nodes_not_list() -> None:
    with pytest.raises(SchemaValidationError):
        GraphSchemaValidator().validate(
            {"schema_version": "1.0.0", "nodes": {}, "edges": []}
        )


def test_edges_not_list() -> None:
    with pytest.raises(SchemaValidationError):
        GraphSchemaValidator().validate(
            {"schema_version": "1.0.0", "nodes": [], "edges": {}}
        )
