from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.dead_code_gate import inventory_digest

ROOT = Path(__file__).resolve().parents[1]


def test_pytest_configuration_has_single_ssot() -> None:
    assert not (ROOT / "pytest.ini").exists()
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.pytest.ini_options]" in pyproject
    assert 'testpaths = ["tests"]' in pyproject
    assert 'pythonpath = ["."]' in pyproject


def test_unreferenced_inventory_is_not_labeled_dead_code() -> None:
    source = (ROOT / "scripts" / "dead_code_gate.py").read_text(encoding="utf-8")
    assert "INVENTORY_NOT_DEAD_CODE_PROOF" in source
    assert 'print("DEAD_CODE_INVENTORY")' not in source


def test_unreferenced_inventory_digest_is_deterministic() -> None:
    modules = ["alpha", "beta.gamma"]
    expected = hashlib.sha256(b"alpha\nbeta.gamma").hexdigest()
    assert inventory_digest(modules) == expected


def test_hardcore_roadmap_is_historical_not_active() -> None:
    roadmap = (ROOT / "docs" / "HARDCORE_ROADMAP.md").read_text(encoding="utf-8")
    assert "Status: Historical CLOSED / ENGINEERING PASS" in roadmap
    assert "Status: Active development roadmap" not in roadmap
