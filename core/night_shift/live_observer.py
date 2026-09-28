"""Live portfolio observation for Shadow Night Shift."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from time import time

import yaml

from core.p3.contracts import content_digest

from .config_validation import (
    require_nonnegative_int,
    require_string,
    require_string_list,
)
from .contracts import NightShiftContractError, RiskClass, require_git_oid
from .portfolio import PortfolioSnapshot, ProjectState

GitRefResolver = Callable[[str, str], str]


def _optional_string_list(value: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise NightShiftContractError(f"{field_name} must be a list of strings")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise NightShiftContractError(f"{field_name} must contain nonblank strings")
        out.append(item.strip())
    return tuple(out)


def resolve_git_ref(repository: str, ref: str) -> str:
    repository = repository.strip()
    ref = ref.strip()
    if not repository or not ref:
        raise NightShiftContractError("repository and ref are required")
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    completed = subprocess.run(
        ["git", "ls-remote", f"https://github.com/{repository}.git", ref],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    if completed.returncode != 0:
        raise NightShiftContractError(
            f"git ref observation failed for {repository}:{ref}"
        )
    rows = [line.split() for line in completed.stdout.splitlines() if line.strip()]
    if len(rows) != 1 or len(rows[0]) < 2 or rows[0][1] != ref:
        raise NightShiftContractError(
            f"git ref observation is not unique for {repository}:{ref}"
        )
    return require_git_oid(rows[0][0], field_name="observed_git_ref")


def observe_portfolio(
    path: str | Path,
    *,
    resolver: GitRefResolver = resolve_git_ref,
    now_epoch: int | None = None,
) -> PortfolioSnapshot:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("projects"), list):
        raise NightShiftContractError("live input manifest must contain projects")
    observed_at = int(time()) if now_epoch is None else now_epoch
    if observed_at < 0:
        raise NightShiftContractError("now_epoch cannot be negative")
    ttl = require_nonnegative_int(raw.get("ttl_seconds"), field_name="ttl_seconds")
    if ttl < 1:
        raise NightShiftContractError("ttl_seconds must be positive")

    projects: list[ProjectState] = []
    evidence: list[dict[str, object]] = []
    for item in raw["projects"]:
        if not isinstance(item, dict):
            raise NightShiftContractError("live project input must be a mapping")
        project_id = require_string(item.get("project_id"), field_name="project_id")
        repository = require_string(item.get("repository"), field_name="repository")
        task_id = require_string(item.get("task_id"), field_name="task_id")
        main_ref = require_string(item.get("main_ref"), field_name="main_ref")
        main_sha = resolver(repository, main_ref)

        candidate_ref_raw = item.get("candidate_ref")
        candidate_base_raw = item.get("candidate_base_sha")
        if (candidate_ref_raw is None) != (candidate_base_raw is None):
            raise NightShiftContractError(
                "candidate_ref and candidate_base_sha must appear together"
            )
        candidate_sha = None
        candidate_base_sha = None
        if candidate_ref_raw is not None:
            candidate_ref = require_string(candidate_ref_raw, field_name="candidate_ref")
            candidate_sha = resolver(repository, candidate_ref)
            candidate_base_sha = require_git_oid(
                require_string(candidate_base_raw, field_name="candidate_base_sha"),
                field_name="candidate_base_sha",
            )

        blockers = _optional_string_list(item.get("blockers", []), field_name="blockers")
        refs = require_string_list(item.get("evidence_refs"), field_name="evidence_refs")
        refs = tuple(sorted(set(refs + (f"git:{repository}:{main_ref}:{main_sha}",))))
        project = ProjectState(
            project_id=project_id,
            repository=repository,
            main_sha=main_sha,
            task_id=task_id,
            closure_percent=require_nonnegative_int(
                item.get("closure_percent"), field_name="closure_percent"
            ),
            risk_class=RiskClass(
                require_string(item.get("risk_class"), field_name="risk_class")
            ),
            candidate_sha=candidate_sha,
            candidate_base_sha=candidate_base_sha,
            blockers=blockers,
            evidence_refs=refs,
        )
        projects.append(project)
        evidence.append(
            {
                "project_id": project.project_id,
                "main_sha": project.main_sha,
                "candidate_sha": project.candidate_sha,
                "candidate_base_sha": project.candidate_base_sha,
            }
        )

    snapshot_id = "live-" + content_digest(
        {"observed_at_epoch": observed_at, "projects": evidence}
    )[:16]
    return PortfolioSnapshot(
        snapshot_id=snapshot_id,
        observed_at_epoch=observed_at,
        expires_at_epoch=observed_at + ttl,
        projects=tuple(projects),
    )
