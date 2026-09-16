"""Bounded CASE-TESTY signed authoring operations.

Repository-controlled synthetic-only authoring.
Never writes directly to main and never merges pull requests.
"""

from __future__ import annotations

import argparse
import base64
import os
import subprocess
import urllib.parse
from pathlib import Path

from factory.github_actions_client import (
    GitHubActionsClient,
    GitHubActionsError,
)


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


def run_command(command: list[str], *, cwd: Path) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        output = (result.stdout + "\n" + result.stderr).strip()
        raise SignedAuthoringError(
            f"command failed ({result.returncode}): "
            f"{' '.join(command)}\n{output}"
        )


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


def verify_commit(
    client: GitHubActionsClient,
    sha: str,
) -> None:
    commit = client._api(
        "GET",
        f"/repos/{client.repository}/commits/{sha}",
    )

    verification = (
        commit
        .get("commit", {})
        .get("verification", {})
    )

    if verification.get("verified") is not True:
        raise SignedAuthoringError(
            "authoring commit is not verified: "
            f"{sha} "
            f"({verification.get('reason')})"
        )


def put_file(
    client: GitHubActionsClient,
    *,
    branch: str,
    path: str,
    content: str,
    message: str,
    existing_sha: str | None = None,
) -> str:
    body = {
        "message": message,
        "content": base64.b64encode(
            content.encode("utf-8")
        ).decode("ascii"),
        "branch": branch,
    }

    if existing_sha is not None:
        body["sha"] = existing_sha

    quoted_path = urllib.parse.quote(
        path,
        safe="/",
    )

    result = client._api(
        "PUT",
        (
            f"/repos/{client.repository}"
            f"/contents/{quoted_path}"
        ),
        body=body,
    )

    commit = result.get("commit")

    require(
        isinstance(commit, dict),
        f"GitHub returned no commit for {path}",
    )

    sha = commit.get("sha")

    require(
        isinstance(sha, str)
        and len(sha) == 40,
        f"invalid commit SHA for {path}",
    )

    verify_commit(client, sha)

    return sha


def delete_branch_best_effort(
    client: GitHubActionsClient,
    branch: str,
) -> None:
    try:
        quoted_branch = urllib.parse.quote(
            branch,
            safe="/",
        )

        client._api(
            "DELETE",
            (
                f"/repos/{client.repository}"
                f"/git/refs/heads/{quoted_branch}"
            ),
        )
    except Exception:
        pass


def create_pull_request(
    client: GitHubActionsClient,
    *,
    branch: str,
) -> dict:
    return client._api(
        "POST",
        f"/repos/{client.repository}/pulls",
        body={
            "title": (
                "case-testy: validate manual "
                "product smoke inventory"
            ),
            "body": (
                "Closes #295\n\n"
                "Generated by the bounded CASE-TESTY "
                "signed-authoring operation bootstrapped "
                "in #296.\n\n"
                "- validates canonical manual/product-smoke "
                "structure\n"
                "- preserves CASE-BATCH-001..008 execution "
                "semantics\n"
                "- preserves manual_product_smoke=SKIPPED\n"
                "- synthetic-only scope\n"
                "- no automatic merge"
            ),
            "head": branch,
            "base": MAIN_BRANCH,
            "draft": False,
        },
    )


