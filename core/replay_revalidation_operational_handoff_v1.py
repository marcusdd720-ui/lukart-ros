"""LRD-01S bounded replay-revalidation operational handoff v1.

This module composes the already-authoritative LRD-01M/01N/01P/01Q/01R
contracts into one fail-closed local handoff. It starts from the durably selected
01R lineage, evaluates supplied candidate evidence, derives one 01P transition,
appends that transition to the immutable 01Q lineage and persists the resulting
strict lineage extension through 01R.

It does not detect repository changes, schedule or execute replay, mutate
Product/CCL state, create a mutable latest pointer, grant provider/storage
or release authority, or introduce another persistence subsystem.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from core.p3.contracts import RuntimeIdentity
from core.replay_revalidation_baseline_lineage_v1 import (
    ReplayRevalidationBaselineLineageEntryV1,
    ReplayRevalidationBaselineLineageError,
    ReplayRevalidationBaselineLineageV1,
)
from core.replay_revalidation_baseline_selection_v1 import (
    ReplayRevalidationBaselineSelectionError,
    ReplayRevalidationBaselineSelectionLedgerV1,
    ReplayRevalidationBaselineSelectionV1,
)
from core.replay_revalidation_baseline_transition_v1 import (
    ReplayRevalidationBaselineTransitionError,
    ReplayRevalidationBaselineTransitionV1,
    evaluate_revalidation_baseline_transition_v1,
)
from core.replay_revalidation_fulfilment_v1 import (
    ReplayRevalidationFulfilmentError,
    ReplayRevalidationFulfilmentV1,
    evaluate_revalidation_fulfilment_v1,
)
from core.replay_revalidation_invalidation_v1 import (
    ReplayRevalidationDecisionV1,
    ReplayRevalidationError,
    ReplayRevalidationFingerprintV1,
    evaluate_revalidation_requirement_v1,
)


class ReplayRevalidationOperationalHandoffError(ValueError):
    """Fail-closed LRD-01S contract violation."""


@dataclass(frozen=True, slots=True)
class ReplayRevalidationOperationalHandoffResultV1:
    """Observed result of one bounded handoff into the durable selected lineage."""

    prior_selection: ReplayRevalidationBaselineSelectionV1
    decision: ReplayRevalidationDecisionV1
    fulfilment: ReplayRevalidationFulfilmentV1
    transition: ReplayRevalidationBaselineTransitionV1
    selected_lineage: ReplayRevalidationBaselineLineageV1
    resulting_selection: ReplayRevalidationBaselineSelectionV1

    def __post_init__(self) -> None:
        if (
            self.resulting_selection.previous_selection_digest
            != self.prior_selection.selection_digest
        ):
            raise ReplayRevalidationOperationalHandoffError(
                "resulting selection is not chained to the exact prior selection"
            )
        if self.resulting_selection.lineage != self.selected_lineage:
            raise ReplayRevalidationOperationalHandoffError(
                "resulting selection/lineage identity mismatch"
            )
        if not self.selected_lineage.entries:
            raise ReplayRevalidationOperationalHandoffError(
                "handoff lineage must contain the derived transition"
            )
        if self.selected_lineage.entries[-1].transition != self.transition:
            raise ReplayRevalidationOperationalHandoffError(
                "handoff transition is not the selected lineage tail"
            )

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

    @property
    def selection_persistence_authority(self) -> bool:
        """Persistence is delegated solely to the existing scoped 01R ledger."""
        return True


def execute_revalidation_operational_handoff_v1(
    *,
    ledger: ReplayRevalidationBaselineSelectionLedgerV1,
    candidate: ReplayRevalidationFingerprintV1,
    candidate_runtime_identity: RuntimeIdentity,
    candidate_repository_sha: str,
    replay_report: Mapping[str, object] | None = None,
    replay_repository_sha: str | None = None,
) -> ReplayRevalidationOperationalHandoffResultV1:
    """Compose 01M→01N→01P→01Q→01R from the exact currently selected lineage.

    Candidate identity and optional replay evidence are supplied by the caller.
    This function performs no change detection or replay execution. A blocked
    transition is still appended and durably selected as lineage evidence, but
    cannot advance the current verified baseline.
    """
    if not isinstance(ledger, ReplayRevalidationBaselineSelectionLedgerV1):
        raise ReplayRevalidationOperationalHandoffError(
            "handoff requires ReplayRevalidationBaselineSelectionLedgerV1"
        )

    try:
        prior_selection = ledger.current_selection()
    except ReplayRevalidationBaselineSelectionError as exc:
        raise ReplayRevalidationOperationalHandoffError(
            f"cannot verify current selected lineage: {exc}"
        ) from exc
    if prior_selection is None:
        raise ReplayRevalidationOperationalHandoffError(
            "operational handoff requires an existing selected baseline lineage"
        )

    prior_lineage = prior_selection.lineage
    prior_baseline = prior_lineage.current_baseline
    baseline_fingerprint, baseline_runtime_identity = prior_baseline.invalidation_inputs()

    try:
        decision = evaluate_revalidation_requirement_v1(
            baseline=baseline_fingerprint,
            candidate=candidate,
            baseline_runtime_identity=baseline_runtime_identity,
            candidate_runtime_identity=candidate_runtime_identity,
        )
        fulfilment = evaluate_revalidation_fulfilment_v1(
            decision=decision,
            baseline=baseline_fingerprint,
            candidate=candidate,
            baseline_runtime_identity=baseline_runtime_identity,
            candidate_runtime_identity=candidate_runtime_identity,
            candidate_repository_sha=candidate_repository_sha,
            replay_report=replay_report,
            replay_repository_sha=replay_repository_sha,
        )
        transition_evaluation = evaluate_revalidation_baseline_transition_v1(
            prior_baseline=prior_baseline,
            decision=decision,
            fulfilment=fulfilment,
            candidate=candidate,
            candidate_runtime_identity=candidate_runtime_identity,
            candidate_repository_sha=candidate_repository_sha,
            replay_report=replay_report,
            replay_repository_sha=replay_repository_sha,
        )
        entry = ReplayRevalidationBaselineLineageEntryV1(
            transition=transition_evaluation.transition,
            resulting_baseline=transition_evaluation.resulting_baseline,
        )
        selected_lineage = prior_lineage.append(entry)
    except (
        ReplayRevalidationError,
        ReplayRevalidationFulfilmentError,
        ReplayRevalidationBaselineTransitionError,
        ReplayRevalidationBaselineLineageError,
    ) as exc:
        raise ReplayRevalidationOperationalHandoffError(
            f"revalidation handoff evaluation failed: {exc}"
        ) from exc

    try:
        resulting_selection = ledger.append(selected_lineage)
    except ReplayRevalidationBaselineSelectionError as exc:
        raise ReplayRevalidationOperationalHandoffError(
            f"revalidation handoff selection failed: {exc}"
        ) from exc

    return ReplayRevalidationOperationalHandoffResultV1(
        prior_selection=prior_selection,
        decision=decision,
        fulfilment=fulfilment,
        transition=transition_evaluation.transition,
        selected_lineage=selected_lineage,
        resulting_selection=resulting_selection,
    )
