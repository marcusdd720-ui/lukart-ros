"""Canonical JSON-Schema execution for CASE-TESTY profile reports.

The report contract lives in ``schemas/case_test_report.schema.json``.  This
module intentionally contains no report field manifest.  It executes the
schema keywords used by that canonical contract and fails closed when the
schema starts using a keyword this executor does not understand.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPORT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "schemas" / "case_test_report.schema.json"
)
_SUPPORTED_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

_SUPPORTED_KEYWORDS = {
    "$schema",
    "$id",
    "title",
    "type",
    "additionalProperties",
    "required",
    "properties",
    "const",
    "pattern",
    "enum",
    "minLength",
    "minItems",
    "items",
    "uniqueItems",
}
_SUPPORTED_TYPES = {"object", "array", "string", "boolean", "integer", "number", "null"}


class ReportSchemaError(RuntimeError):
    """Raised when the canonical schema or a report violates the contract."""


class StrictJsonError(ValueError):
    """Raised when JSON text uses ambiguous or non-standard syntax."""


def _strict_object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJsonError(f"duplicate object key: {key}")
        result[key] = value
    return result


def _reject_non_json_constant(value: str) -> object:
    raise StrictJsonError(f"non-JSON numeric constant: {value}")


def strict_json_loads(text: str) -> object:
    """Parse standards-compliant JSON without silently collapsing duplicate keys."""

    return json.loads(
        text,
        object_pairs_hook=_strict_object_pairs,
        parse_constant=_reject_non_json_constant,
    )


def _schema_error(path: str, message: str) -> ReportSchemaError:
    return ReportSchemaError(f"invalid canonical report schema at {path}: {message}")


def _ensure_non_negative_integer(value: object, *, path: str, keyword: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _schema_error(path, f"{keyword} must be a non-negative integer")


def _validate_schema_definition(schema: object, *, path: str = "$") -> dict[str, object]:
    if not isinstance(schema, dict):
        raise _schema_error(path, "schema node must be an object")

    unknown = sorted(set(schema) - _SUPPORTED_KEYWORDS)
    if unknown:
        raise _schema_error(path, f"unsupported keyword(s): {', '.join(unknown)}")

    for keyword in ("$schema", "$id", "title", "pattern"):
        if keyword in schema and not isinstance(schema[keyword], str):
            raise _schema_error(path, f"{keyword} must be a string")

    if "pattern" in schema:
        try:
            re.compile(str(schema["pattern"]))
        except re.error as exc:
            raise _schema_error(path, f"invalid pattern: {exc}") from exc

    if "type" in schema:
        type_value = schema["type"]
        if isinstance(type_value, str):
            types = [type_value]
        elif isinstance(type_value, list) and type_value and all(
            isinstance(item, str) for item in type_value
        ):
            types = type_value
        else:
            raise _schema_error(path, "type must be a string or a non-empty string array")
        unsupported_types = sorted(set(types) - _SUPPORTED_TYPES)
        if unsupported_types:
            raise _schema_error(path, f"unsupported JSON type(s): {', '.join(unsupported_types)}")

    if "required" in schema:
        required = schema["required"]
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            raise _schema_error(path, "required must be a string array")
        if len(required) != len(set(required)):
            raise _schema_error(path, "required entries must be unique")

    if "enum" in schema:
        enum = schema["enum"]
        if not isinstance(enum, list) or not enum:
            raise _schema_error(path, "enum must be a non-empty array")

    if "minLength" in schema:
        _ensure_non_negative_integer(schema["minLength"], path=path, keyword="minLength")
    if "minItems" in schema:
        _ensure_non_negative_integer(schema["minItems"], path=path, keyword="minItems")

    if "uniqueItems" in schema and not isinstance(schema["uniqueItems"], bool):
        raise _schema_error(path, "uniqueItems must be boolean")

    if "additionalProperties" in schema:
        additional = schema["additionalProperties"]
        if not isinstance(additional, (bool, dict)):
            raise _schema_error(path, "additionalProperties must be boolean or a schema object")
        if isinstance(additional, dict):
            _validate_schema_definition(additional, path=f"{path}.additionalProperties")

    if "properties" in schema:
        properties = schema["properties"]
        if not isinstance(properties, dict) or not all(
            isinstance(name, str) for name in properties
        ):
            raise _schema_error(path, "properties must be an object keyed by strings")
        for name, child in properties.items():
            _validate_schema_definition(child, path=f"{path}.properties.{name}")

    if "items" in schema:
        _validate_schema_definition(schema["items"], path=f"{path}.items")

    return schema


def load_report_schema(path: Path | None = None) -> dict[str, object]:
    """Load and verify the canonical report schema, failing closed on drift."""

    schema_path = REPORT_SCHEMA_PATH if path is None else path
    try:
        raw = strict_json_loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, StrictJsonError) as exc:
        raise ReportSchemaError(
            f"cannot load canonical report schema {schema_path}: {type(exc).__name__}: {exc}"
        ) from exc
    schema = _validate_schema_definition(raw)
    if schema.get("$schema") != _SUPPORTED_SCHEMA_DIALECT:
        raise _schema_error("$", f"$schema must be {_SUPPORTED_SCHEMA_DIALECT}")
    return schema


def _matches_type(value: object, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def _instance_error(path: str, message: str) -> ReportSchemaError:
    return ReportSchemaError(f"report does not satisfy canonical schema at {path}: {message}")


def _validate_instance(value: object, schema: dict[str, object], *, path: str = "$") -> None:
    type_value = schema.get("type")
    if type_value is not None:
        expected_types = [type_value] if isinstance(type_value, str) else type_value
        if not isinstance(expected_types, list) or not all(
            isinstance(item, str) for item in expected_types
        ):
            raise _schema_error(path, "validated type definition became invalid")
        if not any(_matches_type(value, expected) for expected in expected_types):
            raise _instance_error(path, f"expected type {'|'.join(expected_types)}")

    if "const" in schema and value != schema["const"]:
        raise _instance_error(path, "value does not match const")

    if "enum" in schema:
        enum = schema["enum"]
        if not isinstance(enum, list):
            raise _schema_error(path, "validated enum definition became invalid")
        if value not in enum:
            raise _instance_error(path, "value is not in enum")

    if isinstance(value, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            raise _instance_error(path, f"string length is below minLength {min_length}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            raise _instance_error(path, "string does not match pattern")

    if isinstance(value, dict):
        required = schema.get("required", [])
        if not isinstance(required, list):
            raise _schema_error(path, "validated required definition became invalid")
        missing = [name for name in required if isinstance(name, str) and name not in value]
        if missing:
            raise _instance_error(path, f"missing required property(s): {', '.join(missing)}")

        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise _schema_error(path, "validated properties definition became invalid")
        for name, child_schema in properties.items():
            if name in value:
                if not isinstance(child_schema, dict):
                    raise _schema_error(path, f"property schema for {name} became invalid")
                _validate_instance(value[name], child_schema, path=f"{path}.{name}")

        extras = [name for name in value if name not in properties]
        additional = schema.get("additionalProperties", True)
        if additional is False and extras:
            raise _instance_error(path, f"additional property(s) not allowed: {', '.join(extras)}")
        if isinstance(additional, dict):
            for name in extras:
                _validate_instance(value[name], additional, path=f"{path}.{name}")

    if isinstance(value, list):
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            raise _instance_error(path, f"array length is below minItems {min_items}")
        if schema.get("uniqueItems") is True:
            canonical_items = [
                json.dumps(item, sort_keys=True, separators=(",", ":")) for item in value
            ]
            if len(canonical_items) != len(set(canonical_items)):
                raise _instance_error(path, "array items are not unique")
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                _validate_instance(item, items, path=f"{path}[{index}]")


def validate_report_payload(payload: object) -> None:
    """Validate one report against the live canonical schema."""

    schema = load_report_schema()
    _validate_instance(payload, schema)


def report_schema_version() -> str:
    """Read the report schema-version const from the canonical schema."""

    schema = load_report_schema()
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise ReportSchemaError("canonical report schema has no properties object")
    version_schema = properties.get("schema_version")
    if not isinstance(version_schema, dict):
        raise ReportSchemaError("canonical report schema has no schema_version property")
    version = version_schema.get("const")
    if not isinstance(version, str) or not version:
        raise ReportSchemaError("canonical report schema schema_version const is invalid")
    return version


REPORT_SCHEMA = report_schema_version()
