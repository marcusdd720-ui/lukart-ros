"""
Validation Engine tests.

Sprint F-012
"""

from __future__ import annotations

from core.validation.models import (
    Severity,
    ValidationContext,
    ValidationIssue,
    ValidationReport,
)


def test_validation_context_defaults() -> None:
    context = ValidationContext()

    assert context.project is None
    assert context.case_id is None
    assert context.metadata == {}


def test_validation_issue_creation() -> None:
    issue = ValidationIssue(
        code="TEST-001",
        message="Example validation issue.",
        severity=Severity.ERROR,
    )

    assert issue.code == "TEST-001"
    assert issue.message == "Example validation issue."
    assert issue.severity is Severity.ERROR
    assert issue.entity_id is None


def test_empty_report_is_valid() -> None:
    report = ValidationReport()

    assert report.is_valid
    assert len(report) == 0
    assert report.errors == []
    assert report.warnings == []
    assert report.infos == []


def test_add_error_issue() -> None:
    report = ValidationReport()

    report.add(
        ValidationIssue(
            code="ERR-001",
            message="Failure",
            severity=Severity.ERROR,
        )
    )

    assert len(report) == 1
    assert not report.is_valid
    assert len(report.errors) == 1


def test_add_warning_issue() -> None:
    report = ValidationReport()

    report.add(
        ValidationIssue(
            code="WARN-001",
            message="Warning",
            severity=Severity.WARNING,
        )
    )

    assert report.is_valid
    assert len(report.warnings) == 1
    assert len(report.errors) == 0


def test_add_info_issue() -> None:
    report = ValidationReport()

    report.add(
        ValidationIssue(
            code="INFO-001",
            message="Information",
            severity=Severity.INFO,
        )
    )

    assert report.is_valid
    assert len(report.infos) == 1


def test_extend_report() -> None:
    report = ValidationReport()

    report.extend(
        [
            ValidationIssue(
                code="ERR-001",
                message="Failure",
                severity=Severity.ERROR,
            ),
            ValidationIssue(
                code="WARN-001",
                message="Warning",
                severity=Severity.WARNING,
            ),
        ]
    )

    assert len(report) == 2
    assert len(report.errors) == 1
    assert len(report.warnings) == 1