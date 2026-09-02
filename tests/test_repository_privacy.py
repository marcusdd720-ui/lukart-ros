from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_public_cases_directory_contains_only_template() -> None:
    cases_root = repo_root() / "cases"
    assert cases_root.is_dir()
    entries = sorted(path.name for path in cases_root.iterdir())
    assert entries == ["_TEMPLATE"]


def test_github_mvros_workflow_has_no_user_supplied_document_root() -> None:
    workflow = (
        repo_root() / ".github" / "workflows" / "mvros-v1-operations.yml"
    ).read_text(encoding="utf-8")
    assert 'inputs:' not in workflow
    assert 'inputs.root' not in workflow
    assert "tests/fixtures/mvros_v1" in workflow


def test_publish_cannot_push_case_data() -> None:
    publish = (repo_root() / "scripts" / "publish.py").read_text(encoding="utf-8")
    assert "subprocess" not in publish
    assert "git push" not in publish
    assert "git commit" not in publish
    assert "PUBLISH BLOCKED: real case data is local-only" in publish
