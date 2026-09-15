import json
from pathlib import Path

import pytest

from factory.quality.test_report import REPORT_SCHEMA, ReportValidationError, validate_report

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
