from __future__ import annotations

from pathlib import Path

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.environment import collect_environment_fingerprint


def test_environment_fingerprint_binds_lockfiles_and_runtime(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "uv.lock").write_text("lock-a\n", encoding="utf-8")
    (repo / "pylock.toml").write_text("lock-b\n", encoding="utf-8")

    fingerprint = collect_environment_fingerprint(
        repository=repo,
        policy_version="night-shift-policy/v2",
        timezone_probe="UTC",
    )

    assert fingerprint.python_version
    assert fingerprint.system
    assert fingerprint.git_version.startswith("git version ")
    assert [item.path for item in fingerprint.lockfiles] == ["pylock.toml", "uv.lock"]
    assert all(len(item.sha256) == 64 for item in fingerprint.lockfiles)
    assert isinstance(fingerprint.iana_timezone_available, bool)
    assert len(fingerprint.digest()) == 64
def test_lockfile_change_changes_environment_digest(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    lock = repo / "uv.lock"
    lock.write_text("v1\n", encoding="utf-8")

    first = collect_environment_fingerprint(
        repository=repo,
        policy_version="v2",
        timezone_probe="UTC",
    )
    lock.write_text("v2\n", encoding="utf-8")
    second = collect_environment_fingerprint(
        repository=repo,
        policy_version="v2",
        timezone_probe="UTC",
    )

    assert first.digest() != second.digest()


def test_missing_lockfiles_fail_closed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(NightShiftContractError, match="no declared dependency lockfile"):
        collect_environment_fingerprint(
            repository=repo,
            policy_version="v2",
        )
def test_lockfile_escape_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "outside.lock").write_text("outside\n", encoding="utf-8")

    with pytest.raises(NightShiftContractError, match="escaped repository"):
        collect_environment_fingerprint(
            repository=repo,
            policy_version="v2",
            lockfile_names=("../outside.lock",),
        )
