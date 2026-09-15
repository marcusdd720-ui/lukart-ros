"""Canonical CASE-TESTY regression-suite parser, runner and completeness verifier."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SUITE_PATH = Path("docs/CASE_REGRESSION_SUITE.md")
REPORT_SCHEMA = "lukart.case-regression-suite-report.v1"
_BATCH_HEADING = "## TESTY BATCHOWE"
_MANUAL_HEADING = "## TESTY RĘCZNE / PRODUCT SMOKE"
_EXPECTED_COLUMNS = ("ID", "Pytest node", "Description")
_ID_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]{2,63}$")


class SuiteContractError(ValueError):
    """Raised when the canonical regression-suite source is invalid."""


@dataclass(frozen=True)
class BatchCase:
    test_id: str
    pytest_node: str
    description: str


@dataclass(frozen=True)
class SuiteSpec:
    source_path: str
    source_sha256: str
    batch_cases: tuple[BatchCase, ...]


@dataclass(frozen=True)
class CaseResult:
    test_id: str
    pytest_node: str
    status: str
    exit_code: int | None
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.test_id,
            "pytest_node": self.pytest_node,
            "status": self.status,
            "exit_code": self.exit_code,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SuiteReport:
    source_path: str
    source_sha256: str
    expected_batch_tests: tuple[str, ...]
    executed_tests: tuple[str, ...]
    cases: tuple[CaseResult, ...]
    status: str
    reason: str
    errors: tuple[str, ...] = ()
    schema_version: str = REPORT_SCHEMA

    def to_dict(self) -> dict[str, object]:
        counts = {
            "expected": len(self.expected_batch_tests),
            "executed": len(self.executed_tests),
            "pass": sum(case.status == "PASS" for case in self.cases),
            "fail": sum(case.status == "FAIL" for case in self.cases),
            "abstain": sum(case.status == "ABSTAIN" for case in self.cases),
        }
        missing = sorted(set(self.expected_batch_tests) - set(self.executed_tests))
        unexpected = sorted(set(self.executed_tests) - set(self.expected_batch_tests))
        return {
            "schema_version": self.schema_version,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "expected_batch_tests": list(self.expected_batch_tests),
            "executed_tests": list(self.executed_tests),
            "missing_tests": missing,
            "unexpected_tests": unexpected,
            "manual_product_smoke": "SKIPPED",
            "counts": counts,
            "cases": [case.to_dict() for case in self.cases],
            "status": self.status,
            "reason": self.reason,
            "errors": list(self.errors),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


CaseExecutor = Callable[[BatchCase, Path], CaseResult]


def _split_markdown_row(line: str) -> tuple[str, ...]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        raise SuiteContractError("batch table rows must start and end with '|'")
    return tuple(cell.strip() for cell in stripped[1:-1].split("|"))


def _find_unique_heading(lines: Sequence[str], heading: str) -> int:
    indexes = [index for index, line in enumerate(lines) if line.strip() == heading]
    if len(indexes) != 1:
        raise SuiteContractError(f"expected exactly one heading: {heading}")
    return indexes[0]


def _parse_batch_table(lines: Sequence[str], heading_index: int) -> tuple[BatchCase, ...]:
    index = heading_index + 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index + 1 >= len(lines):
        raise SuiteContractError("missing batch table")
    columns = _split_markdown_row(lines[index])
    if columns != _EXPECTED_COLUMNS:
        raise SuiteContractError(
            f"batch table columns must be exactly: {', '.join(_EXPECTED_COLUMNS)}"
        )
    separator = _split_markdown_row(lines[index + 1])
    if len(separator) != len(_EXPECTED_COLUMNS) or not all(
        re.fullmatch(r":?-{3,}:?", cell) for cell in separator
    ):
        raise SuiteContractError("invalid batch table separator")

    cases: list[BatchCase] = []
    index += 2
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            break
        cells = _split_markdown_row(line)
        if len(cells) != len(_EXPECTED_COLUMNS):
            raise SuiteContractError("every batch table row must have exactly three columns")
        test_id, pytest_node, description = cells
        if not test_id or not pytest_node or not description:
            raise SuiteContractError("batch table fields must be non-empty")
        cases.append(BatchCase(test_id, pytest_node, description))
        index += 1
    if not cases:
        raise SuiteContractError("canonical batch suite must contain at least one test")
    return tuple(cases)


def _validate_cases(cases: Sequence[BatchCase], repo_root: Path) -> None:
    ids = [case.test_id for case in cases]
    duplicate_ids = sorted({item for item in ids if ids.count(item) > 1})
    if duplicate_ids:
        raise SuiteContractError(f"duplicate batch IDs: {', '.join(duplicate_ids)}")

    nodes = [case.pytest_node for case in cases]
    duplicate_nodes = sorted({item for item in nodes if nodes.count(item) > 1})
    if duplicate_nodes:
        raise SuiteContractError(f"duplicate pytest nodes: {', '.join(duplicate_nodes)}")

    for case in cases:
        if _ID_PATTERN.fullmatch(case.test_id) is None:
            raise SuiteContractError(f"invalid batch ID: {case.test_id}")
        if any(token in case.pytest_node for token in ("\n", "\r", "|")):
            raise SuiteContractError(f"invalid pytest node for {case.test_id}")
        file_part = case.pytest_node.split("::", 1)[0]
        path = Path(file_part)
        if path.is_absolute() or ".." in path.parts:
            raise SuiteContractError(f"pytest node escapes repository: {case.test_id}")
        if not path.parts or path.parts[0] != "tests" or path.suffix != ".py":
            raise SuiteContractError(f"pytest node must target a tests/*.py file: {case.test_id}")
        if not (repo_root / path).is_file():
            raise SuiteContractError(f"pytest target does not exist: {case.pytest_node}")


def load_suite(source: Path, *, repo_root: Path) -> SuiteSpec:
    raw = source.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SuiteContractError("suite source must be UTF-8") from exc
    lines = text.splitlines()
    batch_index = _find_unique_heading(lines, _BATCH_HEADING)
    manual_index = _find_unique_heading(lines, _MANUAL_HEADING)
    if manual_index <= batch_index:
        raise SuiteContractError("manual/product-smoke section must follow batch section")
    cases = _parse_batch_table(lines, batch_index)
    _validate_cases(cases, repo_root)
    try:
        source_path = source.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        source_path = source.as_posix()
    return SuiteSpec(
        source_path=source_path,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        batch_cases=cases,
    )


def execute_case(case: BatchCase, repo_root: Path) -> CaseResult:
    try:
        completed = subprocess.run(
            (sys.executable, "-m", "pytest", case.pytest_node, "-q"),
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        return CaseResult(
            test_id=case.test_id,
            pytest_node=case.pytest_node,
            status="ABSTAIN",
            exit_code=None,
            reason=f"executor error: {type(exc).__name__}: {exc}",
        )
    status = "PASS" if completed.returncode == 0 else "FAIL"
    return CaseResult(
        test_id=case.test_id,
        pytest_node=case.pytest_node,
        status=status,
        exit_code=completed.returncode,
        reason=f"pytest exit code {completed.returncode}",
    )


def run_suite(
    source: Path,
    *,
    repo_root: Path,
    executor: CaseExecutor | None = None,
) -> SuiteReport:
    try:
        spec = load_suite(source, repo_root=repo_root)
    except (OSError, SuiteContractError) as exc:
        return SuiteReport(
            source_path=source.as_posix(),
            source_sha256="",
            expected_batch_tests=(),
            executed_tests=(),
            cases=(),
            status="ABSTAIN",
            reason="canonical suite could not be validated",
            errors=(str(exc),),
        )

    selected_executor = executor or execute_case
    results = tuple(selected_executor(case, repo_root) for case in spec.batch_cases)
    expected = tuple(case.test_id for case in spec.batch_cases)
    executed = tuple(case.test_id for case in results)
    if executed != expected:
        return SuiteReport(
            source_path=spec.source_path,
            source_sha256=spec.source_sha256,
            expected_batch_tests=expected,
            executed_tests=executed,
            cases=results,
            status="ABSTAIN",
            reason="batch completeness mismatch",
            errors=("executed test IDs do not exactly match canonical batch IDs",),
        )
    if any(result.status == "ABSTAIN" for result in results):
        status = "ABSTAIN"
        reason = "one or more canonical batch tests could not be evaluated"
    elif any(result.status == "FAIL" for result in results):
        status = "FAIL"
        reason = "one or more canonical batch tests failed"
    else:
        status = "PASS"
        reason = "all canonical batch tests passed"
    return SuiteReport(
        source_path=spec.source_path,
        source_sha256=spec.source_sha256,
        expected_batch_tests=expected,
        executed_tests=executed,
        cases=results,
        status=status,
        reason=reason,
    )


def verify_report(source: Path, report_path: Path, *, repo_root: Path) -> tuple[str, ...]:
    errors: list[str] = []
    try:
        spec = load_suite(source, repo_root=repo_root)
    except (OSError, SuiteContractError) as exc:
        return (f"canonical suite invalid: {exc}",)
    try:
        payload: Any = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return (f"report unreadable: {exc}",)
    if not isinstance(payload, dict):
        return ("report root must be an object",)

    expected = [case.test_id for case in spec.batch_cases]
    if payload.get("schema_version") != REPORT_SCHEMA:
        errors.append("report schema_version mismatch")
    if payload.get("source_sha256") != spec.source_sha256:
        errors.append("report source_sha256 does not match canonical suite")
    if payload.get("expected_batch_tests") != expected:
        errors.append("report expected_batch_tests does not match canonical suite")
    if payload.get("executed_tests") != expected:
        errors.append("report is incomplete or out of canonical order")
    if payload.get("missing_tests") != []:
        errors.append("report contains missing tests")
    if payload.get("unexpected_tests") != []:
        errors.append("report contains unexpected tests")
    if payload.get("manual_product_smoke") != "SKIPPED":
        errors.append("manual/product smoke must remain skipped")
    if payload.get("status") != "PASS":
        errors.append("canonical batch report status is not PASS")
    expected_counts = {
        "expected": len(expected),
        "executed": len(expected),
        "pass": len(expected),
        "fail": 0,
        "abstain": 0,
    }
    if payload.get("counts") != expected_counts:
        errors.append("report counts do not prove complete PASS")

    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) != len(expected):
        errors.append("report case count does not match canonical suite")
    else:
        ids = [case.get("id") for case in cases if isinstance(case, dict)]
        statuses = [case.get("status") for case in cases if isinstance(case, dict)]
        if ids != expected:
            errors.append("report case IDs do not match canonical order")
        if len(statuses) != len(expected) or any(status != "PASS" for status in statuses):
            errors.append("one or more report cases are not PASS")
    return tuple(errors)


def _write_report(report: SuiteReport, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.to_json() + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SUITE_PATH)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--verify-report", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = args.root.resolve()
    source = args.source
    if not source.is_absolute():
        source = repo_root / source

    if args.validate_only and args.verify_report is not None:
        print("choose only one of --validate-only or --verify-report", file=sys.stderr)
        return 2
    if args.validate_only:
        try:
            spec = load_suite(source, repo_root=repo_root)
        except (OSError, SuiteContractError) as exc:
            print(f"CANONICAL SUITE VALIDATION: ABSTAIN - {exc}")
            return 2
        print(
            "CANONICAL SUITE VALIDATION: PASS "
            f"({len(spec.batch_cases)} batch tests, sha256={spec.source_sha256})"
        )
        return 0
    if args.verify_report is not None:
        report_path = args.verify_report
        if not report_path.is_absolute():
            report_path = repo_root / report_path
        errors = verify_report(source, report_path, repo_root=repo_root)
        if errors:
            for error in errors:
                print(f"CANONICAL SUITE REPORT: FAIL - {error}")
            return 1
        print("CANONICAL SUITE REPORT: PASS")
        return 0

    report = run_suite(source, repo_root=repo_root)
    if args.output is not None:
        output = args.output
        if not output.is_absolute():
            output = repo_root / output
        _write_report(report, output)
    print(report.to_json())
    return 0 if report.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
