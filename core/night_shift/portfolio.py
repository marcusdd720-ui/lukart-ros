"""Live multi-project portfolio state."""

from __future__ import annotations

from dataclasses import dataclass

from core.p3.contracts import content_digest

from .contracts import NightShiftContractError, RiskClass, require_git_oid


@dataclass(frozen=True, slots=True)
class ProjectState:
    project_id: str
    repository: str
    main_sha: str
    task_id: str
    closure_percent: int
    risk_class: RiskClass
    candidate_sha: str | None = None
    candidate_base_sha: str | None = None
    blockers: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.project_id.strip() or not self.repository.strip() or not self.task_id.strip():
            raise NightShiftContractError("project state identity is required")
        if not 0 <= self.closure_percent <= 100:
            raise NightShiftContractError("closure_percent must be within 0..100")
        object.__setattr__(self, "main_sha", require_git_oid(self.main_sha, field_name="main_sha"))
        if (self.candidate_sha is None) != (self.candidate_base_sha is None):
            raise NightShiftContractError("candidate sha/base must appear together")
        if self.candidate_sha is not None:
            object.__setattr__(
                self,
                "candidate_sha",
                require_git_oid(self.candidate_sha, field_name="candidate_sha"),
            )
            object.__setattr__(
                self,
                "candidate_base_sha",
                require_git_oid(self.candidate_base_sha or "", field_name="candidate_base_sha"),
            )
        refs = tuple(sorted({x.strip() for x in self.evidence_refs}))
        if not refs or any(not x for x in refs):
            raise NightShiftContractError("project state requires evidence")
        object.__setattr__(self, "evidence_refs", refs)

    @property
    def candidate_stale(self) -> bool:
        return self.candidate_base_sha is not None and self.candidate_base_sha != self.main_sha

    @property
    def ready(self) -> bool:
        return not self.blockers and not self.candidate_stale


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    snapshot_id: str
    observed_at_epoch: int
    expires_at_epoch: int
    projects: tuple[ProjectState, ...]

    def __post_init__(self) -> None:
        if (
            not self.snapshot_id.strip()
            or self.observed_at_epoch < 0
            or self.expires_at_epoch <= self.observed_at_epoch
        ):
            raise NightShiftContractError("invalid portfolio snapshot")
        ids = [x.project_id for x in self.projects]
        repos = [x.repository for x in self.projects]
        if len(ids) != len(set(ids)) or len(repos) != len(set(repos)):
            raise NightShiftContractError("portfolio identities must be unique")

    def require_fresh(self, *, now_epoch: int) -> None:
        if now_epoch < self.observed_at_epoch or now_epoch >= self.expires_at_epoch:
            raise NightShiftContractError("portfolio snapshot is stale")

    def digest(self) -> str:
        return content_digest(
            {
                "snapshot_id": self.snapshot_id,
                "observed_at_epoch": self.observed_at_epoch,
                "expires_at_epoch": self.expires_at_epoch,
                "projects": [
                    {
                        "project_id": x.project_id,
                        "repository": x.repository,
                        "main_sha": x.main_sha,
                        "task_id": x.task_id,
                        "closure_percent": x.closure_percent,
                        "risk_class": x.risk_class.value,
                        "candidate_sha": x.candidate_sha,
                        "candidate_base_sha": x.candidate_base_sha,
                        "blockers": list(x.blockers),
                        "evidence_refs": list(x.evidence_refs),
                    }
                    for x in self.projects
                ],
            }
        )
