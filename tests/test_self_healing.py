from pathlib import Path

from factory.self_healing import diagnose_failure, semantic_fingerprint


def test_failure_diagnosis_identifies_semantic_test_failures() -> None:
    diagnosis = diagnose_failure("FAILED tests/test_example.py::test_value - AssertionError")
    assert diagnosis.category == "test"
    assert diagnosis.semantic_failure is True


def test_failure_diagnosis_identifies_quality_repairs() -> None:
    diagnosis = diagnose_failure("ruff check found 1 error and can fix it")
    assert diagnosis.category == "quality"
    assert diagnosis.repairable_by_ruff is True
    assert diagnosis.semantic_failure is False


def test_semantic_fingerprint_ignores_python_formatting_only(tmp_path: Path) -> None:
    module = tmp_path / "example.py"
    module.write_text("x = 1\n\nprint(x)\n", encoding="utf-8")
    before = semantic_fingerprint(tmp_path)
    module.write_text("x=1\nprint(x)\n", encoding="utf-8")
    after = semantic_fingerprint(tmp_path)
    assert before == after


def test_semantic_fingerprint_changes_when_python_ast_changes(tmp_path: Path) -> None:
    module = tmp_path / "example.py"
    module.write_text("x = 1\n", encoding="utf-8")
    before = semantic_fingerprint(tmp_path)
    module.write_text("x = 2\n", encoding="utf-8")
    after = semantic_fingerprint(tmp_path)
    assert before != after
