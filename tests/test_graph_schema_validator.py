import pytest

from knowledge.serialization.exceptions import SchemaValidationError
from knowledge.serialization.schema import GraphSchemaValidator


def test_valid_schema():
    GraphSchemaValidator().validate(
        {"schema_version": "1.0.0", "nodes": [], "edges": []}
    )


def test_missing_schema_version():
    with pytest.raises(SchemaValidationError):
        GraphSchemaValidator().validate({"nodes": [], "edges": []})


def test_missing_nodes():
    with pytest.raises(SchemaValidationError):
        GraphSchemaValidator().validate({"schema_version": "1.0.0", "edges": []})


def test_missing_edges():
    with pytest.raises(SchemaValidationError):
        GraphSchemaValidator().validate({"schema_version": "1.0.0", "nodes": []})


def test_nodes_not_list():
    with pytest.raises(SchemaValidationError):
        GraphSchemaValidator().validate(
            {"schema_version": "1.0.0", "nodes": {}, "edges": []}
        )


def test_edges_not_list():
    with pytest.raises(SchemaValidationError):
        GraphSchemaValidator().validate(
            {"schema_version": "1.0.0", "nodes": [], "edges": {}}
        )
