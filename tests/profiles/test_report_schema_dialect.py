import json
from pathlib import Path

import pytest

from factory.quality.report_schema import REPORT_SCHEMA_PATH, ReportSchemaError, load_report_schema


def _canonical_schema() -> dict[str, object]:
    return json.loads(REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize(
    "dialect",
    [
        None,
        "https://json-schema.org/draft/2019-09/schema",
    ],
)
def test_canonical_schema_requires_supported_draft_2020_12(
    tmp_path: Path, dialect: str | None
) -> None:
    schema = _canonical_schema()
    if dialect is None:
        schema.pop("$schema")
    else:
        schema["$schema"] = dialect

    path = tmp_path / "case_test_report.schema.json"
    _write(path, schema)

    with pytest.raises(ReportSchemaError, match=r"\$schema must be"):
        load_report_schema(path)


def test_canonical_schema_accepts_declared_draft_2020_12() -> None:
    assert load_report_schema()["$schema"] == "https://json-schema.org/draft/2020-12/schema"
