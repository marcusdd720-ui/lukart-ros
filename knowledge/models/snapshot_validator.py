"""
Validate CaseSnapshot before publish.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCHEMA = "lukart.snapshot.v1"


@dataclass(slots=True, frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "ERROR"  # ERROR | WARNING


@dataclass(slots=True, frozen=True)
class SnapshotValidation:
    ok: bool
    ready_to_publish: bool
    issues: tuple[ValidationIssue, ...]

    def report(self) -> str:
        lines = [
            "SnapshotValidation",
            f"ok: {self.ok}",
            f"ready_to_publish: {self.ready_to_publish}",
            f"issues: {len(self.issues)}",
            "",
        ]
        for issue in self.issues:
            lines.append(f"  [{issue.severity}] {issue.code}: {issue.message}")
        if not self.issues:
            lines.append("  (none)")
        return "\n".join(lines)


def validate_snapshot(data: dict[str, Any]) -> SnapshotValidation:
    issues: list[ValidationIssue] = []

    if data.get("schema") != SCHEMA:
        issues.append(
            ValidationIssue(
                "SNAP001",
                f"Unsupported schema: {data.get('schema')!r} (expected {SCHEMA})",
            )
        )

    if not data.get("case_key"):
        issues.append(ValidationIssue("SNAP002", "Missing case_key"))

    if not data.get("graph_case_id"):
        issues.append(ValidationIssue("SNAP003", "Missing graph_case_id"))

    for flag, code in (
        ("fact_pass", "SNAP010"),
        ("law_pass", "SNAP011"),
        ("review_pass", "SNAP012"),
    ):
        if data.get(flag) is not True:
            issues.append(
                ValidationIssue(code, f"{flag} is not True (value={data.get(flag)!r})")
            )

    if not data.get("dossier_path"):
        issues.append(ValidationIssue("SNAP020", "Missing dossier_path"))

    if not data.get("dossier_sha256"):
        issues.append(ValidationIssue("SNAP021", "Missing dossier_sha256"))

    if data.get("git_dirty") is True:
        issues.append(
            ValidationIssue(
                "SNAP030",
                "git_dirty=True at snapshot time (warning only)",
                severity="WARNING",
            )
        )

    status = data.get("status")
    errors = [i for i in issues if i.severity == "ERROR"]
    ready = status == "READY_TO_PUBLISH" and not errors

    if status != "READY_TO_PUBLISH" and not errors:
        issues.append(
            ValidationIssue(
                "SNAP040",
                f"status is {status!r}, not READY_TO_PUBLISH",
            )
        )
        errors = [i for i in issues if i.severity == "ERROR"]
        ready = False

    return SnapshotValidation(
        ok=not errors,
        ready_to_publish=ready,
        issues=tuple(issues),
    )


def main() -> int:
    import json
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[2]
        / "output"
        / "cases"
        / "DS_3960_2025"
        / "snapshots"
        / "latest.json"
    )
    if not path.is_file():
        print("No latest.json at", path)
        return 2

    data = json.loads(path.read_text(encoding="utf-8"))
    result = validate_snapshot(data)
    print(result.report())
    print("Status field:", data.get("status"))
    return 0 if result.ready_to_publish else 1


if __name__ == "__main__":
    raise SystemExit(main())