"""Regression tests for dynamic private local case discovery."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from knowledge.models.case_registry import get_spec, registered_keys
from knowledge.models.local_case_runtime import build_local_case_workspace


ROOT = Path(__file__).resolve().parents[1]


def test_new_case_initializes_runtime_workspace(tmp_path: Path) -> None:
    data_root = tmp_path / "mvros-data"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "new_case.py"),
            "REAL_CASE_1",
            "--data-root",
            str(data_root),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    case_path = data_root / "cases" / "REAL_CASE_1"
    assert (case_path / "case.yaml").is_file()
    for folder in (
        "original",
        "extracted",
        "markdown",
        "evidence",
        "timeline",
        "reports",
        "exports",
        "outbound",
        "inbound",
        "notes",
    ):
        assert (case_path / folder).is_dir()


def test_dynamic_registry_opens_created_case(tmp_path: Path) -> None:
    data_root = tmp_path / "mvros-data"
    case_path = data_root / "cases" / "REAL_CASE_1"
    case_path.mkdir(parents=True)
    (case_path / "case.yaml").write_text(
        "id: REAL_CASE_1\ntitle: First real case\nworking_title: REAL_CASE_1\nlocal_only: true\n",
        encoding="utf-8",
    )

    assert "REAL_CASE_1" in registered_keys(data_root=data_root)
    spec = get_spec("REAL_CASE_1", data_root=data_root)
    workspace = spec.open(data_root=data_root)

    assert workspace.key == "REAL_CASE_1"
    assert workspace.case.id == "REAL_CASE_1"
    assert workspace.case.display_title() == "First real case"
    assert workspace.graph_case_id == "case:REAL_CASE_1"
    assert workspace.graph.has_node("case:REAL_CASE_1")
    assert workspace.root == data_root.resolve()


def test_dynamic_runtime_rejects_unknown_local_case(tmp_path: Path) -> None:
    data_root = tmp_path / "mvros-data"

    try:
        build_local_case_workspace("MISSING", data_root=data_root)
    except KeyError as exc:
        assert "MISSING" in str(exc)
    else:
        raise AssertionError("missing local case must be rejected")
