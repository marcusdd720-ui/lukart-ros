"""
Tests for RQM Audit Rules (Sprint P1.1)
"""

from pathlib import Path

from factory.rqm.audit.rules import (
    ALL_RULES,
    DuplicateFileRule,
    EmptyDirectoryRule,
    GitignoreRule,
    InitRule,
    LargeFileRule,
    LicenseRule,
    PyprojectRule,
    ReadmeRule,
    TodoRule,
    WorkflowRule,
)


def test_all_rules_export_count():
    assert len(ALL_RULES) == 10


def test_readme_rule(tmp_path: Path):
    rule = ReadmeRule()
    assert len(rule.check(tmp_path)) == 1

    (tmp_path / "README.md").write_text("# Test")
    assert len(rule.check(tmp_path)) == 0


def test_license_rule(tmp_path: Path):
    rule = LicenseRule()
    assert len(rule.check(tmp_path)) == 1

    (tmp_path / "LICENSE").write_text("MIT")
    assert len(rule.check(tmp_path)) == 0


def test_gitignore_rule(tmp_path: Path):
    rule = GitignoreRule()
    assert len(rule.check(tmp_path)) == 1

    (tmp_path / ".gitignore").write_text("*.pyc")
    assert len(rule.check(tmp_path)) == 0


def test_workflow_rule(tmp_path: Path):
    rule = WorkflowRule()
    assert len(rule.check(tmp_path)) == 1

    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "ci.yml").write_text("name: CI")
    assert len(rule.check(tmp_path)) == 0


def test_pyproject_rule(tmp_path: Path):
    rule = PyprojectRule()
    assert len(rule.check(tmp_path)) == 1

    (tmp_path / "pyproject.toml").write_text("[build-system]")
    assert len(rule.check(tmp_path)) == 0


def test_init_rule(tmp_path: Path):
    rule = InitRule()
    pkg = tmp_path / "mypackage"
    pkg.mkdir()
    (pkg / "module.py").write_text("x = 1")

    findings = rule.check(tmp_path)
    assert len(findings) == 1
    assert "mypackage" in findings[0].message

    (pkg / "__init__.py").write_text("")
    assert len(rule.check(tmp_path)) == 0


def test_empty_directory_rule(tmp_path: Path):
    rule = EmptyDirectoryRule()
    empty_dir = tmp_path / "empty_folder"
    empty_dir.mkdir()

    findings = rule.check(tmp_path)
    assert len(findings) == 1

    (empty_dir / "file.txt").write_text("data")
    assert len(rule.check(tmp_path)) == 0


def test_todo_rule(tmp_path: Path):
    rule = TodoRule()
    code_file = tmp_path / "main.py"
    code_file.write_text("# TODO: fix this bug\nprint('hello')\n")

    findings = rule.check(tmp_path)
    assert len(findings) == 1
    assert findings[0].line == 1


def test_duplicate_file_rule(tmp_path: Path):
    rule = DuplicateFileRule()
    (tmp_path / "a.txt").write_text("identical content")
    (tmp_path / "b.txt").write_text("identical content")

    findings = rule.check(tmp_path)
    assert len(findings) == 1


def test_large_file_rule(tmp_path: Path):
    rule = LargeFileRule()
    rule.max_bytes = 100  # Obniżony próg dla testu

    (tmp_path / "small.txt").write_text("hello")
    (tmp_path / "large.txt").write_text("x" * 200)

    findings = rule.check(tmp_path)
    assert len(findings) == 1
    finding_file = findings[0].file
    assert finding_file is not None
    assert "large.txt" in finding_file
