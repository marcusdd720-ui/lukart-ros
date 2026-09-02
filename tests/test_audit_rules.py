"""Tests for RQM audit rules."""

from pathlib import Path

from factory.rqm.audit.rules import *


def test_duplicate_file_rule(tmp_path: Path):
    rule = DuplicateFileRule()
    (tmp_path / "a.txt").write_text("identical content")
    (tmp_path / "b.txt").write_text("identical content")

    findings = rule.check(tmp_path)
    assert len(findings) == 1


def test_large_file_rule(tmp_path: Path):
    rule = LargeFileRule()
    rule.max_bytes = 100

    (tmp_path / "small.txt").write_text("hello")
    (tmp_path / "large.txt").write_text("x" * 200)

    findings = rule.check(tmp_path)
    assert len(findings) == 1
    finding_file = findings[0].file
    assert finding_file is not None
    assert "large.txt" in finding_file
