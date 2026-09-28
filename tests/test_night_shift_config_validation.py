from pathlib import Path

import pytest

from core.night_shift.contracts import NightShiftContractError
from core.night_shift.executor_registry import load_executor_profiles
from core.night_shift.project_registry import load_project_registry
from core.night_shift.runtime_profiles import load_runtime_profiles


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_executor_registry_rejects_string_boolean(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "executors.yaml",
        """
executors:
  - executor_id: bad
    capabilities: [git]
    mutating: false
    independent_review: false
    cost_rank: 0
    enabled: "false"
    requires_local_writer: false
    heavy_compute: false
    max_parallel: 1
""".strip(),
    )
    with pytest.raises(NightShiftContractError, match="enabled must be a boolean"):
        load_executor_profiles(path)


def test_project_registry_rejects_string_boolean(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "projects.yaml",
        """
projects:
  - project_id: BAD
    repository: owner/repo
    priority: 0
    default_risk_class: R1
    required_capabilities: [git]
    mutating: "false"
""".strip(),
    )
    with pytest.raises(NightShiftContractError, match="mutating must be a boolean"):
        load_project_registry(path)


def test_runtime_registry_rejects_string_boolean(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "runtimes.yaml",
        """
runtimes:
  - runtime_id: bad
    adapter: bad
    evidence: VALIDATED
    crash_resume: "true"
    idempotent_steps: true
    deterministic_replay: false
    durable_timers: false
    distributed_workers: false
    requires_external_service: false
    operational_rank: 0
    source_refs: [test:bad]
""".strip(),
    )
    with pytest.raises(NightShiftContractError, match="crash_resume must be a boolean"):
        load_runtime_profiles(path)


def test_executor_registry_rejects_non_list_capabilities(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "executors.yaml",
        """
executors:
  - executor_id: bad
    capabilities: git
    mutating: false
    independent_review: false
    cost_rank: 0
    enabled: true
    requires_local_writer: false
    heavy_compute: false
    max_parallel: 1
""".strip(),
    )
    with pytest.raises(NightShiftContractError, match="capabilities must be a list"):
        load_executor_profiles(path)


def test_executor_registry_rejects_null_identity(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "executors-null.yaml",
        """
executors:
  - executor_id:
    capabilities: [git]
    mutating: false
    independent_review: false
    cost_rank: 0
    enabled: true
    requires_local_writer: false
    heavy_compute: false
    max_parallel: 1
""".strip(),
    )
    with pytest.raises(NightShiftContractError, match="executor_id must be a nonblank string"):
        load_executor_profiles(path)
