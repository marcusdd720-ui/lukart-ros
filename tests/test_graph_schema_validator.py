import pytest

from knowledge.serialization.exceptions import SchemaValidationError
from knowledge.serialization.schema import GraphSchemaValidator


def test_valid_schema():

    GraphSchemaValidator().validate(
        {
            "nodes": [],
            "edges": [],
        }
    )


def test_missing_nodes():

    with pytest.raises(SchemaValidationError):

        GraphSchemaValidator().validate(
            {
                "edges": [],
            }
        )


def test_missing_edges():

    with pytest.raises(SchemaValidationError):

        GraphSchemaValidator().validate(
            {
                "nodes": [],
            }
        )


def test_nodes_not_list():

    with pytest.raises(SchemaValidationError):

        GraphSchemaValidator().validate(
            {
                "nodes": {},
                "edges": [],
            }
        )


def test_edges_not_list():

    with pytest.raises(SchemaValidationError):

        GraphSchemaValidator().validate(
            {
                "nodes": [],
                "edges": {},
            }
        )