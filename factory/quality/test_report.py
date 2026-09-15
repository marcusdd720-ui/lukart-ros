"""Fail-closed validation for CASE-TESTY machine-readable profile reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPORT_SCHEMA = "lukart.case-test-profile-report.v1"


class ReportValidationError(RuntimeError):
    pass


def validate_report(path: Path, *, expected_profile: str, expected_sha: str) -> dict[str, object]:
    if not path.is_file():
        raise ReportValidationError(f"report artifact missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportValidationError(f"malformed report: {type(exc).__name__}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReportValidationError("malformed report: top-level JSON must be an object")
    required_fields = {
        "schema_version",
        "repository",
        "ref",
        "git_sha",
        "checkout_sha",
        "profile",
        "started_at",
        "ended_at",
        "required_steps",
        "steps",
        "status",
        "reason",
    }
    missing = sorted(required_fields - payload.keys())
    if missing:
        raise ReportValidationError(f"malformed report: missing fields: {', '.join(missing)}")
    if payload["schema_version"] != REPORT_SCHEMA:
        raise ReportValidationError("malformed report: unsupported schema_version")
    if payload["profile"] != expected_profile:
        raise ReportValidationError(
            f"profile mismatch: expected {expected_profile}, got {payload['profile']}"
        )
    if payload["git_sha"] != expected_sha or payload["checkout_sha"] != expected_sha:
        raise ReportValidationError("wrong SHA: report is not bound to expected checkout SHA")
    required_steps = payload["required_steps"]
    steps = payload["steps"]
    if not isinstance(required_steps, list) or not required_steps:
        raise ReportValidationError("skipped required validation: required_steps is empty")
    if not isinstance(steps, list):
        raise ReportValidationError("malformed report: steps must be a list")
    by_name: dict[str, dict[str, object]] = {}
    for item in steps:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ReportValidationError("malformed report: invalid step record")
        by_name[item["name"]] = item
    for required_name in required_steps:
        if required_name not in by_name:
            raise ReportValidationError(f"skipped required validation: {required_name}")
        step = by_name[required_name]
        if step.get("required") is not True:
            raise ReportValidationError(
                f"skipped required validation: {required_name} not required"
            )
        if step.get("status") != "PASS" or step.get("exit_code") != 0:
            raise ReportValidationError(f"required step not PASS: {required_name}")
    if payload["status"] != "PASS":
        raise ReportValidationError(f"profile final status is not PASS: {payload['status']}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    try:
        validate_report(args.path, expected_profile=args.profile, expected_sha=args.sha)
    except ReportValidationError as exc:
        print(f"REPORT VALIDATION: FAIL: {exc}")
        return 1
    print("REPORT VALIDATION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
