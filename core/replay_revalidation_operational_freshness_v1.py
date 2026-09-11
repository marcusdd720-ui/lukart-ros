"""LRD-01 periodic-freshness gate for the operational revalidation handoff v1.

This module composes the already-authoritative LRD-01L freshness evaluation with
LRD-01S. It does not choose cadence, read the wall clock, schedule or execute
replay, detect repository changes, or gain Product/CCL/provider/storage/release
authority.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from core.cross_environment_replay_verifier_v1 import VerificationError, verify_report
from core.p3.contracts import RuntimeIdentity
from core.periodic_replay_revalidation_v1 import (
    PeriodicReplayCadencePolicyV1,
    PeriodicReplayError,
    PeriodicReplayEvaluationV1,
    PeriodicReplayObservationV1,
    PeriodicReplayState,
    evaluate_periodic_replay_v1,
)
from core.replay_revalidation_baseline_selection_v1 import (
    ReplayRevalidationBaselineSelectionLedgerV1,
)
from core.replay_revalidation_invalidation_v1 import ReplayRevalidationFingerprintV1
from core.replay_revalidation_operational_handoff_v1 import (
    ReplayRevalidationOperationalHandoffError,
    ReplayRevalidationOperationalHandoffResultV1,
    execute_revalidation_operational_handoff_v1,
)


class ReplayRevalidationOperationalFreshnessError(ValueError):
    """Fail-closed periodic-freshness gate violation."""


@dataclass(frozen=True, slots=True)
class ReplayRevalidationOperationalFreshnessResultV1:
    """One accepted 01L freshness evaluation plus the resulting 01S handoff."""

    periodic_evaluation: PeriodicReplayEvaluationV1
    handoff: ReplayRevalidationOperationalHandoffResultV1

    def __post_init__(self) -> None:
        if self.periodic_evaluation.state not in {
            PeriodicReplayState.CURRENT,
            PeriodicReplayState.DUE,
        }:
            raise ReplayRevalidationOperationalFreshnessError(
                "accepted operational handoff requires CURRENT or DUE periodic freshness"
            )

    @property
    def selection_persistence_authority(self) -> bool:
        """Persistence remains delegated solely to the existing scoped 01S/01R path."""
        return self.handoff.selection_persistence_authority

    @property
    def scheduler_authority(self) -> bool:
        return False

    @property
    def repository_change_detection_authority(self) -> bool:
        return False

    @property
    def replay_execution_authority(self) -> bool:
        return False

    @property
    def cadence_policy_authority(self) -> bool:
        return False

    @property
    def mutable_pointer_authority(self) -> bool:
        return False

    @property
    def release_authority(self) -> bool:
        return False

    @property
    def product_write_authority(self) -> bool:
        return False

    @property
    def ccl_write_authority(self) -> bool:
        return False

    @property
    def storage_authority(self) -> bool:
        return False

    @property
    def provider_authority(self) -> bool:
        return False


def execute_fresh_revalidation_operational_handoff_v1(
    *,
    policy: PeriodicReplayCadencePolicyV1,
    evaluated_at: int,
    observations: Sequence[PeriodicReplayObservationV1],
    ledger: ReplayRevalidationBaselineSelectionLedgerV1,
    candidate: ReplayRevalidationFingerprintV1,
    candidate_runtime_identity: RuntimeIdentity,
    candidate_repository_sha: str,
    replay_report: Mapping[str, object] | None = None,
    replay_repository_sha: str | None = None,
) -> ReplayRevalidationOperationalFreshnessResultV1:
    """Require fresh exact 01L evidence before delegating unchanged inputs to 01S.

    CURRENT and DUE are accepted because 01L defines DUE as inside the warning
    window but not overdue. OVERDUE and UNVERIFIABLE are rejected before 01S can
    persist a selection. Time, cadence and observations are explicit caller inputs.
    """
    observation_chain = tuple(observations)
    try:
        evaluation = evaluate_periodic_replay_v1(
            policy=policy,
            evaluated_at=evaluated_at,
            observations=observation_chain,
        )
    except PeriodicReplayError as exc:
        raise ReplayRevalidationOperationalFreshnessError(
            f"cannot verify periodic replay freshness: {exc}"
        ) from exc

    if evaluation.state not in {PeriodicReplayState.CURRENT, PeriodicReplayState.DUE}:
        violations = ",".join(evaluation.violations) or "periodic_replay_not_fresh"
        raise ReplayRevalidationOperationalFreshnessError(
            f"periodic replay freshness rejected: {evaluation.state.value}: {violations}"
        )

    latest = observation_chain[-1]
    if latest.repository_sha != candidate_repository_sha:
        raise ReplayRevalidationOperationalFreshnessError(
            "periodic replay repository SHA does not match candidate repository SHA"
        )
    if latest.lrd01i_bundle_digest != candidate.lrd01i_bundle_digest:
        raise ReplayRevalidationOperationalFreshnessError(
            "periodic replay bundle identity does not match candidate fingerprint"
        )

    if replay_report is not None:
        try:
            replay_report_digest = verify_report(replay_report)
        except VerificationError as exc:
            raise ReplayRevalidationOperationalFreshnessError(
                f"cannot verify supplied replay report: {exc}"
            ) from exc
        if replay_report_digest != latest.cross_environment_report_digest:
            raise ReplayRevalidationOperationalFreshnessError(
                "periodic replay report identity does not match supplied replay report"
            )

    try:
        handoff = execute_revalidation_operational_handoff_v1(
            ledger=ledger,
            candidate=candidate,
            candidate_runtime_identity=candidate_runtime_identity,
            candidate_repository_sha=candidate_repository_sha,
            replay_report=replay_report,
            replay_repository_sha=replay_repository_sha,
        )
    except ReplayRevalidationOperationalHandoffError as exc:
        raise ReplayRevalidationOperationalFreshnessError(
            f"fresh operational handoff failed: {exc}"
        ) from exc

    return ReplayRevalidationOperationalFreshnessResultV1(
        periodic_evaluation=evaluation,
        handoff=handoff,
    )
