"""Pure deterministic CASE-TESTY signed-authoring transforms.

This module is intentionally incapable of GitHub publication.
All privileged publication belongs to case_signed_authoring_hardened.
"""

from __future__ import annotations

MAIN_BRANCH = "main"
OPERATION = "harden_manual_smoke_inventory"
TARGET_BRANCH = "case-testy/manual-inventory-validation-295-auto"

ALLOWED_PATHS = {
    "factory/quality/case_regression_suite.py",
    "tests/case/test_case_regression_suite_manual_inventory.py",
}


class SignedAuthoringError(RuntimeError):
    """Fail-closed CASE-TESTY authoring error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SignedAuthoringError(message)


def replace_once(
    text: str,
    old: str,
    new: str,
    *,
    label: str,
) -> str:
    count = text.count(old)
    if count != 1:
        raise SignedAuthoringError(
            f"{label}: expected exactly one target, found {count}"
        )
    return text.replace(old, new, 1)


def render_regression_suite_update(source: str) -> str:
    text = source

    text = replace_once(
        text,
        '_EXPECTED_COLUMNS = ("ID", "Pytest node", "Description")\n',
        '_EXPECTED_COLUMNS = ("ID", "Pytest node", "Description")\n'
        '_MANUAL_EXPECTED_COLUMNS = (\n'
        '    "ID",\n'
        '    "Authority",\n'
        '    "Synthetic stimulus",\n'
        '    "Acceptance criteria",\n'
        ')\n',
        label="manual table columns",
    )

    text = replace_once(
        text,
        "@dataclass(frozen=True)\n"
        "class SuiteSpec:\n"
        "    source_path: str\n"
        "    source_sha256: str\n"
        "    batch_cases: tuple[BatchCase, ...]\n",
        "@dataclass(frozen=True)\n"
        "class ManualCase:\n"
        "    test_id: str\n"
        "    authority: str\n"
        "    synthetic_stimulus: str\n"
        "    acceptance_criteria: str\n\n\n"
        "@dataclass(frozen=True)\n"
        "class SuiteSpec:\n"
        "    source_path: str\n"
        "    source_sha256: str\n"
        "    batch_cases: tuple[BatchCase, ...]\n"
        "    manual_cases: tuple[ManualCase, ...]\n",
        label="ManualCase model",
    )

    marker = (
        "\n\ndef _validate_cases("
        "cases: Sequence[BatchCase], repo_root: Path"
        ") -> None:\n"
    )

    parser = r'''

def _parse_manual_table(
    lines: Sequence[str],
    heading_index: int,
) -> tuple[ManualCase, ...]:
    index = heading_index + 1

    while index < len(lines):
        stripped = lines[index].strip()

        if stripped.startswith("#"):
            raise SuiteContractError(
                "missing manual/product-smoke table"
            )

        if stripped.startswith("|"):
            break

        index += 1

    if index + 1 >= len(lines):
        raise SuiteContractError(
            "missing manual/product-smoke table"
        )

    columns = _split_markdown_row(lines[index])

    if columns != _MANUAL_EXPECTED_COLUMNS:
        raise SuiteContractError(
            "manual table columns must be exactly: "
            + ", ".join(_MANUAL_EXPECTED_COLUMNS)
        )

    separator = _split_markdown_row(lines[index + 1])

    if (
        len(separator) != len(_MANUAL_EXPECTED_COLUMNS)
        or not all(
            re.fullmatch(r":?-{3,}:?", cell)
            for cell in separator
        )
    ):
        raise SuiteContractError(
            "invalid manual table separator"
        )

    cases: list[ManualCase] = []
    index += 2

    while index < len(lines):
        stripped = lines[index].strip()

        if not stripped or stripped.startswith("#"):
            break

        if not stripped.startswith("|"):
            raise SuiteContractError(
                "manual table rows must remain "
                "contiguous table rows"
            )

        cells = _split_markdown_row(lines[index])

        if len(cells) != len(_MANUAL_EXPECTED_COLUMNS):
            raise SuiteContractError(
                "every manual table row must have "
                "exactly four columns"
            )

        (
            test_id,
            authority,
            synthetic_stimulus,
            acceptance_criteria,
        ) = cells

        if not all(
            (
                test_id,
                authority,
                synthetic_stimulus,
                acceptance_criteria,
            )
        ):
            raise SuiteContractError(
                "manual table fields must be non-empty"
            )

        cases.append(
            ManualCase(
                test_id=test_id,
                authority=authority,
                synthetic_stimulus=synthetic_stimulus,
                acceptance_criteria=acceptance_criteria,
            )
        )

        index += 1

    if not cases:
        raise SuiteContractError(
            "canonical manual/product-smoke suite "
            "must contain at least one test"
        )

    return tuple(cases)


def _validate_manual_cases(
    cases: Sequence[ManualCase],
) -> None:
    ids = [case.test_id for case in cases]

    duplicate_ids = sorted(
        {
            item
            for item in ids
            if ids.count(item) > 1
        }
    )

    if duplicate_ids:
        raise SuiteContractError(
            "duplicate manual IDs: "
            + ", ".join(duplicate_ids)
        )

    for case in cases:
        if _ID_PATTERN.fullmatch(case.test_id) is None:
            raise SuiteContractError(
                f"invalid manual ID: {case.test_id}"
            )
'''

    require(
        marker in text,
        "manual parser insertion point not found",
    )

    text = text.replace(
        marker,
        parser + marker,
        1,
    )

    text = replace_once(
        text,
        "    cases = _parse_batch_table(lines, batch_index)\n"
        "    _validate_cases(cases, repo_root)\n",
        "    cases = _parse_batch_table(lines, batch_index)\n"
        "    manual_cases = _parse_manual_table(\n"
        "        lines,\n"
        "        manual_index,\n"
        "    )\n"
        "    _validate_cases(cases, repo_root)\n"
        "    _validate_manual_cases(manual_cases)\n",
        label="load_suite manual validation",
    )

    text = replace_once(
        text,
        "        batch_cases=cases,\n"
        "    )\n",
        "        batch_cases=cases,\n"
        "        manual_cases=manual_cases,\n"
        "    )\n",
        label="SuiteSpec manual cases",
    )

    return text


def render_test_file() -> str:
    return '''from pathlib import Path

import pytest

from factory.quality.case_regression_suite import (
    CaseResult,
    SuiteContractError,
    load_suite,
    run_suite,
)


def _write_suite(
    tmp_path: Path,
    manual_table: str,
) -> Path:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    (tests_dir / "test_synthetic_batch.py").write_text(
        "def test_synthetic_batch():\\n"
        "    assert True\\n",
        encoding="utf-8",
    )

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    source = docs_dir / "CASE_REGRESSION_SUITE.md"

    source.write_text(
        "# CASE-TESTY — Synthetic Canonical Regression Suite\\n\\n"
        "## TESTY BATCHOWE\\n\\n"
        "| ID | Pytest node | Description |\\n"
        "|---|---|---|\\n"
        "| CASE-BATCH-SYN | "
        "tests/test_synthetic_batch.py | "
        "Synthetic batch |\\n\\n"
        "## TESTY RĘCZNE / PRODUCT SMOKE\\n\\n"
        "Synthetic repository-backed manual checks.\\n\\n"
        + manual_table
        + "\\n",
        encoding="utf-8",
    )

    return source


def _valid_manual_table() -> str:
    return (
        "| ID | Authority | Synthetic stimulus | "
        "Acceptance criteria |\\n"
        "|---|---|---|---|\\n"
        "| CASE-MANUAL-001 | SYN-AUTH-1 | "
        "SYN-STIMULUS-1 | Synthetic acceptance 1 |\\n"
        "| CASE-MANUAL-002 | SYN-AUTH-2 | "
        "SYN-STIMULUS-2 | Synthetic acceptance 2 |"
    )


def test_manual_inventory_is_structurally_parsed(
    tmp_path: Path,
) -> None:
    spec = load_suite(
        _write_suite(
            tmp_path,
            _valid_manual_table(),
        ),
        repo_root=tmp_path,
    )

    assert [
        case.test_id
        for case in spec.manual_cases
    ] == [
        "CASE-MANUAL-001",
        "CASE-MANUAL-002",
    ]

    assert (
        spec.manual_cases[0].authority
        == "SYN-AUTH-1"
    )


def test_duplicate_manual_ids_fail_closed(
    tmp_path: Path,
) -> None:
    table = (
        "| ID | Authority | Synthetic stimulus | "
        "Acceptance criteria |\\n"
        "|---|---|---|---|\\n"
        "| CASE-MANUAL-001 | A | S1 | C1 |\\n"
        "| CASE-MANUAL-001 | B | S2 | C2 |"
    )

    with pytest.raises(
        SuiteContractError,
        match="duplicate manual IDs",
    ):
        load_suite(
            _write_suite(tmp_path, table),
            repo_root=tmp_path,
        )


def test_manual_table_requires_exact_columns(
    tmp_path: Path,
) -> None:
    table = (
        "| ID | Authority | Acceptance criteria |\\n"
        "|---|---|---|\\n"
        "| CASE-MANUAL-001 | A | C |"
    )

    with pytest.raises(
        SuiteContractError,
        match="manual table columns must be exactly",
    ):
        load_suite(
            _write_suite(tmp_path, table),
            repo_root=tmp_path,
        )


def test_manual_table_rejects_empty_required_field(
    tmp_path: Path,
) -> None:
    table = (
        "| ID | Authority | Synthetic stimulus | "
        "Acceptance criteria |\\n"
        "|---|---|---|---|\\n"
        "| CASE-MANUAL-001 | A |  | C |"
    )

    with pytest.raises(
        SuiteContractError,
        match="manual table fields must be non-empty",
    ):
        load_suite(
            _write_suite(tmp_path, table),
            repo_root=tmp_path,
        )


def test_malformed_manual_row_fails_closed(
    tmp_path: Path,
) -> None:
    table = (
        "| ID | Authority | Synthetic stimulus | "
        "Acceptance criteria |\\n"
        "|---|---|---|---|\\n"
        "| CASE-MANUAL-001 | A | S |"
    )

    with pytest.raises(
        SuiteContractError,
        match=(
            "every manual table row must have "
            "exactly four columns"
        ),
    ):
        load_suite(
            _write_suite(tmp_path, table),
            repo_root=tmp_path,
        )


def test_invalid_manual_id_fails_closed(
    tmp_path: Path,
) -> None:
    table = (
        "| ID | Authority | Synthetic stimulus | "
        "Acceptance criteria |\\n"
        "|---|---|---|---|\\n"
        "| bad manual id | A | S | C |"
    )

    with pytest.raises(
        SuiteContractError,
        match="invalid manual ID",
    ):
        load_suite(
            _write_suite(tmp_path, table),
            repo_root=tmp_path,
        )


def test_manual_inventory_remains_non_executable(
    tmp_path: Path,
) -> None:
    executed: list[str] = []

    def fake_executor(case, repo_root):
        del repo_root

        executed.append(case.test_id)

        return CaseResult(
            test_id=case.test_id,
            pytest_node=case.pytest_node,
            status="PASS",
            exit_code=0,
            reason="synthetic PASS",
        )

    report = run_suite(
        _write_suite(
            tmp_path,
            _valid_manual_table(),
        ),
        repo_root=tmp_path,
        executor=fake_executor,
    )

    payload = report.to_dict()

    assert report.status == "PASS"
    assert executed == ["CASE-BATCH-SYN"]
    assert payload["executed_tests"] == [
        "CASE-BATCH-SYN"
    ]
    assert payload["manual_product_smoke"] == "SKIPPED"
'''
