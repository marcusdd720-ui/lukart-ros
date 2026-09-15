import json
from pathlib import Path

import pytest

from factory.quality import report_schema
from factory.quality.report_schema import REPORT_SCHEMA
from factory.quality.test_report import ReportValidationError, validate_report

SHA = "69f4843be7fc94c446f72b891a8fb44fbf9d9ed3"


def _payload() -> dict[str, object]:
    return {
        "schema_version": REPORT_SCHEMA,
        "repository": "marcusdd720-ui/lukart-ros",
        "ref": "case-testy/automation-p0",
        "git_sha": SHA,
        "checkout_sha": SHA,
        "profile": "FAST",
        "started_at": "2026-09-15T10:00:00Z",
        "ended_at": "2026-09-15T10:01:00Z",
        "required_steps": ["one"],
        "steps": [
            {
                "name": "one",
                "command": ["python", "-V"],
                "required": True,
                "status": "PASS",
                "exit_code": 0,
                "reason": "exit code 0",
            }
        ],
        "status": "PASS",
        "reason": "all required steps passed",
    }


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_complete_report_validates(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    _write(path, _payload())
    assert validate_report(path, expected_profile="FAST", expected_sha=SHA)["status"] == "PASS"


def test_missing_report_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ReportValidationError, match="report artifact missing"):
        validate_report(tmp_path / "missing.json", expected_profile="FAST", expected_sha=SHA)


def test_malformed_report_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ReportValidationError, match="malformed report"):
        validate_report(path, expected_profile="FAST", expected_sha=SHA)


def test_non_object_report_fails_canonical_schema(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    _write(path, [])
    with pytest.raises(ReportValidationError, match="schema validation failed"):
        validate_report(path, expected_profile="FAST", expected_sha=SHA)


def test_missing_required_field_fails_canonical_schema(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    payload = _payload()
    del payload["repository"]
    _write(path, payload)
    with pytest.raises(ReportValidationError, match="missing required property"):
        validate_report(path, expected_profile="FAST", expected_sha=SHA)


def test_wrong_primitive_type_fails_canonical_schema(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    payload = _payload()
    payload["repository"] = 7
    _write(path, payload)
    with pytest.raises(ReportValidationError, match="schema validation failed"):
        validate_report(path, expected_profile="FAST", expected_sha=SHA)


def test_additional_property_fails_canonical_schema(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    payload = _payload()
    payload["unexpected"] = "must fail closed"
    _write(path, payload)
    with pytest.raises(ReportValidationError, match="additional property"):
        validate_report(path, expected_profile="FAST", expected_sha=SHA)


@pytest.mark.parametrize(
    ("field", "value", "expected_profile"),
    [
        ("profile", "NOPE", "NOPE"),
        ("status", "UNKNOWN", "FAST"),
    ],
)
def test_unknown_enum_value_fails_canonical_schema(
    tmp_path: Path, field: str, value: str, expected_profile: str
) -> None:
    path = tmp_path / "report.json"
    payload = _payload()
    payload[field] = value
    _write(path, payload)
    with pytest.raises(ReportValidationError, match="value is not in enum"):
        validate_report(path, expected_profile=expected_profile, expected_sha=SHA)


def test_schema_drift_is_enforced_by_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    schema = json.loads(report_schema.REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))
    schema["required"].append("p2_required_marker")
    schema["properties"]["p2_required_marker"] = {"type": "string"}
    drifted_schema = tmp_path / "case_test_report.schema.json"
    _write(drifted_schema, schema)
    monkeypatch.setattr(report_schema, "REPORT_SCHEMA_PATH", drifted_schema)

    path = tmp_path / "report.json"
    _write(path, _payload())
    with pytest.raises(ReportValidationError, match="p2_required_marker"):
        validate_report(path, expected_profile="FAST", expected_sha=SHA)


def test_unsupported_schema_keyword_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    schema = json.loads(report_schema.REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))
    schema["allOf"] = []
    unsupported_schema = tmp_path / "case_test_report.schema.json"
    _write(unsupported_schema, schema)
    monkeypatch.setattr(report_schema, "REPORT_SCHEMA_PATH", unsupported_schema)

    path = tmp_path / "report.json"
    _write(path, _payload())
    with pytest.raises(ReportValidationError, match="unsupported keyword"):
        validate_report(path, expected_profile="FAST", expected_sha=SHA)


def test_wrong_sha_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    payload = _payload()
    payload["checkout_sha"] = "2" * 40
    _write(path, payload)
    with pytest.raises(ReportValidationError, match="wrong SHA"):
        validate_report(path, expected_profile="FAST", expected_sha=SHA)


def test_profile_mismatch_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    _write(path, _payload())
    with pytest.raises(ReportValidationError, match="profile mismatch"):
        validate_report(path, expected_profile="FULL", expected_sha=SHA)


def test_duplicate_step_names_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    payload = _payload()
    steps = payload["steps"]
    assert isinstance(steps, list)
    assert isinstance(steps[0], dict)
    duplicate = dict(steps[0])
    duplicate["status"] = "FAIL"
    duplicate["exit_code"] = 1
    duplicate["reason"] = "exit code 1"
    steps.insert(0, duplicate)
    _write(path, payload)

    with pytest.raises(ReportValidationError, match="duplicate step name"):
        validate_report(path, expected_profile="FAST", expected_sha=SHA)


def test_required_step_omitted_from_manifest_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    payload = _payload()
    steps = payload["steps"]
    assert isinstance(steps, list)
    steps.append(
        {
            "name": "hidden-required",
            "command": ["python", "-c", "raise SystemExit(1)"],
            "required": True,
            "status": "FAIL",
            "exit_code": 1,
            "reason": "exit code 1",
        }
    )
    _write(path, payload)

    with pytest.raises(ReportValidationError, match="required-step manifest mismatch"):
        validate_report(path, expected_profile="FAST", expected_sha=SHA)


def test_skipped_required_validation_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    payload = _payload()
    payload["steps"] = []
    _write(path, payload)
    with pytest.raises(ReportValidationError, match="skipped required validation"):
        validate_report(path, expected_profile="FAST", expected_sha=SHA)


def test_required_unknown_cannot_validate_as_pass(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    payload = _payload()
    steps = payload["steps"]
    assert isinstance(steps, list)
    assert isinstance(steps[0], dict)
    steps[0]["status"] = "UNKNOWN"
    steps[0]["exit_code"] = None
    _write(path, payload)
    with pytest.raises(ReportValidationError, match="required step not PASS"):
        validate_report(path, expected_profile="FAST", expected_sha=SHA)
