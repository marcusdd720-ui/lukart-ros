from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.quality.case_regression_suite import (
    BatchCase,
    CaseResult,
    SuiteContractError,
    load_suite,
    run_suite,
    verify_report,
)


def _suite_text(rows: list[tuple[str, str, str]]) -> str:
    body = "\n".join(
        f"| {test_id} | {node} | {description} |"
        for test_id, node, description in rows
    )
    return (
        "# CASE-TESTY — Canonical Regression Suite\n\n"
        "## TESTY BATCHOWE\n\n"
        "| ID | Pytest node | Description |\n"
        "|---|---|---|\n"
        f"{body}\n\n"
        "## TESTY RĘCZNE / PRODUCT SMOKE\n\n"
        "Manual/product-smoke scenarios are not executed by the automated batch runner.\n"
    )


def _write_target(root: Path, relative: str = "tests/test_synthetic_case.py") -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("def test_synthetic() -> None:\n    assert True\n", encoding="utf-8")


def test_load_suite_parses_strict_batch_mapping(tmp_path: Path) -> None:
    _write_target(tmp_path)
    source = tmp_path / "docs" / "CASE_REGRESSION_SUITE.md"
    source.parent.mkdir()
    source.write_text(
        _suite_text([("CASE-BATCH-001", "tests/test_synthetic_case.py", "synthetic")]),
        encoding="utf-8",
    )

    spec = load_suite(source, repo_root=tmp_path)

    assert [case.test_id for case in spec.batch_cases] == ["CASE-BATCH-001"]
    assert len(spec.source_sha256) == 64


def test_duplicate_batch_id_fails_closed(tmp_path: Path) -> None:
    _write_target(tmp_path)
    source = tmp_path / "suite.md"
    source.write_text(
        _suite_text(
            [
                ("CASE-BATCH-001", "tests/test_synthetic_case.py", "one"),
                (
                    "CASE-BATCH-001",
                    "tests/test_synthetic_case.py::test_synthetic",
                    "two",
                ),
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(SuiteContractError, match="duplicate batch IDs"):
        load_suite(source, repo_root=tmp_path)


def test_missing_manual_section_fails_closed(tmp_path: Path) -> None:
    _write_target(tmp_path)
    source = tmp_path / "suite.md"
    source.write_text(
        "# CASE\n\n"
        "## TESTY BATCHOWE\n\n"
        "| ID | Pytest node | Description |\n"
        "|---|---|---|\n"
        "| CASE-BATCH-001 | tests/test_synthetic_case.py | synthetic |\n",
        encoding="utf-8",
    )

    with pytest.raises(SuiteContractError, match="TESTY RĘCZNE"):
        load_suite(source, repo_root=tmp_path)


def test_pytest_mapping_cannot_escape_tests_tree(tmp_path: Path) -> None:
    source = tmp_path / "suite.md"
    source.write_text(
        _suite_text([("CASE-BATCH-001", "../private_case.py", "invalid")]),
        encoding="utf-8",
    )

    with pytest.raises(SuiteContractError, match="escapes repository"):
        load_suite(source, repo_root=tmp_path)


def test_run_suite_requires_exact_completeness(tmp_path: Path) -> None:
    _write_target(tmp_path)
    source = tmp_path / "suite.md"
    source.write_text(
        _suite_text(
            [
                ("CASE-BATCH-001", "tests/test_synthetic_case.py", "one"),
                (
                    "CASE-BATCH-002",
                    "tests/test_synthetic_case.py::test_synthetic",
                    "two",
                ),
            ]
        ),
        encoding="utf-8",
    )

    def execute(case: BatchCase, _: Path) -> CaseResult:
        if case.test_id == "CASE-BATCH-002":
            return CaseResult("OTHER-ID", case.pytest_node, "PASS", 0, "synthetic")
        return CaseResult(case.test_id, case.pytest_node, "PASS", 0, "synthetic")

    report = run_suite(source, repo_root=tmp_path, executor=execute)

    assert report.status == "ABSTAIN"
    assert "completeness" in report.reason


def test_run_suite_reports_test_failure(tmp_path: Path) -> None:
    _write_target(tmp_path)
    source = tmp_path / "suite.md"
    source.write_text(
        _suite_text([("CASE-BATCH-001", "tests/test_synthetic_case.py", "synthetic")]),
        encoding="utf-8",
    )

    def execute(case: BatchCase, _: Path) -> CaseResult:
        return CaseResult(case.test_id, case.pytest_node, "FAIL", 1, "synthetic failure")

    report = run_suite(source, repo_root=tmp_path, executor=execute)

    assert report.status == "FAIL"
    assert report.cases[0].status == "FAIL"


def test_verify_report_rejects_missing_execution(tmp_path: Path) -> None:
    _write_target(tmp_path)
    source = tmp_path / "suite.md"
    source.write_text(
        _suite_text([("CASE-BATCH-001", "tests/test_synthetic_case.py", "synthetic")]),
        encoding="utf-8",
    )
    spec = load_suite(source, repo_root=tmp_path)
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": "lukart.case-regression-suite-report.v1",
                "source_sha256": spec.source_sha256,
                "expected_batch_tests": ["CASE-BATCH-001"],
                "executed_tests": [],
                "missing_tests": ["CASE-BATCH-001"],
                "unexpected_tests": [],
                "manual_product_smoke": "SKIPPED",
                "cases": [],
                "status": "PASS",
            }
        ),
        encoding="utf-8",
    )

    errors = verify_report(source, report_path, repo_root=tmp_path)

    assert errors
    assert any("incomplete" in error or "missing" in error for error in errors)


