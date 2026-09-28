from pathlib import Path

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.live_observer import observe_portfolio


def _manifest(tmp_path: Path) -> Path:
    path = tmp_path / "live.yaml"
    path.write_text(
        """
ttl_seconds: 60
projects:
  - project_id: A
    repository: owner/a
    main_ref: refs/heads/main
    task_id: TASK-A
    closure_percent: 50
    risk_class: R1
    candidate_ref: refs/pull/7/head
    candidate_base_sha: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    blockers: []
    evidence_refs: [github:pr7]
""".strip(),
        encoding="utf-8",
    )
    return path


def test_observer_resolves_live_main_and_candidate(tmp_path: Path) -> None:
    values = {
        ("owner/a", "refs/heads/main"): "b" * 40,
        ("owner/a", "refs/pull/7/head"): "c" * 40,
    }
    snapshot = observe_portfolio(
        _manifest(tmp_path),
        resolver=lambda repository, ref: values[(repository, ref)],
        now_epoch=10,
    )
    project = snapshot.projects[0]
    assert project.main_sha == "b" * 40
    assert project.candidate_sha == "c" * 40
    assert project.candidate_stale
    assert snapshot.expires_at_epoch == 70


def test_observer_fails_closed_when_candidate_pair_is_partial(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
ttl_seconds: 60
projects:
  - project_id: A
    repository: owner/a
    main_ref: refs/heads/main
    task_id: TASK-A
    closure_percent: 50
    risk_class: R1
    candidate_ref: refs/pull/7/head
    blockers: []
    evidence_refs: [github:pr7]
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(NightShiftContractError, match="must appear together"):
        observe_portfolio(
            path,
            resolver=lambda repository, ref: "b" * 40,
            now_epoch=10,
        )