def harden_manual_smoke_inventory(
    repo_root: Path,
) -> None:
    client = GitHubActionsClient.from_environment()

    require(
        client.repository
        == os.environ.get("GITHUB_REPOSITORY"),
        "repository identity mismatch",
    )

    expected_base = os.environ.get(
        "GITHUB_SHA",
        "",
    ).strip()

    require(
        len(expected_base) == 40,
        "GITHUB_SHA is missing or invalid",
    )

    main_ref = client._api(
        "GET",
        (
            f"/repos/{client.repository}"
            f"/git/ref/heads/{MAIN_BRANCH}"
        ),
    )

    live_base = (
        main_ref
        .get("object", {})
        .get("sha")
    )

    require(
        live_base == expected_base,
        (
            "main moved before authoring: "
            f"expected={expected_base} "
            f"live={live_base}"
        ),
    )

    source_path = (
        repo_root
        / "factory/quality/case_regression_suite.py"
    )

    test_path = (
        repo_root
        / "tests/case/"
        "test_case_regression_suite_manual_inventory.py"
    )

    require(
        source_path.is_file(),
        "canonical regression-suite module is missing",
    )

    require(
        not test_path.exists(),
        (
            "manual inventory regression test file "
            "already exists"
        ),
    )

    original = source_path.read_text(
        encoding="utf-8"
    )

    updated = render_regression_suite_update(
        original
    )

    source_path.write_text(
        updated,
        encoding="utf-8",
    )

    test_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    test_content = render_test_file()

    test_path.write_text(
        test_content,
        encoding="utf-8",
    )

    run_command(
        [
            "uv",
            "run",
            "--frozen",
            "--extra",
            "dev",
            "pytest",
            (
                "tests/case/"
                "test_case_regression_suite_"
                "manual_inventory.py"
            ),
            "-q",
        ],
        cwd=repo_root,
    )

    run_command(
        [
            "uv",
            "run",
            "--frozen",
            "--extra",
            "dev",
            "python",
            "-m",
            "factory.quality.case_regression_suite",
            "--validate-only",
        ],
        cwd=repo_root,
    )

    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )

    changed = {
        line[3:].strip()
        for line in status.stdout.splitlines()
        if len(line) >= 4
        and line[3:].strip()
    }

    require(
        changed == ALLOWED_PATHS,
        (
            "unexpected working-tree diff: "
            f"{sorted(changed)}"
        ),
    )

    quoted_branch = urllib.parse.quote(
        TARGET_BRANCH,
        safe="/",
    )

    try:
        client._api(
            "GET",
            (
                f"/repos/{client.repository}"
                f"/git/ref/heads/{quoted_branch}"
            ),
        )
    except GitHubActionsError:
        pass
    else:
        raise SignedAuthoringError(
            "target branch already exists: "
            f"{TARGET_BRANCH}"
        )

    client._api(
        "POST",
        f"/repos/{client.repository}/git/refs",
        body={
            "ref": f"refs/heads/{TARGET_BRANCH}",
            "sha": live_base,
        },
    )

    try:
        current = client._api(
            "GET",
            (
                f"/repos/{client.repository}"
                "/contents/"
                "factory/quality/"
                "case_regression_suite.py"
                f"?ref={live_base}"
            ),
        )

        current_sha = current.get("sha")

        require(
            isinstance(current_sha, str)
            and len(current_sha) == 40,
            "invalid source blob SHA",
        )

        first_commit = put_file(
            client,
            branch=TARGET_BRANCH,
            path=(
                "factory/quality/"
                "case_regression_suite.py"
            ),
            content=updated,
            message=(
                "case-testy: validate manual "
                "smoke inventory structure"
            ),
            existing_sha=current_sha,
        )

        second_commit = put_file(
            client,
            branch=TARGET_BRANCH,
            path=(
                "tests/case/"
                "test_case_regression_suite_"
                "manual_inventory.py"
            ),
            content=test_content,
            message=(
                "case-testy: add manual "
                "inventory validation tests"
            ),
        )

        compare = client._api(
            "GET",
            (
                f"/repos/{client.repository}"
                f"/compare/{MAIN_BRANCH}..."
                f"{quoted_branch}"
            ),
        )

        files = compare.get("files")

        require(
            isinstance(files, list),
            "GitHub compare returned invalid files",
        )

        remote_paths = {
            item.get("filename")
            for item in files
            if isinstance(item, dict)
            and isinstance(
                item.get("filename"),
                str,
            )
        }

        require(
            remote_paths == ALLOWED_PATHS,
            (
                "unexpected remote diff: "
                f"{sorted(remote_paths)}"
            ),
        )

        pr = create_pull_request(
            client,
            branch=TARGET_BRANCH,
        )

        number = pr.get("number")
        url = pr.get("html_url")

        require(
            isinstance(number, int)
            and number > 0,
            "GitHub returned invalid PR number",
        )

        require(
            isinstance(url, str)
            and bool(url),
            "GitHub returned invalid PR URL",
        )

        print(
            f"Created PR #{number}: {url}"
        )

        print(
            "Verified commits: "
            f"{first_commit}, "
            f"{second_commit}"
        )

    except Exception:
        delete_branch_best_effort(
            client,
            TARGET_BRANCH,
        )
        raise


def main(
    argv: list[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run one bounded CASE-TESTY "
            "signed-authoring operation."
        )
    )

    parser.add_argument(
        "operation",
        choices=(OPERATION,),
    )

    args = parser.parse_args(argv)

    if args.operation != OPERATION:
        raise SignedAuthoringError(
            "unsupported operation"
        )

    harden_manual_smoke_inventory(
        Path.cwd()
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
