"""H4 canonical-assurance gate for Operation Contract v1 regression coverage."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
SUITE_PATH = REPO_ROOT / "docs" / "CASE_REGRESSION_SUITE.md"
_OPERATION_TEST_GLOB = "test_operation_*_v1.py"
_BATCH_NODE_PATTERN = re.compile(r"\|\s*CASE-BATCH-[^|]+\|\s*(tests/[^|]+\.py(?:\:\:[^|]+)?)\s*\|")


def _declared_test_files() -> set[str]:
    text = SUITE_PATH.read_text(encoding="utf-8")
    return {match.split("::", 1)[0] for match in _BATCH_NODE_PATTERN.findall(text)}


def test_every_operation_contract_test_file_is_canonical_batch_covered() -> None:
    operation_tests = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "tests").glob(_OPERATION_TEST_GLOB)
    }
    declared = _declared_test_files()
    missing = sorted(operation_tests - declared)
    assert not missing, f"operation contract tests missing from canonical batch SOT: {missing}"


def test_h4_assurance_gate_is_itself_canonical_batch_covered() -> None:
    assert "tests/test_h4_operation_contract_assurance.py" in _declared_test_files()
