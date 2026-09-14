from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.repository_critical_path_gate import validate_critical_paths


def test_accepts_exact_files_and_nonempty_subtrees(tmp_path: Path) -> None:
    (tmp_path / "SECURITY.md").write_text("policy\n", encoding="utf-8")
    ledger = tmp_path / "core" / "case_ledger"
    ledger.mkdir(parents=True)
    (ledger / "__init__.py").write_text("# ledger\n", encoding="utf-8")
    evidence = validate_critical_paths(
        tmp_path,
        ["SECURITY.md", "core/case_ledger/**"],
    )
    assert evidence["exact_files"] == ["SECURITY.md"]
    assert evidence["subtrees"] == ["core/case_ledger/**"]


def test_rejects_missing_exact_artifact(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="exact artifact is missing"):
        validate_critical_paths(tmp_path, ["docs/REPOSITORY_GOVERNANCE.md"])


def test_rejects_missing_subtree(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="subtree is missing"):
        validate_critical_paths(tmp_path, ["core/case_ledger/**"])


def test_rejects_empty_subtree(tmp_path: Path) -> None:
    (tmp_path / "core" / "case_ledger").mkdir(parents=True)
    with pytest.raises(RuntimeError, match="no tracked files"):
        validate_critical_paths(tmp_path, ["core/case_ledger/**"])


def test_rejects_repository_escape(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="escapes repository"):
        validate_critical_paths(tmp_path, ["../outside.txt"])


def test_rejects_duplicate_inventory(tmp_path: Path) -> None:
    (tmp_path / "SECURITY.md").write_text("policy\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="duplicates"):
        validate_critical_paths(tmp_path, ["SECURITY.md", "SECURITY.md"])


def test_canonical_inventory_tracks_real_ledger_package_and_governance_enforcers() -> None:
    root = Path(__file__).resolve().parents[1]
    policy = json.loads(
        (root / "config" / "enterprise_v1.json").read_text(encoding="utf-8")
    )
    critical_paths = set(
        policy["h2_repository_policy"]["review_integrity"]["critical_paths"]
    )
    assert "core/case_ledger/**" in critical_paths
    assert "core/case_ledger.py" not in critical_paths
    assert {
        "scripts/repository_critical_path_gate.py",
        "scripts/solo_maintainer_governance_gate.py",
        "tests/test_repository_critical_path_gate.py",
        "tests/test_solo_maintainer_governance_gate.py",
        "docs/WORKING_PRINCIPLES.md",
        "docs/REPOSITORY_GOVERNANCE.md",
    } <= critical_paths


def test_current_canonical_inventory_resolves_on_repository() -> None:
    root = Path(__file__).resolve().parents[1]
    policy = json.loads(
        (root / "config" / "enterprise_v1.json").read_text(encoding="utf-8")
    )
    critical_paths = policy["h2_repository_policy"]["review_integrity"]["critical_paths"]
    evidence = validate_critical_paths(root, critical_paths)
    assert evidence["critical_paths"] == len(critical_paths)