def test_verify_report_rejects_wrong_source_digest(tmp_path: Path) -> None:
    _write_target(tmp_path)
    source = tmp_path / "suite.md"
    source.write_text(
        _suite_text([("CASE-BATCH-001", "tests/test_synthetic_case.py", "synthetic")]),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": "lukart.case-regression-suite-report.v1",
                "source_sha256": "0" * 64,
                "expected_batch_tests": ["CASE-BATCH-001"],
                "executed_tests": ["CASE-BATCH-001"],
                "missing_tests": [],
                "unexpected_tests": [],
                "manual_product_smoke": "SKIPPED",
                "cases": [
                    {
                        "id": "CASE-BATCH-001",
                        "pytest_node": "tests/test_synthetic_case.py",
                        "status": "PASS",
                        "exit_code": 0,
                        "reason": "ok",
                    }
                ],
                "status": "PASS",
            }
        ),
        encoding="utf-8",
    )

    errors = verify_report(source, report_path, repo_root=tmp_path)

    assert "report source_sha256 does not match canonical suite" in errors


def test_repository_canonical_suite_is_valid() -> None:
    root = Path(__file__).resolve().parents[2]
    source = root / "docs" / "CASE_REGRESSION_SUITE.md"

    spec = load_suite(source, repo_root=root)

    assert spec.batch_cases
    assert all(case.pytest_node.startswith("tests/") for case in spec.batch_cases)


def test_verify_report_accepts_complete_bound_pass(tmp_path: Path) -> None:
    _write_target(tmp_path)
    source = tmp_path / "suite.md"
    source.write_text(
        _suite_text([("CASE-BATCH-001", "tests/test_synthetic_case.py", "synthetic")]),
        encoding="utf-8",
    )

    def execute(case: BatchCase, _: Path) -> CaseResult:
        return CaseResult(case.test_id, case.pytest_node, "PASS", 0, "synthetic pass")

    report = run_suite(source, repo_root=tmp_path, executor=execute)
    report_path = tmp_path / "report.json"
    report_path.write_text(report.to_json(), encoding="utf-8")

    assert verify_report(source, report_path, repo_root=tmp_path) == ()


def test_manual_product_smoke_section_is_not_executed(tmp_path: Path) -> None:
    _write_target(tmp_path)
    source = tmp_path / "suite.md"
    source.write_text(
        _suite_text([("CASE-BATCH-001", "tests/test_synthetic_case.py", "synthetic")])
        + "\n| MANUAL-001 | tests/test_should_not_run.py | manual only |\n",
        encoding="utf-8",
    )
    seen: list[str] = []

    def execute(case: BatchCase, _: Path) -> CaseResult:
        seen.append(case.test_id)
        return CaseResult(case.test_id, case.pytest_node, "PASS", 0, "synthetic pass")

    report = run_suite(source, repo_root=tmp_path, executor=execute)

    assert report.status == "PASS"
    assert seen == ["CASE-BATCH-001"]
