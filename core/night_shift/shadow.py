"""State-bound Shadow Twin calibration and autonomy-debt accounting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.p3.contracts import content_digest, require_hex_digest

from .contracts import NightShiftContractError, require_git_oid


def _nonblank(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise NightShiftContractError(f"{field_name} is required")
    return normalized


def _digest(value: str, *, field_name: str) -> str:
    try:
        return require_hex_digest(value, field_name=field_name)
    except ValueError as exc:
        raise NightShiftContractError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class ShadowPrediction:
    task_id: str
    repository: str
    subject_sha: str
    state_snapshot_digest: str
    task_capsule_digest: str
    policy_digest: str
    executor_class: str
    expected_terminal_state: str
    predicted_at_epoch: int
    expires_at_epoch: int

    def __post_init__(self) -> None:
        for field_name in (
            "task_id",
            "repository",
            "executor_class",
            "expected_terminal_state",
        ):
            object.__setattr__(
                self,
                field_name,
                _nonblank(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self,
            "subject_sha",
            require_git_oid(self.subject_sha, field_name="subject_sha"),
        )
        for field_name in (
            "state_snapshot_digest",
            "task_capsule_digest",
            "policy_digest",
        ):
            object.__setattr__(
                self,
                field_name,
                _digest(getattr(self, field_name), field_name=field_name),
            )
        if self.predicted_at_epoch < 0:
            raise NightShiftContractError("predicted_at_epoch cannot be negative")
        if self.expires_at_epoch <= self.predicted_at_epoch:
            raise NightShiftContractError(
                "shadow prediction expiry must follow prediction time"
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": "night-shift-shadow-prediction/v1",
            "task_id": self.task_id,
            "repository": self.repository,
            "subject_sha": self.subject_sha,
            "state_snapshot_digest": self.state_snapshot_digest,
            "task_capsule_digest": self.task_capsule_digest,
            "policy_digest": self.policy_digest,
            "executor_class": self.executor_class,
            "expected_terminal_state": self.expected_terminal_state,
            "predicted_at_epoch": self.predicted_at_epoch,
            "expires_at_epoch": self.expires_at_epoch,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class ShadowObservation:
    task_id: str
    repository: str
    subject_sha: str
    state_snapshot_digest: str
    task_capsule_digest: str
    policy_digest: str
    executor_class: str
    terminal_state: str
    observed_at_epoch: int

    def __post_init__(self) -> None:
        for field_name in (
            "task_id",
            "repository",
            "executor_class",
            "terminal_state",
        ):
            object.__setattr__(
                self,
                field_name,
                _nonblank(getattr(self, field_name), field_name=field_name),
            )
        object.__setattr__(
            self,
            "subject_sha",
            require_git_oid(self.subject_sha, field_name="subject_sha"),
        )
        for field_name in (
            "state_snapshot_digest",
            "task_capsule_digest",
            "policy_digest",
        ):
            object.__setattr__(
                self,
                field_name,
                _digest(getattr(self, field_name), field_name=field_name),
            )
        if self.observed_at_epoch < 0:
            raise NightShiftContractError("observed_at_epoch cannot be negative")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": "night-shift-shadow-observation/v1",
            "task_id": self.task_id,
            "repository": self.repository,
            "subject_sha": self.subject_sha,
            "state_snapshot_digest": self.state_snapshot_digest,
            "task_capsule_digest": self.task_capsule_digest,
            "policy_digest": self.policy_digest,
            "executor_class": self.executor_class,
            "terminal_state": self.terminal_state,
            "observed_at_epoch": self.observed_at_epoch,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


class ShadowDivergence(StrEnum):
    EXACT_MATCH = "EXACT_MATCH"
    EXECUTOR_DIVERGENCE = "EXECUTOR_DIVERGENCE"
    TERMINAL_DIVERGENCE = "TERMINAL_DIVERGENCE"
    EXECUTOR_AND_TERMINAL_DIVERGENCE = "EXECUTOR_AND_TERMINAL_DIVERGENCE"


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    repository: str
    policy_digest: str
    subject_sha: str
    task_capsule_digest: str
    prediction_digest: str
    observation_digest: str
    divergence: ShadowDivergence
    debt_delta: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "repository",
            _nonblank(self.repository, field_name="repository"),
        )
        object.__setattr__(
            self,
            "subject_sha",
            require_git_oid(self.subject_sha, field_name="subject_sha"),
        )
        for field_name in (
            "policy_digest",
            "task_capsule_digest",
            "prediction_digest",
            "observation_digest",
        ):
            object.__setattr__(
                self,
                field_name,
                _digest(getattr(self, field_name), field_name=field_name),
            )
        expected_delta = {
            ShadowDivergence.EXACT_MATCH: -1,
            ShadowDivergence.EXECUTOR_DIVERGENCE: 1,
            ShadowDivergence.TERMINAL_DIVERGENCE: 2,
            ShadowDivergence.EXECUTOR_AND_TERMINAL_DIVERGENCE: 3,
        }[self.divergence]
        if self.debt_delta != expected_delta:
            raise NightShiftContractError(
                "shadow calibration debt delta does not match divergence"
            )

    @property
    def exact_match(self) -> bool:
        return self.divergence is ShadowDivergence.EXACT_MATCH

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": "night-shift-shadow-calibration/v1",
            "repository": self.repository,
            "policy_digest": self.policy_digest,
            "subject_sha": self.subject_sha,
            "task_capsule_digest": self.task_capsule_digest,
            "prediction_digest": self.prediction_digest,
            "observation_digest": self.observation_digest,
            "divergence": self.divergence.value,
            "debt_delta": self.debt_delta,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


def compare_shadow(
    prediction: ShadowPrediction,
    observation: ShadowObservation,
) -> CalibrationResult:
    identity_fields = (
        "task_id",
        "repository",
        "subject_sha",
        "state_snapshot_digest",
        "task_capsule_digest",
        "policy_digest",
    )
    mismatched = [
        field_name
        for field_name in identity_fields
        if getattr(prediction, field_name) != getattr(observation, field_name)
    ]
    if mismatched:
        raise NightShiftContractError(
            "shadow twin identity mismatch: " + ",".join(mismatched)
        )
    if observation.observed_at_epoch < prediction.predicted_at_epoch:
        raise NightShiftContractError(
            "shadow observation predates prediction"
        )
    if observation.observed_at_epoch >= prediction.expires_at_epoch:
        raise NightShiftContractError(
            "shadow prediction expired before observation"
        )

    executor_match = prediction.executor_class == observation.executor_class
    terminal_match = (
        prediction.expected_terminal_state == observation.terminal_state
    )
    if executor_match and terminal_match:
        divergence = ShadowDivergence.EXACT_MATCH
        delta = -1
    elif not executor_match and terminal_match:
        divergence = ShadowDivergence.EXECUTOR_DIVERGENCE
        delta = 1
    elif executor_match and not terminal_match:
        divergence = ShadowDivergence.TERMINAL_DIVERGENCE
        delta = 2
    else:
        divergence = ShadowDivergence.EXECUTOR_AND_TERMINAL_DIVERGENCE
        delta = 3

    return CalibrationResult(
        repository=prediction.repository,
        policy_digest=prediction.policy_digest,
        subject_sha=prediction.subject_sha,
        task_capsule_digest=prediction.task_capsule_digest,
        prediction_digest=prediction.digest(),
        observation_digest=observation.digest(),
        divergence=divergence,
        debt_delta=delta,
    )


@dataclass(frozen=True, slots=True)
class AutonomyDebtEvent:
    calibration_digest: str
    debt_delta: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "calibration_digest",
            _digest(self.calibration_digest, field_name="calibration_digest"),
        )
        if self.debt_delta not in {-1, 1, 2, 3}:
            raise NightShiftContractError("unsupported autonomy debt delta")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "calibration_digest": self.calibration_digest,
            "debt_delta": self.debt_delta,
        }


@dataclass(frozen=True, slots=True)
class AutonomyDebtLedger:
    repository: str
    policy_digest: str
    opening_value: int = 0
    downgrade_threshold: int = 10
    minimum_samples_for_auto: int = 3
    events: tuple[AutonomyDebtEvent, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "repository",
            _nonblank(self.repository, field_name="repository"),
        )
        object.__setattr__(
            self,
            "policy_digest",
            _digest(self.policy_digest, field_name="policy_digest"),
        )
        if self.opening_value < 0:
            raise NightShiftContractError("autonomy debt cannot be negative")
        if self.downgrade_threshold < 1:
            raise NightShiftContractError(
                "autonomy debt threshold must be positive"
            )
        if self.minimum_samples_for_auto < 1:
            raise NightShiftContractError(
                "minimum shadow samples for auto must be positive"
            )
        calibration_ids = [item.calibration_digest for item in self.events]
        if len(calibration_ids) != len(set(calibration_ids)):
            raise NightShiftContractError(
                "duplicate shadow calibration in autonomy debt ledger"
            )

    @property
    def value(self) -> int:
        value = self.opening_value
        for event in self.events:
            value = max(0, value + event.debt_delta)
        return value

    @property
    def sample_count(self) -> int:
        return len(self.events)

    @property
    def requires_downgrade(self) -> bool:
        return self.value >= self.downgrade_threshold

    @property
    def has_minimum_samples(self) -> bool:
        return self.sample_count >= self.minimum_samples_for_auto

    def apply(self, result: CalibrationResult) -> AutonomyDebtLedger:
        if result.repository != self.repository:
            raise NightShiftContractError(
                "shadow calibration belongs to a different repository"
            )
        if result.policy_digest != self.policy_digest:
            raise NightShiftContractError(
                "shadow calibration belongs to a different policy"
            )
        event = AutonomyDebtEvent(result.digest(), result.debt_delta)
        if event.calibration_digest in {
            item.calibration_digest for item in self.events
        }:
            raise NightShiftContractError(
                "shadow calibration already accounted for"
            )
        return AutonomyDebtLedger(
            repository=self.repository,
            policy_digest=self.policy_digest,
            opening_value=self.opening_value,
            downgrade_threshold=self.downgrade_threshold,
            minimum_samples_for_auto=self.minimum_samples_for_auto,
            events=(*self.events, event),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": "night-shift-autonomy-debt-ledger/v1",
            "repository": self.repository,
            "policy_digest": self.policy_digest,
            "opening_value": self.opening_value,
            "downgrade_threshold": self.downgrade_threshold,
            "minimum_samples_for_auto": self.minimum_samples_for_auto,
            "events": [item.canonical_dict() for item in self.events],
            "value": self.value,
            "sample_count": self.sample_count,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class ShadowPromotionClearance:
    repository: str
    subject_sha: str
    task_capsule_digest: str
    ledger_digest: str
    debt_value: int
    downgrade_threshold: int
    sample_count: int
    minimum_samples_for_auto: int
    issued_at_epoch: int
    expires_at_epoch: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "repository",
            _nonblank(self.repository, field_name="repository"),
        )
        object.__setattr__(
            self,
            "subject_sha",
            require_git_oid(self.subject_sha, field_name="subject_sha"),
        )
        for field_name in ("task_capsule_digest", "ledger_digest"):
            object.__setattr__(
                self,
                field_name,
                _digest(getattr(self, field_name), field_name=field_name),
            )
        if self.debt_value < 0:
            raise NightShiftContractError("clearance debt cannot be negative")
        if self.downgrade_threshold < 1:
            raise NightShiftContractError(
                "clearance debt threshold must be positive"
            )
        if self.sample_count < 0:
            raise NightShiftContractError("clearance sample count cannot be negative")
        if self.minimum_samples_for_auto < 1:
            raise NightShiftContractError(
                "clearance minimum samples must be positive"
            )
        if self.issued_at_epoch < 0:
            raise NightShiftContractError("clearance issuance cannot be negative")
        if self.expires_at_epoch <= self.issued_at_epoch:
            raise NightShiftContractError(
                "shadow clearance expiry must follow issuance"
            )

    @property
    def allows_auto(self) -> bool:
        return (
            self.debt_value < self.downgrade_threshold
            and self.sample_count >= self.minimum_samples_for_auto
        )

    def require_fresh(self, *, now_epoch: int) -> None:
        if now_epoch < self.issued_at_epoch:
            raise NightShiftContractError(
                "current time precedes shadow clearance issuance"
            )
        if now_epoch >= self.expires_at_epoch:
            raise NightShiftContractError("shadow promotion clearance expired")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": "night-shift-shadow-promotion-clearance/v1",
            "repository": self.repository,
            "subject_sha": self.subject_sha,
            "task_capsule_digest": self.task_capsule_digest,
            "ledger_digest": self.ledger_digest,
            "debt_value": self.debt_value,
            "downgrade_threshold": self.downgrade_threshold,
            "sample_count": self.sample_count,
            "minimum_samples_for_auto": self.minimum_samples_for_auto,
            "issued_at_epoch": self.issued_at_epoch,
            "expires_at_epoch": self.expires_at_epoch,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


def issue_shadow_clearance(
    *,
    ledger: AutonomyDebtLedger,
    subject_sha: str,
    task_capsule_digest: str,
    now_epoch: int,
    ttl_seconds: int,
) -> ShadowPromotionClearance:
    if ttl_seconds <= 0:
        raise NightShiftContractError(
            "shadow clearance ttl must be positive"
        )
    return ShadowPromotionClearance(
        repository=ledger.repository,
        subject_sha=subject_sha,
        task_capsule_digest=task_capsule_digest,
        ledger_digest=ledger.digest(),
        debt_value=ledger.value,
        downgrade_threshold=ledger.downgrade_threshold,
        sample_count=ledger.sample_count,
        minimum_samples_for_auto=ledger.minimum_samples_for_auto,
        issued_at_epoch=now_epoch,
        expires_at_epoch=now_epoch + ttl_seconds,
    )


# Compatibility wrapper retained for callers that only need the current scalar value.
@dataclass(frozen=True, slots=True)
class AutonomyDebt:
    value: int
    downgrade_threshold: int = 10

    def __post_init__(self) -> None:
        if self.value < 0:
            raise NightShiftContractError("autonomy debt cannot be negative")
        if self.downgrade_threshold < 1:
            raise NightShiftContractError(
                "autonomy debt threshold must be positive"
            )

    def apply(self, result: CalibrationResult) -> AutonomyDebt:
        return AutonomyDebt(
            value=max(0, self.value + result.debt_delta),
            downgrade_threshold=self.downgrade_threshold,
        )

    @property
    def requires_downgrade(self) -> bool:
        return self.value >= self.downgrade_threshold
