from pathlib import Path

import pytest

from factory.local_case_store import PrivacyViolation, case_dir, validate_data_root


def test_case_root_is_created_outside_repository(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    data = tmp_path / "MVROS-DATA"

    resolved = validate_data_root(data, repo_root=repo)
    assert resolved == data.resolve()
    assert repo not in resolved.parents


def test_repository_subdirectory_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(PrivacyViolation):
        validate_data_root(repo / "cases", repo_root=repo)


def test_case_key_cannot_escape_local_store(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    data = tmp_path / "MVROS-DATA"

    with pytest.raises(PrivacyViolation):
        case_dir("../outside", data, repo_root=repo)


def test_case_key_cannot_contain_path_separator(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    data = tmp_path / "MVROS-DATA"

    with pytest.raises(PrivacyViolation):
        case_dir("real/case", data, repo_root=repo)
