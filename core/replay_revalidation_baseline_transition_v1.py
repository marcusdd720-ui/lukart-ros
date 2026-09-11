"""LRD-01P deterministic replay-revalidation baseline transition v1.

This module composes already-authoritative LRD-01M, LRD-01N and LRD-01O evidence.
It proves whether an exact prior baseline is reused, advanced to one exact freshly
revalidated candidate baseline, or remains blocked. It does not schedule replay,
persist a latest-baseline pointer, mutate Product/CCL state, or grant release,
storage/provider, policy, or certification authority.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from core.p3.contracts import RuntimeIdentity, content_digest, require_hex_digest
from core.replay_revalidation_baseline_v1 import (
    ReplayRevalidationBaselineError,
    ReplayRevalidationBaselineV1,
)
from core.replay_revalidation_fulfilment_v1 import (
    ReplayRevalidationFulfilmentError,
    ReplayRevalidationFulfilmentState,
    ReplayRevalidationFulfilmentV1,
    verify_revalidation_fulfilment_v1,
)
from core.replay_revalidation_invalidation_v1 import (
    ReplayRevalidationDecisionV1,
    ReplayRevalidationError,
    ReplayRevalidationFingerprintV1,
    ReplayRevalidationState,
    verify_revalidation_decision_v1,
)

REVALIDATION_BASELINE_TRANSITION_SCHEMA_V1 = (
    "lukart.replay-revalidation-baseline-transition.v1"
)
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ReplayRevalidationBaselineTransitionError(ValueError):
    """Fail-closed LRD-01P contract violation."""


class ReplayRevalidationBaselineTransitionState(StrEnum):
    BASELINE_REUSED = "BASELINE_REUSED"
    BASELINE_ADVANCED = "BASELINE_ADVANCED"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"
    REVALIDATION_FAILED = "REVALIDATION_FAILED"
    UNVERIFIABLE = "UNVERIFIABLE"


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ReplayRevalidationBaselineTransitionError(
            f"{field} must be canonical nonblank text"
        )
    return value


def _digest(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    try:
        normalized = require_hex_digest(text, field_name=field)
    except ValueError as exc:
        raise ReplayRevalidationBaselineTransitionError(str(exc)) from exc
    if normalized != text:
        raise ReplayRevalidationBaselineTransitionError(
            f"{field} must be canonical lowercase sha256"
        )
    return normalized


def _optional_digest(value: object, *, field: str) -> str | None:
    return None if value is None else _digest(value, field=field)


def _git_sha(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _GIT_SHA_RE.fullmatch(text) is None:
        raise ReplayRevalidationBaselineTransitionError(
            f"{field} must be a lowercase full Git SHA"
        )
    return text


def _strict(value: Mapping[str, object], expected: frozenset[str], *, field: str) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = ",".join(sorted(expected - actual)) or "-"
    unknown = ",".join(sorted(actual - expected)) or "-"
    raise ReplayRevalidationBaselineTransitionError(
        f"{field} key contract violation: missing={missing}; unknown={unknown}"
    )


_TRANSITION_KEYS = frozenset(
    {
        "schema",
        "prior_baseline_digest",
        "prior_repository_sha",
        "decision_digest",
        "fulfilment_digest",
        "candidate_fingerprint_digest",
        "candidate_repository_sha",
        "candidate_runtime_identity_digest",
        "candidate_replay_report_digest",
        "state",
        "resulting_baseline_digest",
        "baseline_reused",
        "baseline_advanced",
        "violations",
        "scheduler_authority",
        "release_authority",
        "product_write_authority",
        "ccl_write_authority",
        "storage_authority",
        "provider_authority",
        "persistence_authority",
        "transition_digest",
    }
)


@dataclass(frozen=True, slots=True)
class ReplayRevalidationBaselineTransitionV1:
    """Content-addressed decision about one exact revalidation-baseline transition."""

    prior_baseline_digest: str
    prior_repository_sha: str
    decision_digest: str
    fulfilment_digest: str
    candidate_fingerprint_digest: str
    candidate_repository_sha: str
    candidate_runtime_identity_digest: str
    candidate_replay_report_digest: str | None
    state: ReplayRevalidationBaselineTransitionState
    resulting_baseline_digest: str | None
    violations: tuple[str, ...]
    schema: str = REVALIDATION_BASELINE_TRANSITION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != REVALIDATION_BASELINE_TRANSITION_SCHEMA_V1:
            raise ReplayRevalidationBaselineTransitionError(
                f"unsupported transition schema: {self.schema}"
            )
        for field in (
            "prior_baseline_digest",
            "decision_digest",
            "fulfilment_digest",
            "candidate_fingerprint_digest",
            "candidate_runtime_identity_digest",
        ):
            object.__setattr__(self, field, _digest(getattr(self, field), field=field))
        object.__setattr__(
            self,
            "prior_repository_sha",
            _git_sha(self.prior_repository_sha, field="prior_repository_sha"),
        )
        object.__setattr__(
            self,
            "candidate_repository_sha",
            _git_sha(self.candidate_repository_sha, field="candidate_repository_sha"),
        )
        object.__setattr__(
            self,
            "candidate_replay_report_digest",
            _optional_digest(
                self.candidate_replay_report_digest,
                field="candidate_replay_report_digest",
            ),
        )
        object.__setattr__(
            self,
            "resulting_baseline_digest",
            _optional_digest(
                self.resulting_baseline_digest,
                field="resulting_baseline_digest",
            ),
        )
        if not isinstance(self.state, ReplayRevalidationBaselineTransitionState):
            raise ReplayRevalidationBaselineTransitionError("unknown transition state")
        violations = tuple(sorted({_text(item, field="violation") for item in self.violations}))
        object.__setattr__(self, "violations", violations)

        if self.state is ReplayRevalidationBaselineTransitionState.BASELINE_REUSED:
            if self.resulting_baseline_digest != self.prior_baseline_digest:
                raise ReplayRevalidationBaselineTransitionError(
                    "BASELINE_REUSED must preserve the exact prior baseline digest"
                )
            if self.candidate_replay_report_digest is not None or violations:
                raise ReplayRevalidationBaselineTransitionError(
                    "BASELINE_REUSED cannot bind replacement replay or violations"
                )
        elif self.state is ReplayRevalidationBaselineTransitionState.BASELINE_ADVANCED:
            if self.resulting_baseline_digest is None:
                raise ReplayRevalidationBaselineTransitionError(
                    "BASELINE_ADVANCED requires an exact resulting baseline digest"
                )
            if self.resulting_baseline_digest == self.prior_baseline_digest:
                raise ReplayRevalidationBaselineTransitionError(
                    "BASELINE_ADVANCED must produce a distinct baseline identity"
                )
            if self.candidate_replay_report_digest is None or violations:
                raise ReplayRevalidationBaselineTransitionError(
                    "BASELINE_ADVANCED requires fresh replay evidence and no violations"
                )
        else:
            if self.resulting_baseline_digest is not None or not violations:
                raise ReplayRevalidationBaselineTransitionError(
                    f"{self.state.value} must remain blocked with explicit violations"
                )
            if (
                self.state is ReplayRevalidationBaselineTransitionState.REVALIDATION_FAILED
                and self.candidate_replay_report_digest is None
            ):
                raise ReplayRevalidationBaselineTransitionError(
                    "REVALIDATION_FAILED requires exact replay evidence"
                )
            if (
                self.state
                in {
                    ReplayRevalidationBaselineTransitionState.REVALIDATION_REQUIRED,
                    ReplayRevalidationBaselineTransitionState.UNVERIFIABLE,
                }
                and self.candidate_replay_report_digest is not None
            ):
                raise ReplayRevalidationBaselineTransitionError(
                    f"{self.state.value} cannot bind replacement replay evidence"
                )

    @property
    def baseline_reused(self) -> bool:
        return self.state is ReplayRevalidationBaselineTransitionState.BASELINE_REUSED

    @property
    def baseline_advanced(self) -> bool:
        return self.state is ReplayRevalidationBaselineTransitionState.BASELINE_ADVANCED

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "prior_baseline_digest": self.prior_baseline_digest,
            "prior_repository_sha": self.prior_repository_sha,
            "decision_digest": self.decision_digest,
            "fulfilment_digest": self.fulfilment_digest,
            "candidate_fingerprint_digest": self.candidate_fingerprint_digest,
            "candidate_repository_sha": self.candidate_repository_sha,
            "candidate_runtime_identity_digest": self.candidate_runtime_identity_digest,
            "candidate_replay_report_digest": self.candidate_replay_report_digest,
            "state": self.state.value,
            "resulting_baseline_digest": self.resulting_baseline_digest,
            "baseline_reused": self.baseline_reused,
            "baseline_advanced": self.baseline_advanced,
            "violations": list(self.violations),
            "scheduler_authority": False,
            "release_authority": False,
            "product_write_authority": False,
            "ccl_write_authority": False,
            "storage_authority": False,
            "provider_authority": False,
            "persistence_authority": False,
        }

    @property
    def transition_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "transition_digest": self.transition_digest}

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
    ) -> ReplayRevalidationBaselineTransitionV1:
        _strict(value, _TRANSITION_KEYS, field="revalidation baseline transition")
        for authority in (
            "scheduler_authority",
            "release_authority",
            "product_write_authority",
            "ccl_write_authority",
            "storage_authority",
            "provider_authority",
            "persistence_authority",
        ):
            if value.get(authority) is not False:
                raise ReplayRevalidationBaselineTransitionError(
                    f"{authority} must remain false"
                )
        raw_violations = value.get("violations")
        if not isinstance(raw_violations, list):
            raise ReplayRevalidationBaselineTransitionError("violations must be a list")
        try:
            state = ReplayRevalidationBaselineTransitionState(
                _text(value.get("state"), field="state")
            )
        except ValueError as exc:
            raise ReplayRevalidationBaselineTransitionError(
                "unknown transition state"
            ) from exc
        result = cls(
            schema=_text(value.get("schema"), field="schema"),
            prior_baseline_digest=_digest(
                value.get("prior_baseline_digest"), field="prior_baseline_digest"
            ),
            prior_repository_sha=_git_sha(
                value.get("prior_repository_sha"), field="prior_repository_sha"
            ),
            decision_digest=_digest(value.get("decision_digest"), field="decision_digest"),
            fulfilment_digest=_digest(
                value.get("fulfilment_digest"), field="fulfilment_digest"
            ),
            candidate_fingerprint_digest=_digest(
                value.get("candidate_fingerprint_digest"),
                field="candidate_fingerprint_digest",
            ),
            candidate_repository_sha=_git_sha(
                value.get("candidate_repository_sha"),
                field="candidate_repository_sha",
            ),
            candidate_runtime_identity_digest=_digest(
                value.get("candidate_runtime_identity_digest"),
                field="candidate_runtime_identity_digest",
            ),
            candidate_replay_report_digest=_optional_digest(
                value.get("candidate_replay_report_digest"),
                field="candidate_replay_report_digest",
            ),
            state=state,
            resulting_baseline_digest=_optional_digest(
                value.get("resulting_baseline_digest"),
                field="resulting_baseline_digest",
            ),
            violations=tuple(_text(item, field="violation") for item in raw_violations),
        )
        if value.get("baseline_reused") is not result.baseline_reused:
            raise ReplayRevalidationBaselineTransitionError("baseline_reused mismatch")
        if value.get("baseline_advanced") is not result.baseline_advanced:
            raise ReplayRevalidationBaselineTransitionError("baseline_advanced mismatch")
        expected = _digest(value.get("transition_digest"), field="transition_digest")
        if result.transition_digest != expected:
            raise ReplayRevalidationBaselineTransitionError("transition_digest mismatch")
        if dict(value) != result.canonical_dict():
            raise ReplayRevalidationBaselineTransitionError(
                "revalidation baseline transition is not canonical"
            )
        return result


@dataclass(frozen=True, slots=True)
class ReplayRevalidationBaselineTransitionEvaluationV1:
    transition: ReplayRevalidationBaselineTransitionV1
    resulting_baseline: ReplayRevalidationBaselineV1 | None

    def __post_init__(self) -> None:
        expected = self.transition.resulting_baseline_digest
        actual = None if self.resulting_baseline is None else self.resulting_baseline.baseline_digest
        if actual != expected:
            raise ReplayRevalidationBaselineTransitionError(
                "transition/resulting baseline evidence mismatch"
            )


def _verified_prior_baseline(
    baseline: ReplayRevalidationBaselineV1,
) -> ReplayRevalidationBaselineV1:
    try:
        return ReplayRevalidationBaselineV1.from_dict(baseline.canonical_dict())
    except ReplayRevalidationBaselineError as exc:
        raise ReplayRevalidationBaselineTransitionError(
            f"invalid prior LRD-01O baseline evidence: {exc}"
        ) from exc


def _build_transition(
    *,
    prior: ReplayRevalidationBaselineV1,
    decision: ReplayRevalidationDecisionV1,
    fulfilment: ReplayRevalidationFulfilmentV1,
    candidate: ReplayRevalidationFingerprintV1,
    candidate_runtime_identity: RuntimeIdentity,
    candidate_repository_sha: str,
    state: ReplayRevalidationBaselineTransitionState,
    resulting_baseline: ReplayRevalidationBaselineV1 | None,
    violations: tuple[str, ...],
) -> ReplayRevalidationBaselineTransitionEvaluationV1:
    result_digest = None if resulting_baseline is None else resulting_baseline.baseline_digest
    transition = ReplayRevalidationBaselineTransitionV1(
        prior_baseline_digest=prior.baseline_digest,
        prior_repository_sha=prior.repository_sha,
        decision_digest=decision.decision_digest,
        fulfilment_digest=fulfilment.fulfilment_digest,
        candidate_fingerprint_digest=candidate.fingerprint_digest,
        candidate_repository_sha=candidate_repository_sha,
        candidate_runtime_identity_digest=candidate_runtime_identity.digest(),
        candidate_replay_report_digest=fulfilment.replay_report_digest,
        state=state,
        resulting_baseline_digest=result_digest,
        violations=violations,
    )
    return ReplayRevalidationBaselineTransitionEvaluationV1(
        transition=transition,
        resulting_baseline=resulting_baseline,
    )


def evaluate_revalidation_baseline_transition_v1(
    *,
    prior_baseline: ReplayRevalidationBaselineV1,
    decision: ReplayRevalidationDecisionV1,
    fulfilment: ReplayRevalidationFulfilmentV1,
    candidate: ReplayRevalidationFingerprintV1,
    candidate_runtime_identity: RuntimeIdentity,
    candidate_repository_sha: str,
    replay_report: Mapping[str, object] | None = None,
    replay_repository_sha: str | None = None,
) -> ReplayRevalidationBaselineTransitionEvaluationV1:
    """Recompute upstream evidence and produce one fail-closed baseline transition."""
    prior = _verified_prior_baseline(prior_baseline)
    baseline_fingerprint, baseline_runtime = prior.invalidation_inputs()
    candidate_sha = _git_sha(candidate_repository_sha, field="candidate_repository_sha")
    if candidate_runtime_identity.code_sha != candidate_sha:
        raise ReplayRevalidationBaselineTransitionError(
            "candidate repository SHA/RuntimeIdentity substitution detected"
        )
    if candidate.runtime_identity_digest != candidate_runtime_identity.digest():
        raise ReplayRevalidationBaselineTransitionError(
            "candidate fingerprint RuntimeIdentity substitution detected"
        )

    try:
        verify_revalidation_decision_v1(
            decision,
            baseline=baseline_fingerprint,
            candidate=candidate,
            baseline_runtime_identity=baseline_runtime,
            candidate_runtime_identity=candidate_runtime_identity,
        )
        verify_revalidation_fulfilment_v1(
            fulfilment,
            decision=decision,
            baseline=baseline_fingerprint,
            candidate=candidate,
            baseline_runtime_identity=baseline_runtime,
            candidate_runtime_identity=candidate_runtime_identity,
            candidate_repository_sha=candidate_sha,
            replay_report=replay_report,
            replay_repository_sha=replay_repository_sha,
        )
    except (ReplayRevalidationError, ReplayRevalidationFulfilmentError) as exc:
        raise ReplayRevalidationBaselineTransitionError(
            f"invalid upstream revalidation evidence: {exc}"
        ) from exc

    if fulfilment.state is ReplayRevalidationFulfilmentState.BASELINE_REUSABLE:
        if decision.state is not ReplayRevalidationState.UNCHANGED:
            raise ReplayRevalidationBaselineTransitionError(
                "BASELINE_REUSABLE requires an exact UNCHANGED decision"
            )
        return _build_transition(
            prior=prior,
            decision=decision,
            fulfilment=fulfilment,
            candidate=candidate,
            candidate_runtime_identity=candidate_runtime_identity,
            candidate_repository_sha=candidate_sha,
            state=ReplayRevalidationBaselineTransitionState.BASELINE_REUSED,
            resulting_baseline=prior,
            violations=(),
        )

    if fulfilment.state is ReplayRevalidationFulfilmentState.REVALIDATED:
        if replay_report is None or replay_repository_sha is None:
            raise ReplayRevalidationBaselineTransitionError(
                "REVALIDATED transition requires exact replay report and repository SHA"
            )
        try:
            advanced = ReplayRevalidationBaselineV1.build(
                repository_sha=candidate_sha,
                replay_repository_sha=replay_repository_sha,
                runtime_identity=candidate_runtime_identity,
                fingerprint=candidate,
                replay_report=replay_report,
            )
        except ReplayRevalidationBaselineError as exc:
            raise ReplayRevalidationBaselineTransitionError(
                f"candidate cannot become a verified LRD-01O baseline: {exc}"
            ) from exc
        if advanced.replay_report_digest != fulfilment.replay_report_digest:
            raise ReplayRevalidationBaselineTransitionError(
                "advanced baseline/fulfilment replay evidence mismatch"
            )
        return _build_transition(
            prior=prior,
            decision=decision,
            fulfilment=fulfilment,
            candidate=candidate,
            candidate_runtime_identity=candidate_runtime_identity,
            candidate_repository_sha=candidate_sha,
            state=ReplayRevalidationBaselineTransitionState.BASELINE_ADVANCED,
            resulting_baseline=advanced,
            violations=(),
        )

    state_map = {
        ReplayRevalidationFulfilmentState.REVALIDATION_REQUIRED: (
            ReplayRevalidationBaselineTransitionState.REVALIDATION_REQUIRED
        ),
        ReplayRevalidationFulfilmentState.REVALIDATION_FAILED: (
            ReplayRevalidationBaselineTransitionState.REVALIDATION_FAILED
        ),
        ReplayRevalidationFulfilmentState.UNVERIFIABLE: (
            ReplayRevalidationBaselineTransitionState.UNVERIFIABLE
        ),
    }
    try:
        transition_state = state_map[fulfilment.state]
    except KeyError as exc:
        raise ReplayRevalidationBaselineTransitionError(
            f"unsupported fulfilment transition state: {fulfilment.state.value}"
        ) from exc
    return _build_transition(
        prior=prior,
        decision=decision,
        fulfilment=fulfilment,
        candidate=candidate,
        candidate_runtime_identity=candidate_runtime_identity,
        candidate_repository_sha=candidate_sha,
        state=transition_state,
        resulting_baseline=None,
        violations=(fulfilment.violations or ("revalidation_transition_blocked",)),
    )


def verify_revalidation_baseline_transition_v1(
    transition: ReplayRevalidationBaselineTransitionV1,
    *,
    prior_baseline: ReplayRevalidationBaselineV1,
    decision: ReplayRevalidationDecisionV1,
    fulfilment: ReplayRevalidationFulfilmentV1,
    candidate: ReplayRevalidationFingerprintV1,
    candidate_runtime_identity: RuntimeIdentity,
    candidate_repository_sha: str,
    replay_report: Mapping[str, object] | None = None,
    replay_repository_sha: str | None = None,
) -> str:
    """Recompute the exact transition from upstream evidence and return its identity."""
    expected = evaluate_revalidation_baseline_transition_v1(
        prior_baseline=prior_baseline,
        decision=decision,
        fulfilment=fulfilment,
        candidate=candidate,
        candidate_runtime_identity=candidate_runtime_identity,
        candidate_repository_sha=candidate_repository_sha,
        replay_report=replay_report,
        replay_repository_sha=replay_repository_sha,
    )
    if transition.canonical_dict() != expected.transition.canonical_dict():
        raise ReplayRevalidationBaselineTransitionError(
            "revalidation baseline transition evidence mismatch"
        )
    return transition.transition_digest
