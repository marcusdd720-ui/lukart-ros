"""Provider-neutral contracts for the Night Shift sovereign control plane."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.p3.contracts import content_digest, require_hex_digest


class NightShiftContractError(ValueError):
    """Fail-closed violation of a Night Shift control-plane contract."""


class RiskClass(StrEnum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"


class PromotionMode(StrEnum):
    AUTO = "AUTO"
    PREAUTHORIZED = "PREAUTHORIZED"
    HUMAN = "HUMAN"
def _nonblank(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise NightShiftContractError(f"{field_name} is required")
    return normalized


def _sorted_nonblank(values: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    normalized = tuple(sorted({item.strip() for item in values}))
    if any(not item for item in normalized):
        raise NightShiftContractError(f"{field_name} cannot contain blank values")
    return normalized


def _sha(value: str, *, field_name: str) -> str:
    try:
        return require_hex_digest(value, field_name=field_name)
    except ValueError as exc:
        raise NightShiftContractError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class PolicyRef:
    policy_id: str
    version: str
    policy_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _nonblank(self.policy_id, field_name="policy_id"))
        object.__setattr__(self, "version", _nonblank(self.version, field_name="version"))
        object.__setattr__(
            self,
            "policy_digest",
            _sha(self.policy_digest, field_name="policy_digest"),
        )
    def canonical_dict(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "policy_digest": self.policy_digest,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class LiveStateSnapshot:
    snapshot_id: str
    repository: str
    branch: str
    base_sha: str
    head_sha: str
    observed_at_epoch: int
    expires_at_epoch: int
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "snapshot_id", _nonblank(self.snapshot_id, field_name="snapshot_id")
        )
        object.__setattr__(
            self, "repository", _nonblank(self.repository, field_name="repository")
        )
        object.__setattr__(self, "branch", _nonblank(self.branch, field_name="branch"))
        object.__setattr__(self, "base_sha", _sha(self.base_sha, field_name="base_sha"))
        object.__setattr__(self, "head_sha", _sha(self.head_sha, field_name="head_sha"))
        if self.observed_at_epoch < 0:
            raise NightShiftContractError("observed_at_epoch cannot be negative")
        if self.expires_at_epoch <= self.observed_at_epoch:
            raise NightShiftContractError("state snapshot expiry must follow observation")
        evidence_refs = _sorted_nonblank(self.evidence_refs, field_name="evidence_refs")
        if not evidence_refs:
            raise NightShiftContractError("state snapshot requires evidence")
        object.__setattr__(self, "evidence_refs", evidence_refs)

    def require_fresh(self, *, now_epoch: int) -> None:
        if now_epoch < self.observed_at_epoch:
            raise NightShiftContractError("current time precedes state observation")
        if now_epoch >= self.expires_at_epoch:
            raise NightShiftContractError("state snapshot is stale")
    def canonical_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "repository": self.repository,
            "branch": self.branch,
            "base_sha": self.base_sha,
            "head_sha": self.head_sha,
            "observed_at_epoch": self.observed_at_epoch,
            "expires_at_epoch": self.expires_at_epoch,
            "evidence_refs": list(self.evidence_refs),
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class TaskCapsule:
    task_id: str
    repository: str
    state_snapshot_digest: str
    policy_digest: str
    objective: str
    risk_class: RiskClass
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    acceptance_checks: tuple[str, ...]
    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", _nonblank(self.task_id, field_name="task_id"))
        object.__setattr__(
            self, "repository", _nonblank(self.repository, field_name="repository")
        )
        object.__setattr__(
            self,
            "state_snapshot_digest",
            _sha(self.state_snapshot_digest, field_name="state_snapshot_digest"),
        )
        object.__setattr__(
            self,
            "policy_digest",
            _sha(self.policy_digest, field_name="policy_digest"),
        )
        object.__setattr__(self, "objective", _nonblank(self.objective, field_name="objective"))
        allowed = _sorted_nonblank(self.allowed_paths, field_name="allowed_paths")
        forbidden = _sorted_nonblank(self.forbidden_paths, field_name="forbidden_paths")
        checks = _sorted_nonblank(self.acceptance_checks, field_name="acceptance_checks")
        if not allowed:
            raise NightShiftContractError("task requires at least one allowed path")
        if not checks:
            raise NightShiftContractError("task requires acceptance checks")
        overlap = set(allowed) & set(forbidden)
        if overlap:
            raise NightShiftContractError("allowed and forbidden paths overlap")
        object.__setattr__(self, "allowed_paths", allowed)
        object.__setattr__(self, "forbidden_paths", forbidden)
        object.__setattr__(self, "acceptance_checks", checks)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "repository": self.repository,
            "state_snapshot_digest": self.state_snapshot_digest,
            "policy_digest": self.policy_digest,
            "objective": self.objective,
            "risk_class": self.risk_class.value,
            "allowed_paths": list(self.allowed_paths),
            "forbidden_paths": list(self.forbidden_paths),
            "acceptance_checks": list(self.acceptance_checks),
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class AutonomyEnvelope:
    envelope_id: str
    issued_at_epoch: int
    expires_at_epoch: int
    repositories: tuple[str, ...]
    allowed_risk_classes: tuple[RiskClass, ...]
    max_tasks: int
    promotion_mode: PromotionMode

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "envelope_id", _nonblank(self.envelope_id, field_name="envelope_id")
        )
        if self.issued_at_epoch < 0:
            raise NightShiftContractError("issued_at_epoch cannot be negative")
        if self.expires_at_epoch <= self.issued_at_epoch:
            raise NightShiftContractError("authority expiry must follow issuance")
        repositories = _sorted_nonblank(self.repositories, field_name="repositories")
        if not repositories:
            raise NightShiftContractError("authority requires at least one repository")
        risks = tuple(sorted(set(self.allowed_risk_classes), key=lambda item: item.value))
        if not risks:
            raise NightShiftContractError("authority requires at least one risk class")
        if self.max_tasks < 1:
            raise NightShiftContractError("max_tasks must be positive")
        if self.promotion_mode is PromotionMode.AUTO and any(
            risk not in {RiskClass.R0, RiskClass.R1} for risk in risks
        ):
            raise NightShiftContractError(
                "automatic promotion authority cannot include R2/R3/R4"
            )
        object.__setattr__(self, "repositories", repositories)
        object.__setattr__(self, "allowed_risk_classes", risks)

    def require_authorized(
        self,
        *,
        repository: str,
        risk_class: RiskClass,
        now_epoch: int,
    ) -> None:
        if now_epoch < self.issued_at_epoch:
            raise NightShiftContractError("current time precedes authority issuance")
        if now_epoch >= self.expires_at_epoch:
            raise NightShiftContractError("authority envelope expired")
        if repository not in self.repositories:
            raise NightShiftContractError("repository outside authority envelope")
        if risk_class not in self.allowed_risk_classes:
            raise NightShiftContractError("risk class outside authority envelope")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "envelope_id": self.envelope_id,
            "issued_at_epoch": self.issued_at_epoch,
            "expires_at_epoch": self.expires_at_epoch,
            "repositories": list(self.repositories),
            "allowed_risk_classes": [item.value for item in self.allowed_risk_classes],
            "max_tasks": self.max_tasks,
            "promotion_mode": self.promotion_mode.value,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class ExecutionDecision:
    decision_id: str
    policy_ref_digest: str
    state_snapshot_digest: str
    task_capsule_digest: str
    autonomy_envelope_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "decision_id", _nonblank(self.decision_id, field_name="decision_id")
        )
        for field_name in (
            "policy_ref_digest",
            "state_snapshot_digest",
            "task_capsule_digest",
            "autonomy_envelope_digest",
        ):
            object.__setattr__(
                self,
                field_name,
                _sha(getattr(self, field_name), field_name=field_name),
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "policy_ref_digest": self.policy_ref_digest,
            "state_snapshot_digest": self.state_snapshot_digest,
            "task_capsule_digest": self.task_capsule_digest,
            "autonomy_envelope_digest": self.autonomy_envelope_digest,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


def authorize_task(
    *,
    policy: PolicyRef,
    state: LiveStateSnapshot,
    task: TaskCapsule,
    envelope: AutonomyEnvelope,
    now_epoch: int,
    decision_id: str,
) -> ExecutionDecision:
    """Fail closed unless all bound identities and authority checks agree."""

    state.require_fresh(now_epoch=now_epoch)
    envelope.require_authorized(
        repository=task.repository,
        risk_class=task.risk_class,
        now_epoch=now_epoch,
    )
    if task.repository != state.repository:
        raise NightShiftContractError("task repository does not match live state")
    if task.state_snapshot_digest != state.digest():
        raise NightShiftContractError("task is bound to a different state snapshot")
    if task.policy_digest != policy.policy_digest:
        raise NightShiftContractError("task is bound to a different policy digest")

    return ExecutionDecision(
        decision_id=decision_id,
        policy_ref_digest=policy.digest(),
        state_snapshot_digest=state.digest(),
        task_capsule_digest=task.digest(),
        autonomy_envelope_digest=envelope.digest(),
    )
