"""LRD-01N change-triggered replay revalidation fulfilment v1.

Verification-only composition over LRD-01M invalidation decisions and LRD-01K
cross-environment replay evidence. This module does not execute or schedule replay,
mutate Product/CCL state, or grant release, provider, policy, or certification authority.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from core.cross_environment_replay_verifier_v1 import VerificationError, verify_report
from core.p3.contracts import RuntimeIdentity, content_digest, require_hex_digest
from core.replay_revalidation_invalidation_v1 import (
    ReplayRevalidationDecisionV1,
    ReplayRevalidationError,
    ReplayRevalidationFingerprintV1,
    ReplayRevalidationState,
    verify_revalidation_decision_v1,
)

REVALIDATION_FULFILMENT_SCHEMA_V1 = "lukart.replay-revalidation-fulfilment.v1"
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ACCEPTABLE_REPLAY_CLASSIFICATIONS = frozenset(
    {
        "EXACT_ENVIRONMENT_REPLAY",
        "CROSS_ENV_SEMANTICALLY_EQUIVALENT",
        "PRESENTATION_ONLY_DRIFT",
    }
)


class ReplayRevalidationFulfilmentError(ValueError):
    """Fail-closed LRD-01N contract violation."""


class ReplayRevalidationFulfilmentState(StrEnum):
    BASELINE_REUSABLE = "BASELINE_REUSABLE"
    REVALIDATED = "REVALIDATED"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"
    REVALIDATION_FAILED = "REVALIDATION_FAILED"
    UNVERIFIABLE = "UNVERIFIABLE"


def _digest(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ReplayRevalidationFulfilmentError(f"{field} must be lowercase sha256")
    try:
        normalized = require_hex_digest(value, field_name=field)
    except ValueError as exc:
        raise ReplayRevalidationFulfilmentError(str(exc)) from exc
    if normalized != value:
        raise ReplayRevalidationFulfilmentError(
            f"{field} must be canonical lowercase sha256"
        )
    return normalized


def _optional_digest(value: object, *, field: str) -> str | None:
    return None if value is None else _digest(value, field=field)


def _git_sha(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _GIT_SHA_RE.fullmatch(value) is None:
        raise ReplayRevalidationFulfilmentError(
            f"{field} must be a lowercase 40-char git SHA"
        )
    return value


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ReplayRevalidationFulfilmentError(
            f"{field} must be canonical nonblank text"
        )
    return value


def _strict(
    value: Mapping[str, object],
    expected: frozenset[str],
    *,
    field: str,
) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = ",".join(sorted(expected - actual)) or "-"
    unknown = ",".join(sorted(actual - expected)) or "-"
    raise ReplayRevalidationFulfilmentError(
        f"{field} key contract violation: missing={missing}; unknown={unknown}"
    )


_FULFILMENT_KEYS = frozenset(
    {
        "schema",
        "decision_digest",
        "candidate_fingerprint_digest",
        "candidate_repository_sha",
        "replay_repository_sha",
        "replay_report_digest",
        "state",
        "violations",
        "baseline_replay_reusable",
        "revalidation_satisfied",
        "scheduler_authority",
        "release_authority",
        "product_write_authority",
        "ccl_write_authority",
        "fulfilment_digest",
    }
)


@dataclass(frozen=True, slots=True)
class ReplayRevalidationFulfilmentV1:
    decision_digest: str
    candidate_fingerprint_digest: str
    candidate_repository_sha: str
    replay_repository_sha: str | None
    replay_report_digest: str | None
    state: ReplayRevalidationFulfilmentState
    violations: tuple[str, ...]
    schema: str = REVALIDATION_FULFILMENT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != REVALIDATION_FULFILMENT_SCHEMA_V1:
            raise ReplayRevalidationFulfilmentError(
                f"unsupported fulfilment schema: {self.schema}"
            )
        object.__setattr__(
            self,
            "decision_digest",
            _digest(self.decision_digest, field="decision_digest"),
        )
        object.__setattr__(
            self,
            "candidate_fingerprint_digest",
            _digest(
                self.candidate_fingerprint_digest,
                field="candidate_fingerprint_digest",
            ),
        )
        object.__setattr__(
            self,
            "candidate_repository_sha",
            _git_sha(self.candidate_repository_sha, field="candidate_repository_sha"),
        )
        if self.replay_repository_sha is not None:
            object.__setattr__(
                self,
                "replay_repository_sha",
                _git_sha(self.replay_repository_sha, field="replay_repository_sha"),
            )
        object.__setattr__(
            self,
            "replay_report_digest",
            _optional_digest(self.replay_report_digest, field="replay_report_digest"),
        )
        if not isinstance(self.state, ReplayRevalidationFulfilmentState):
            raise ReplayRevalidationFulfilmentError("unknown fulfilment state")
        violations = tuple(
            sorted({_text(item, field="violation") for item in self.violations})
        )
        object.__setattr__(self, "violations", violations)

        replay_bound = (
            self.replay_repository_sha is not None
            or self.replay_report_digest is not None
        )
        if (self.replay_repository_sha is None) != (
            self.replay_report_digest is None
        ):
            raise ReplayRevalidationFulfilmentError(
                "replay repository SHA and report digest must be present together"
            )
        if self.state is ReplayRevalidationFulfilmentState.REVALIDATED:
            if not replay_bound or violations:
                raise ReplayRevalidationFulfilmentError(
                    "REVALIDATED requires exact replay evidence and no violations"
                )
        elif self.state is ReplayRevalidationFulfilmentState.REVALIDATION_FAILED:
            if not replay_bound or not violations:
                raise ReplayRevalidationFulfilmentError(
                    "REVALIDATION_FAILED requires exact replay evidence and violations"
                )
        elif replay_bound:
            raise ReplayRevalidationFulfilmentError(
                f"{self.state.value} cannot bind replay evidence"
            )
        elif self.state is ReplayRevalidationFulfilmentState.BASELINE_REUSABLE:
            if violations:
                raise ReplayRevalidationFulfilmentError(
                    "BASELINE_REUSABLE cannot contain violations"
                )
        elif not violations:
            raise ReplayRevalidationFulfilmentError(
                f"{self.state.value} requires explicit violations"
            )

    @property
    def baseline_replay_reusable(self) -> bool:
        return self.state is ReplayRevalidationFulfilmentState.BASELINE_REUSABLE

    @property
    def revalidation_satisfied(self) -> bool:
        return self.state is ReplayRevalidationFulfilmentState.REVALIDATED

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "decision_digest": self.decision_digest,
            "candidate_fingerprint_digest": self.candidate_fingerprint_digest,
            "candidate_repository_sha": self.candidate_repository_sha,
            "replay_repository_sha": self.replay_repository_sha,
            "replay_report_digest": self.replay_report_digest,
            "state": self.state.value,
            "violations": list(self.violations),
            "baseline_replay_reusable": self.baseline_replay_reusable,
            "revalidation_satisfied": self.revalidation_satisfied,
            "scheduler_authority": False,
            "release_authority": False,
            "product_write_authority": False,
            "ccl_write_authority": False,
        }

    @property
    def fulfilment_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "fulfilment_digest": self.fulfilment_digest}

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
    ) -> ReplayRevalidationFulfilmentV1:
        _strict(value, _FULFILMENT_KEYS, field="revalidation fulfilment")
        for authority in (
            "scheduler_authority",
            "release_authority",
            "product_write_authority",
            "ccl_write_authority",
        ):
            if value.get(authority) is not False:
                raise ReplayRevalidationFulfilmentError(
                    f"{authority} must remain false"
                )
        raw_violations = value.get("violations")
        if not isinstance(raw_violations, list):
            raise ReplayRevalidationFulfilmentError("violations must be a list")
        try:
            state = ReplayRevalidationFulfilmentState(
                _text(value.get("state"), field="state")
            )
        except ValueError as exc:
            raise ReplayRevalidationFulfilmentError(
                "unknown fulfilment state"
            ) from exc
        result = cls(
            schema=_text(value.get("schema"), field="schema"),
            decision_digest=_digest(
                value.get("decision_digest"),
                field="decision_digest",
            ),
            candidate_fingerprint_digest=_digest(
                value.get("candidate_fingerprint_digest"),
                field="candidate_fingerprint_digest",
            ),
            candidate_repository_sha=_git_sha(
                value.get("candidate_repository_sha"),
                field="candidate_repository_sha",
            ),
            replay_repository_sha=(
                None
                if value.get("replay_repository_sha") is None
                else _git_sha(
                    value.get("replay_repository_sha"),
                    field="replay_repository_sha",
                )
            ),
            replay_report_digest=_optional_digest(
                value.get("replay_report_digest"),
                field="replay_report_digest",
            ),
            state=state,
            violations=tuple(
                _text(item, field="violation") for item in raw_violations
            ),
        )
        if value.get("baseline_replay_reusable") is not result.baseline_replay_reusable:
            raise ReplayRevalidationFulfilmentError(
                "baseline_replay_reusable mismatch"
            )
        if value.get("revalidation_satisfied") is not result.revalidation_satisfied:
            raise ReplayRevalidationFulfilmentError("revalidation_satisfied mismatch")
        expected = _digest(
            value.get("fulfilment_digest"),
            field="fulfilment_digest",
        )
        if result.fulfilment_digest != expected:
            raise ReplayRevalidationFulfilmentError("fulfilment_digest mismatch")
        if dict(value) != result.canonical_dict():
            raise ReplayRevalidationFulfilmentError(
                "revalidation fulfilment is not canonical"
            )
        return result


def _verify_plan_matches_candidate(
    *,
    report: Mapping[str, object],
    candidate: ReplayRevalidationFingerprintV1,
) -> None:
    plan = report.get("plan")
    if not isinstance(plan, dict):
        raise ReplayRevalidationFulfilmentError(
            "verified replay report plan is missing"
        )
    expected: tuple[tuple[str, object], ...] = (
        ("lrd01i_bundle_digest", candidate.lrd01i_bundle_digest),
        ("ssc02_manifest_digest", candidate.ssc02_manifest_digest),
        ("environment_profile_digests", list(candidate.environment_profile_digests)),
        ("replay_policy_digest", candidate.replay_policy_digest),
        ("migration_registry_digest", candidate.migration_registry_digest),
        (
            "canonicalization_profile_digest",
            candidate.canonicalization_profile_digest,
        ),
        ("crypto_profile_digest", candidate.crypto_profile_digest),
    )
    for field, identity in expected:
        if plan.get(field) != identity:
            raise ReplayRevalidationFulfilmentError(
                "replay report/candidate fingerprint substitution detected: "
                f"{field}"
            )


def _replay_failures(report: Mapping[str, object]) -> tuple[str, ...]:
    raw = report.get("receipts")
    if not isinstance(raw, list):
        raise ReplayRevalidationFulfilmentError(
            "verified replay report receipts are missing"
        )
    failures: set[str] = set()
    for receipt in raw:
        if not isinstance(receipt, dict):
            raise ReplayRevalidationFulfilmentError(
                "verified replay receipt is malformed"
            )
        profile = str(receipt.get("environment_profile_digest"))
        if receipt.get("execution_status") != "VERIFIED":
            failures.add(f"execution_not_verified:{profile}")
        classification = str(receipt.get("classification"))
        if classification not in _ACCEPTABLE_REPLAY_CLASSIFICATIONS:
            failures.add(
                f"unacceptable_replay_classification:{profile}:{classification}"
            )
    return tuple(sorted(failures))


def _result(
    *,
    decision: ReplayRevalidationDecisionV1,
    candidate: ReplayRevalidationFingerprintV1,
    candidate_repository_sha: str,
    replay_repository_sha: str | None,
    replay_report_digest: str | None,
    state: ReplayRevalidationFulfilmentState,
    violations: tuple[str, ...],
) -> ReplayRevalidationFulfilmentV1:
    return ReplayRevalidationFulfilmentV1(
        decision_digest=decision.decision_digest,
        candidate_fingerprint_digest=candidate.fingerprint_digest,
        candidate_repository_sha=candidate_repository_sha,
        replay_repository_sha=replay_repository_sha,
        replay_report_digest=replay_report_digest,
        state=state,
        violations=violations,
    )


def evaluate_revalidation_fulfilment_v1(
    *,
    decision: ReplayRevalidationDecisionV1,
    baseline: ReplayRevalidationFingerprintV1 | None,
    candidate: ReplayRevalidationFingerprintV1,
    baseline_runtime_identity: RuntimeIdentity | None,
    candidate_runtime_identity: RuntimeIdentity,
    candidate_repository_sha: str,
    replay_report: Mapping[str, object] | None = None,
    replay_repository_sha: str | None = None,
) -> ReplayRevalidationFulfilmentV1:
    """Bind one verified 01M decision to exact 01K replay evidence, fail closed."""
    try:
        verify_revalidation_decision_v1(
            decision,
            baseline=baseline,
            candidate=candidate,
            baseline_runtime_identity=baseline_runtime_identity,
            candidate_runtime_identity=candidate_runtime_identity,
        )
    except ReplayRevalidationError as exc:
        raise ReplayRevalidationFulfilmentError(
            f"invalid LRD-01M decision evidence: {exc}"
        ) from exc

    candidate_sha = _git_sha(
        candidate_repository_sha,
        field="candidate_repository_sha",
    )
    if len(candidate_runtime_identity.code_sha) != 40:
        raise ReplayRevalidationFulfilmentError(
            "candidate RuntimeIdentity code_sha must be exact 40-char repository SHA"
        )
    if candidate_runtime_identity.code_sha != candidate_sha:
        raise ReplayRevalidationFulfilmentError(
            "candidate repository SHA/RuntimeIdentity substitution detected"
        )

    if decision.state is ReplayRevalidationState.UNCHANGED:
        if replay_report is not None or replay_repository_sha is not None:
            raise ReplayRevalidationFulfilmentError(
                "UNCHANGED decision must reuse its verified baseline without "
                "replacement evidence"
            )
        return _result(
            decision=decision,
            candidate=candidate,
            candidate_repository_sha=candidate_sha,
            replay_repository_sha=None,
            replay_report_digest=None,
            state=ReplayRevalidationFulfilmentState.BASELINE_REUSABLE,
            violations=(),
        )
    if decision.state is ReplayRevalidationState.UNVERIFIABLE:
        if replay_report is not None or replay_repository_sha is not None:
            raise ReplayRevalidationFulfilmentError(
                "replay evidence cannot cure an UNVERIFIABLE invalidation decision"
            )
        return _result(
            decision=decision,
            candidate=candidate,
            candidate_repository_sha=candidate_sha,
            replay_repository_sha=None,
            replay_report_digest=None,
            state=ReplayRevalidationFulfilmentState.UNVERIFIABLE,
            violations=(
                decision.violations
                or ("revalidation_decision_unverifiable",)
            ),
        )

    if replay_report is None and replay_repository_sha is None:
        return _result(
            decision=decision,
            candidate=candidate,
            candidate_repository_sha=candidate_sha,
            replay_repository_sha=None,
            replay_report_digest=None,
            state=ReplayRevalidationFulfilmentState.REVALIDATION_REQUIRED,
            violations=("fresh_cross_environment_replay_evidence_missing",),
        )
    if replay_report is None or replay_repository_sha is None:
        raise ReplayRevalidationFulfilmentError(
            "replay report and replay repository SHA must be supplied together"
        )
    replay_sha = _git_sha(
        replay_repository_sha,
        field="replay_repository_sha",
    )
    if replay_sha != candidate_sha:
        raise ReplayRevalidationFulfilmentError(
            "replay evidence was not produced for the exact candidate repository SHA"
        )
    try:
        report_digest = verify_report(replay_report)
    except VerificationError as exc:
        raise ReplayRevalidationFulfilmentError(
            f"invalid LRD-01K replay evidence: {exc}"
        ) from exc
    _verify_plan_matches_candidate(report=replay_report, candidate=candidate)
    failures = _replay_failures(replay_report)
    if failures:
        return _result(
            decision=decision,
            candidate=candidate,
            candidate_repository_sha=candidate_sha,
            replay_repository_sha=replay_sha,
            replay_report_digest=report_digest,
            state=ReplayRevalidationFulfilmentState.REVALIDATION_FAILED,
            violations=failures,
        )
    return _result(
        decision=decision,
        candidate=candidate,
        candidate_repository_sha=candidate_sha,
        replay_repository_sha=replay_sha,
        replay_report_digest=report_digest,
        state=ReplayRevalidationFulfilmentState.REVALIDATED,
        violations=(),
    )


def verify_revalidation_fulfilment_v1(
    fulfilment: ReplayRevalidationFulfilmentV1,
    *,
    decision: ReplayRevalidationDecisionV1,
    baseline: ReplayRevalidationFingerprintV1 | None,
    candidate: ReplayRevalidationFingerprintV1,
    baseline_runtime_identity: RuntimeIdentity | None,
    candidate_runtime_identity: RuntimeIdentity,
    candidate_repository_sha: str,
    replay_report: Mapping[str, object] | None = None,
    replay_repository_sha: str | None = None,
) -> str:
    """Recompute fulfilment from exact upstream evidence and return its identity."""
    expected = evaluate_revalidation_fulfilment_v1(
        decision=decision,
        baseline=baseline,
        candidate=candidate,
        baseline_runtime_identity=baseline_runtime_identity,
        candidate_runtime_identity=candidate_runtime_identity,
        candidate_repository_sha=candidate_repository_sha,
        replay_report=replay_report,
        replay_repository_sha=replay_repository_sha,
    )
    if fulfilment.canonical_dict() != expected.canonical_dict():
        raise ReplayRevalidationFulfilmentError(
            "revalidation fulfilment evidence mismatch"
        )
    return fulfilment.fulfilment_digest
