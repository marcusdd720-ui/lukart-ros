"""LRD-01L periodic replay revalidation and missed-drill detection v1.

Verification-only composition over LRD-01E health and LRD-01K cross-environment replay
evidence. Time is always caller-supplied. This module schedules nothing and grants no
Product, CCL, Gold, policy, trust-root, storage, release, or certification authority.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from core.cross_environment_replay_verifier_v1 import VerificationError, verify_report
from core.long_range_health_v1 import LongRangeHealthReportV1, LongRangeHealthState
from core.p3.contracts import content_digest, require_hex_digest

CADENCE_POLICY_SCHEMA_V1 = "lukart.periodic-replay-cadence-policy.v1"
OBSERVATION_SCHEMA_V1 = "lukart.periodic-replay-observation.v1"
EVALUATION_SCHEMA_V1 = "lukart.periodic-replay-evaluation.v1"

_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ACCEPTABLE_REPLAY_CLASSIFICATIONS = frozenset(
    {
        "EXACT_ENVIRONMENT_REPLAY",
        "CROSS_ENV_SEMANTICALLY_EQUIVALENT",
        "PRESENTATION_ONLY_DRIFT",
    }
)


class PeriodicReplayError(ValueError):
    """Fail-closed LRD-01L contract violation."""


class PeriodicReplayState(StrEnum):
    CURRENT = "CURRENT"
    DUE = "DUE"
    OVERDUE = "OVERDUE"
    UNVERIFIABLE = "UNVERIFIABLE"


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PeriodicReplayError(f"{field} must be canonical nonblank text")
    return value


def _digest(value: object, *, field: str) -> str:
    try:
        return require_hex_digest(_text(value, field=field), field_name=field)
    except ValueError as exc:
        raise PeriodicReplayError(str(exc)) from exc


def _optional_digest(value: object, *, field: str) -> str | None:
    return None if value is None else _digest(value, field=field)


def _timestamp(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PeriodicReplayError(f"{field} must be a nonnegative integer")
    return value


def _strict(value: Mapping[str, object], expected: frozenset[str], *, field: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = ",".join(sorted(expected - actual)) or "-"
        unknown = ",".join(sorted(actual - expected)) or "-"
        raise PeriodicReplayError(
            f"{field} key contract violation: missing={missing}; unknown={unknown}"
        )


def _git_sha(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _GIT_SHA_RE.fullmatch(text) is None:
        raise PeriodicReplayError(f"{field} must be a lowercase full Git SHA")
    return text


def _verify_identity(value: Mapping[str, object], identity_field: str) -> str:
    actual = _digest(value.get(identity_field), field=identity_field)
    body = dict(value)
    body.pop(identity_field, None)
    if content_digest(body) != actual:
        raise PeriodicReplayError(f"{identity_field} mismatch")
    return actual


def _cross_environment_revalidation(
    report: Mapping[str, object],
) -> tuple[str, str, bool, tuple[str, ...]]:
    try:
        report_digest = verify_report(report)
    except VerificationError as exc:
        raise PeriodicReplayError(f"invalid LRD-01K report: {exc}") from exc
    plan = report.get("plan")
    if not isinstance(plan, Mapping):
        raise PeriodicReplayError("LRD-01K report plan is missing")
    bundle_digest = _digest(plan.get("lrd01i_bundle_digest"), field="lrd01i_bundle_digest")
    receipts = report.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        raise PeriodicReplayError("LRD-01K report receipts are missing")
    violations: list[str] = []
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            raise PeriodicReplayError("LRD-01K receipt must be an object")
        if receipt.get("execution_status") != "VERIFIED":
            violations.append("cross_environment_execution_not_verified")
        classification = receipt.get("classification")
        if classification not in _ACCEPTABLE_REPLAY_CLASSIFICATIONS:
            violations.append("cross_environment_semantic_revalidation_failed")
    normalized = tuple(sorted(set(violations)))
    return report_digest, bundle_digest, not normalized, normalized


@dataclass(frozen=True, slots=True)
class PeriodicReplayCadencePolicyV1:
    effective_at: int
    max_replay_age_seconds: int
    due_window_seconds: int
    schema: str = CADENCE_POLICY_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CADENCE_POLICY_SCHEMA_V1:
            raise PeriodicReplayError(f"unsupported cadence policy schema: {self.schema}")
        _timestamp(self.effective_at, field="effective_at")
        max_age = _timestamp(self.max_replay_age_seconds, field="max_replay_age_seconds")
        due_window = _timestamp(self.due_window_seconds, field="due_window_seconds")
        if max_age == 0:
            raise PeriodicReplayError("max_replay_age_seconds must be positive")
        if due_window == 0 or due_window >= max_age:
            raise PeriodicReplayError(
                "due_window_seconds must be positive and less than max_replay_age_seconds"
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "effective_at": self.effective_at,
            "max_replay_age_seconds": self.max_replay_age_seconds,
            "due_window_seconds": self.due_window_seconds,
            "required_health_state": LongRangeHealthState.HEALTHY.value,
            "acceptable_replay_classifications": sorted(_ACCEPTABLE_REPLAY_CLASSIFICATIONS),
            "scheduler_authority": False,
        }

    @property
    def policy_digest(self) -> str:
        return content_digest(self.canonical_dict())


_OBSERVATION_KEYS = frozenset(
    {
        "schema",
        "case_id",
        "repository_sha",
        "observed_at",
        "lrd01i_bundle_digest",
        "cross_environment_report_digest",
        "long_range_health_report_digest",
        "upstream_revalidation_pass",
        "upstream_violations",
        "previous_observation_digest",
        "observation_digest",
    }
)


@dataclass(frozen=True, slots=True)
class PeriodicReplayObservationV1:
    case_id: str
    repository_sha: str
    observed_at: int
    lrd01i_bundle_digest: str
    cross_environment_report_digest: str
    long_range_health_report_digest: str
    upstream_revalidation_pass: bool
    upstream_violations: tuple[str, ...]
    previous_observation_digest: str | None = None
    schema: str = OBSERVATION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != OBSERVATION_SCHEMA_V1:
            raise PeriodicReplayError(f"unsupported observation schema: {self.schema}")
        object.__setattr__(self, "case_id", _text(self.case_id, field="case_id"))
        object.__setattr__(
            self,
            "repository_sha",
            _git_sha(self.repository_sha, field="repository_sha"),
        )
        object.__setattr__(self, "observed_at", _timestamp(self.observed_at, field="observed_at"))
        for field in (
            "lrd01i_bundle_digest",
            "cross_environment_report_digest",
            "long_range_health_report_digest",
        ):
            object.__setattr__(self, field, _digest(getattr(self, field), field=field))
        object.__setattr__(
            self,
            "previous_observation_digest",
            _optional_digest(
                self.previous_observation_digest,
                field="previous_observation_digest",
            ),
        )
        normalized = tuple(
            sorted({_text(item, field="upstream_violation") for item in self.upstream_violations})
        )
        object.__setattr__(self, "upstream_violations", normalized)
        if not isinstance(self.upstream_revalidation_pass, bool):
            raise PeriodicReplayError("upstream_revalidation_pass must be boolean")
        if self.upstream_revalidation_pass and normalized:
            raise PeriodicReplayError("passing observation cannot contain upstream violations")
        if not self.upstream_revalidation_pass and not normalized:
            raise PeriodicReplayError("failed observation requires upstream violations")

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "repository_sha": self.repository_sha,
            "observed_at": self.observed_at,
            "lrd01i_bundle_digest": self.lrd01i_bundle_digest,
            "cross_environment_report_digest": self.cross_environment_report_digest,
            "long_range_health_report_digest": self.long_range_health_report_digest,
            "upstream_revalidation_pass": self.upstream_revalidation_pass,
            "upstream_violations": list(self.upstream_violations),
            "previous_observation_digest": self.previous_observation_digest,
        }

    @property
    def observation_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "observation_digest": self.observation_digest}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> PeriodicReplayObservationV1:
        _strict(value, _OBSERVATION_KEYS, field="periodic replay observation")
        violations = value.get("upstream_violations")
        if (
            not isinstance(violations, list)
            or not all(isinstance(item, str) for item in violations)
        ):
            raise PeriodicReplayError("upstream_violations must be a list of strings")
        result = cls(
            schema=_text(value.get("schema"), field="schema"),
            case_id=_text(value.get("case_id"), field="case_id"),
            repository_sha=_git_sha(value.get("repository_sha"), field="repository_sha"),
            observed_at=_timestamp(value.get("observed_at"), field="observed_at"),
            lrd01i_bundle_digest=_digest(
                value.get("lrd01i_bundle_digest"), field="lrd01i_bundle_digest"
            ),
            cross_environment_report_digest=_digest(
                value.get("cross_environment_report_digest"),
                field="cross_environment_report_digest",
            ),
            long_range_health_report_digest=_digest(
                value.get("long_range_health_report_digest"),
                field="long_range_health_report_digest",
            ),
            upstream_revalidation_pass=value.get("upstream_revalidation_pass") is True,
            upstream_violations=tuple(violations),
            previous_observation_digest=_optional_digest(
                value.get("previous_observation_digest"),
                field="previous_observation_digest",
            ),
        )
        if value.get("upstream_revalidation_pass") is not result.upstream_revalidation_pass:
            raise PeriodicReplayError("upstream_revalidation_pass must be boolean")
        if result.observation_digest != _digest(
            value.get("observation_digest"), field="observation_digest"
        ):
            raise PeriodicReplayError("observation_digest mismatch")
        return result


def build_periodic_replay_observation_v1(
    *,
    case_id: str,
    repository_sha: str,
    observed_at: int,
    cross_environment_report: Mapping[str, object],
    long_range_health_report: LongRangeHealthReportV1,
    previous: PeriodicReplayObservationV1 | None = None,
) -> PeriodicReplayObservationV1:
    """Bind one actual upstream revalidation result without inventing upstream semantics."""
    case_id = _text(case_id, field="case_id")
    observed_at = _timestamp(observed_at, field="observed_at")
    cross_digest, bundle_digest, cross_pass, cross_violations = _cross_environment_revalidation(
        cross_environment_report
    )
    if long_range_health_report.case_id != case_id:
        raise PeriodicReplayError("LRD-01E health report case scope mismatch")
    if long_range_health_report.evaluated_at > observed_at:
        raise PeriodicReplayError("LRD-01E health report timestamp is after observation")
    violations = list(cross_violations)
    if long_range_health_report.state is not LongRangeHealthState.HEALTHY:
        violations.append("long_range_health_not_healthy")
    previous_digest = None
    if previous is not None:
        if previous.case_id != case_id:
            raise PeriodicReplayError("previous observation case scope mismatch")
        if previous.lrd01i_bundle_digest != bundle_digest:
            raise PeriodicReplayError("previous observation bundle identity mismatch")
        if previous.observed_at >= observed_at:
            raise PeriodicReplayError("observation chain timestamp must increase")
        previous_digest = previous.observation_digest
    normalized = tuple(sorted(set(violations)))
    return PeriodicReplayObservationV1(
        case_id=case_id,
        repository_sha=_git_sha(repository_sha, field="repository_sha"),
        observed_at=observed_at,
        lrd01i_bundle_digest=bundle_digest,
        cross_environment_report_digest=cross_digest,
        long_range_health_report_digest=long_range_health_report.report_digest,
        upstream_revalidation_pass=cross_pass and not normalized,
        upstream_violations=normalized,
        previous_observation_digest=previous_digest,
    )


def verify_observation_evidence_v1(
    observation: PeriodicReplayObservationV1,
    *,
    cross_environment_report: Mapping[str, object],
    long_range_health_report: LongRangeHealthReportV1,
) -> str:
    """Rebind an immutable observation to the exact upstream evidence objects."""
    cross_digest, bundle_digest, cross_pass, cross_violations = _cross_environment_revalidation(
        cross_environment_report
    )
    if observation.cross_environment_report_digest != cross_digest:
        raise PeriodicReplayError("cross-environment report substitution detected")
    if observation.lrd01i_bundle_digest != bundle_digest:
        raise PeriodicReplayError("LRD-01I bundle substitution detected")
    if observation.long_range_health_report_digest != long_range_health_report.report_digest:
        raise PeriodicReplayError("long-range health report substitution detected")
    if observation.case_id != long_range_health_report.case_id:
        raise PeriodicReplayError("observation/health case scope mismatch")
    violations = list(cross_violations)
    if long_range_health_report.state is not LongRangeHealthState.HEALTHY:
        violations.append("long_range_health_not_healthy")
    normalized = tuple(sorted(set(violations)))
    expected_pass = cross_pass and not normalized
    if observation.upstream_revalidation_pass is not expected_pass:
        raise PeriodicReplayError("observation upstream result mismatch")
    if observation.upstream_violations != normalized:
        raise PeriodicReplayError("observation upstream violations mismatch")
    return observation.observation_digest


_EVALUATION_KEYS = frozenset(
    {
        "schema",
        "evaluated_at",
        "cadence_policy_digest",
        "observation_chain_digest",
        "latest_observation_digest",
        "latest_observation_age_seconds",
        "state",
        "violations",
        "scheduler_authority",
        "evaluation_digest",
    }
)


def verify_observation_chain_v1(
    observations: Sequence[PeriodicReplayObservationV1],
) -> str:
    """Verify one exact immutable observation chain and return its content identity."""
    if not observations:
        return content_digest([])
    seen: set[str] = set()
    previous: PeriodicReplayObservationV1 | None = None
    case_id = observations[0].case_id
    bundle_digest = observations[0].lrd01i_bundle_digest
    identities: list[str] = []
    for observation in observations:
        identity = observation.observation_digest
        if identity in seen:
            raise PeriodicReplayError("duplicate observation in periodic replay chain")
        seen.add(identity)
        if observation.case_id != case_id:
            raise PeriodicReplayError("periodic replay chain case scope mismatch")
        if observation.lrd01i_bundle_digest != bundle_digest:
            raise PeriodicReplayError("periodic replay chain bundle identity mismatch")
        if previous is None:
            if observation.previous_observation_digest is not None:
                raise PeriodicReplayError(
                    "first periodic replay observation must not have a predecessor"
                )
        else:
            if observation.previous_observation_digest != previous.observation_digest:
                raise PeriodicReplayError("periodic replay observation predecessor mismatch")
            if observation.observed_at <= previous.observed_at:
                raise PeriodicReplayError("periodic replay chain timestamp must increase")
        identities.append(identity)
        previous = observation
    return content_digest(identities)


@dataclass(frozen=True, slots=True)
class PeriodicReplayEvaluationV1:
    evaluated_at: int
    cadence_policy_digest: str
    observation_chain_digest: str
    latest_observation_digest: str | None
    latest_observation_age_seconds: int | None
    state: PeriodicReplayState
    violations: tuple[str, ...]
    schema: str = EVALUATION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != EVALUATION_SCHEMA_V1:
            raise PeriodicReplayError(f"unsupported evaluation schema: {self.schema}")
        object.__setattr__(
            self,
            "evaluated_at",
            _timestamp(self.evaluated_at, field="evaluated_at"),
        )
        object.__setattr__(
            self,
            "cadence_policy_digest",
            _digest(self.cadence_policy_digest, field="cadence_policy_digest"),
        )
        object.__setattr__(
            self,
            "observation_chain_digest",
            _digest(self.observation_chain_digest, field="observation_chain_digest"),
        )
        object.__setattr__(
            self,
            "latest_observation_digest",
            _optional_digest(
                self.latest_observation_digest,
                field="latest_observation_digest",
            ),
        )
        if self.latest_observation_age_seconds is not None:
            object.__setattr__(
                self,
                "latest_observation_age_seconds",
                _timestamp(
                    self.latest_observation_age_seconds,
                    field="latest_observation_age_seconds",
                ),
            )
        if not isinstance(self.state, PeriodicReplayState):
            raise PeriodicReplayError("unknown periodic replay state")
        normalized = tuple(sorted({_text(item, field="violation") for item in self.violations}))
        object.__setattr__(self, "violations", normalized)
        if self.state in {PeriodicReplayState.CURRENT, PeriodicReplayState.DUE} and normalized:
            raise PeriodicReplayError("CURRENT/DUE evaluation cannot contain violations")
        if (
            self.state in {PeriodicReplayState.OVERDUE, PeriodicReplayState.UNVERIFIABLE}
            and not normalized
        ):
            raise PeriodicReplayError("OVERDUE/UNVERIFIABLE evaluation requires violations")

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "evaluated_at": self.evaluated_at,
            "cadence_policy_digest": self.cadence_policy_digest,
            "observation_chain_digest": self.observation_chain_digest,
            "latest_observation_digest": self.latest_observation_digest,
            "latest_observation_age_seconds": self.latest_observation_age_seconds,
            "state": self.state.value,
            "violations": list(self.violations),
            "scheduler_authority": False,
        }

    @property
    def evaluation_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "evaluation_digest": self.evaluation_digest}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> PeriodicReplayEvaluationV1:
        _strict(value, _EVALUATION_KEYS, field="periodic replay evaluation")
        if value.get("scheduler_authority") is not False:
            raise PeriodicReplayError("periodic replay evidence cannot grant scheduler authority")
        violations = value.get("violations")
        if (
            not isinstance(violations, list)
            or not all(isinstance(item, str) for item in violations)
        ):
            raise PeriodicReplayError("violations must be a list of strings")
        age = value.get("latest_observation_age_seconds")
        if age is not None:
            age = _timestamp(age, field="latest_observation_age_seconds")
        try:
            state = PeriodicReplayState(_text(value.get("state"), field="state"))
        except ValueError as exc:
            raise PeriodicReplayError("unknown periodic replay state") from exc
        result = cls(
            schema=_text(value.get("schema"), field="schema"),
            evaluated_at=_timestamp(value.get("evaluated_at"), field="evaluated_at"),
            cadence_policy_digest=_digest(
                value.get("cadence_policy_digest"), field="cadence_policy_digest"
            ),
            observation_chain_digest=_digest(
                value.get("observation_chain_digest"), field="observation_chain_digest"
            ),
            latest_observation_digest=_optional_digest(
                value.get("latest_observation_digest"), field="latest_observation_digest"
            ),
            latest_observation_age_seconds=age,
            state=state,
            violations=tuple(violations),
        )
        if result.evaluation_digest != _digest(
            value.get("evaluation_digest"), field="evaluation_digest"
        ):
            raise PeriodicReplayError("evaluation_digest mismatch")
        return result


def _historical_gap_violations(
    *,
    policy: PeriodicReplayCadencePolicyV1,
    observations: Sequence[PeriodicReplayObservationV1],
) -> tuple[str, ...]:
    if not observations:
        return ()
    violations: list[str] = []
    first = observations[0]
    if first.observed_at < policy.effective_at:
        raise PeriodicReplayError("periodic replay observation predates cadence policy")
    if first.observed_at - policy.effective_at > policy.max_replay_age_seconds:
        violations.append("initial_periodic_replay_deadline_missed")
    for previous, current in zip(observations, observations[1:], strict=False):
        if current.observed_at - previous.observed_at > policy.max_replay_age_seconds:
            violations.append("historical_periodic_replay_gap")
    return tuple(sorted(set(violations)))


def evaluate_periodic_replay_v1(
    *,
    policy: PeriodicReplayCadencePolicyV1,
    evaluated_at: int,
    observations: Sequence[PeriodicReplayObservationV1],
) -> PeriodicReplayEvaluationV1:
    """Evaluate explicit cadence history; never read the wall clock or schedule work."""
    evaluated_at = _timestamp(evaluated_at, field="evaluated_at")
    if evaluated_at < policy.effective_at:
        raise PeriodicReplayError("evaluation timestamp predates cadence policy")
    chain_digest = verify_observation_chain_v1(observations)
    if not observations:
        age_from_effective = evaluated_at - policy.effective_at
        if age_from_effective > policy.max_replay_age_seconds:
            return PeriodicReplayEvaluationV1(
                evaluated_at=evaluated_at,
                cadence_policy_digest=policy.policy_digest,
                observation_chain_digest=chain_digest,
                latest_observation_digest=None,
                latest_observation_age_seconds=None,
                state=PeriodicReplayState.OVERDUE,
                violations=("initial_periodic_replay_missing",),
            )
        return PeriodicReplayEvaluationV1(
            evaluated_at=evaluated_at,
            cadence_policy_digest=policy.policy_digest,
            observation_chain_digest=chain_digest,
            latest_observation_digest=None,
            latest_observation_age_seconds=None,
            state=PeriodicReplayState.UNVERIFIABLE,
            violations=("periodic_replay_observation_missing",),
        )
    historical_violations = _historical_gap_violations(policy=policy, observations=observations)
    latest = observations[-1]
    if latest.observed_at > evaluated_at:
        raise PeriodicReplayError("periodic replay observation timestamp is in the future")
    age = evaluated_at - latest.observed_at
    if historical_violations:
        return PeriodicReplayEvaluationV1(
            evaluated_at=evaluated_at,
            cadence_policy_digest=policy.policy_digest,
            observation_chain_digest=chain_digest,
            latest_observation_digest=latest.observation_digest,
            latest_observation_age_seconds=age,
            state=PeriodicReplayState.OVERDUE,
            violations=historical_violations,
        )
    if not latest.upstream_revalidation_pass:
        return PeriodicReplayEvaluationV1(
            evaluated_at=evaluated_at,
            cadence_policy_digest=policy.policy_digest,
            observation_chain_digest=chain_digest,
            latest_observation_digest=latest.observation_digest,
            latest_observation_age_seconds=age,
            state=PeriodicReplayState.UNVERIFIABLE,
            violations=("upstream_revalidation_failed", *latest.upstream_violations),
        )
    if age > policy.max_replay_age_seconds:
        state = PeriodicReplayState.OVERDUE
        violations = ("periodic_replay_overdue",)
    elif age >= policy.max_replay_age_seconds - policy.due_window_seconds:
        state = PeriodicReplayState.DUE
        violations = ()
    else:
        state = PeriodicReplayState.CURRENT
        violations = ()
    return PeriodicReplayEvaluationV1(
        evaluated_at=evaluated_at,
        cadence_policy_digest=policy.policy_digest,
        observation_chain_digest=chain_digest,
        latest_observation_digest=latest.observation_digest,
        latest_observation_age_seconds=age,
        state=state,
        violations=violations,
    )
