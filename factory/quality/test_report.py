"""Fail-closed validation for CASE-TESTY machine-readable profile reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from factory.quality.report_schema import ReportSchemaError, validate_report_payload


class ReportValidationError(RuntimeError):
    pass


def validate_report(path: Path, *, expected_profile: str, expected_sha: str) -> dict[str, object]:
    if not path.is_file():
        raise ReportValidationError(f"report artifact missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportValidationError(f"malformed report: {type(exc).__name__}: {exc}") from exc

    try:
        validate_report_payload(payload)
    except ReportSchemaError as exc:
        raise ReportValidationError(f"schema validation failed: {exc}") from exc

    report = cast(dict[str, object], payload)
    if report["profile"] != expected_profile:
        raise ReportValidationError(
            f"profile mismatch: expected {expected_profile}, got {report['profile']}"
        )
    if report["git_sha"] != expected_sha or report["checkout_sha"] != expected_sha:
        raise ReportValidationError("wrong SHA: report is not bound to expected checkout SHA")

    required_steps = cast(list[str], report["required_steps"])
    steps = cast(list[dict[str, object]], report["steps"])
    step_names = [cast(str, item["name"]) for item in steps]
    if len(step_names) != len(set(step_names)):
        duplicate_names = sorted({name for name in step_names if step_names.count(name) > 1})
        raise ReportValidationError(f"duplicate step name(s): {', '.join(duplicate_names)}")

    by_name = {cast(str, item["name"]): item for item in steps}
    for required_name in required_steps:
        if required_name not in by_name:
            raise ReportValidationError(f"skipped required validation: {required_name}")
        if by_name[required_name]["required"] is not True:
            raise ReportValidationError(
                f"skipped required validation: {required_name} not required"
            )

    required_manifest = set(required_steps)
    required_from_steps = {
        name for name, item in by_name.items() if item["required"] is True
    }
    if required_manifest != required_from_steps:
        missing = sorted(required_from_steps - required_manifest)
        unexpected = sorted(required_manifest - required_from_steps)
        details: list[str] = []
        if missing:
            details.append(f"missing from manifest: {', '.join(missing)}")
        if unexpected:
            details.append(f"manifest marks non-required step(s): {', '.join(unexpected)}")
        raise ReportValidationError(f"required-step manifest mismatch: {'; '.join(details)}")

    for required_name in required_steps:
        step = by_name[required_name]
        if step["status"] != "PASS" or step["exit_code"] != 0:
            raise ReportValidationError(f"required step not PASS: {required_name}")
    if report["status"] != "PASS":
        raise ReportValidationError(f"profile final status is not PASS: {report['status']}")
    return report


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
