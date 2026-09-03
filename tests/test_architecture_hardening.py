"""Adversarial regression tests for architecture boundaries and local evidence."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.import_manager import ImportManager
from core.local_case_store import PrivacyViolation, validate_case_key


def test_symlink_import_is_rejected(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    manager = ImportManager(str(data_root))
    case_path = manager.data_root / "cases" / "CASE-0001"
    (case_path / "original").mkdir(parents=True)
    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "outside.txt"
    target.write_text("private", encoding="utf-8")
    (source / "linked.txt").symlink_to(target)

    with pytest.raises(ValueError, match="Symlink"):
        manager.import_directory("CASE-0001", str(source))


def test_case_key_traversal_is_rejected() -> None:
    with pytest.raises(PrivacyViolation):
        validate_case_key("../../outside")
