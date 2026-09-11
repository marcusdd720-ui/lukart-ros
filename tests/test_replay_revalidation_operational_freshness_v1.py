from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.enterprise.durability import SQLiteProvenanceStore
from core.periodic_replay_revalidation_v1 import (
    PeriodicReplayCadencePolicyV1,
    PeriodicReplayObservationV1,
    PeriodicReplayState,
    build_periodic_replay_observation_v1,
)
from core.replay_revalidation_baseline_lineage_v1 import ReplayRevalidationBaselineLineageV1
from core.replay_revalidation_baseline_selection_v1 import (
    ReplayRevalidationBaselineSelectionLedgerV1,
)
from core.replay_revalidation_baseline_transition_v1 import (
    ReplayRevalidationBaselineTransitionState,
)
from core.replay_revalidation_operational_freshness_v1 import (
    ReplayRevalidationOperationalFreshnessError,
    execute_fresh_revalidation_operational_handoff_v1,
)
from tests.test_periodic_replay_revalidation_v1 import CASE_ID, _health
from tests.test_replay_revalidation_baseline_transition_v1 import (
    _baseline,
    _changed_material,
    h,
)


def _policy() -> PeriodicReplayCadencePolicyV1:
    return PeriodicReplayCadencePolicyV1(
        effective_at=0,
        max_replay_age_seconds=1000,
        due_window_seconds=200,
    )


def _periodic_observation(
    *,
    repository_sha: str,
    replay_report: dict[str, object],
    observed_at: int = 1000,
    previous: PeriodicReplayObservationV1 | None = None,
) -> PeriodicReplayObservationV1:
    return build_periodic_replay_observation_v1(
        case_id=CASE_ID,
        repository_sha=repository_sha,
        observed_at=observed_at,
        cross_environment_report=replay_report,
        long_range_health_report=_health(evaluated_at=min(990, observed_at)),
        previous=previous,
    )


def _ledger_with_genesis(
    path: Path,
) -> tuple[SQLiteProvenanceStore, ReplayRevalidationBaselineSelectionLedgerV1]:
    baseline, _ = _baseline()
    store = SQLiteProvenanceStore(path)
    ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
    ledger.append(ReplayRevalidationBaselineLineageV1.build(genesis_baseline=baseline))
    return store, ledger


def test_current_periodic_evidence_allows_exact_baseline_reuse(tmp_path: Path) -> None:
    baseline, _ = _baseline()
    observation = _periodic_observation(
        repository_sha=baseline.repository_sha,
        replay_report=baseline.replay_report,
    )
    store, ledger = _ledger_with_genesis(tmp_path / "freshness.db")
    try:
        result = execute_fresh_revalidation_operational_handoff_v1(
            policy=_policy(),
            evaluated_at=1100,
            observations=(observation,),
            ledger=ledger,
            candidate=baseline.fingerprint,
            candidate_runtime_identity=baseline.runtime_identity,
            candidate_repository_sha=baseline.repository_sha,
        )
        assert result.periodic_evaluation.state is PeriodicReplayState.CURRENT
        assert result.handoff.transition.state is (
            ReplayRevalidationBaselineTransitionState.BASELINE_REUSED
        )
        assert len(ledger.selections()) == 2
        assert result.selection_persistence_authority is True
        assert result.scheduler_authority is False
        assert result.repository_change_detection_authority is False
        assert result.replay_execution_authority is False
        assert result.cadence_policy_authority is False
        assert result.mutable_pointer_authority is False
        assert result.release_authority is False
        assert result.product_write_authority is False
        assert result.ccl_write_authority is False
        assert result.storage_authority is False
        assert result.provider_authority is False
    finally:
        store.close()


def test_due_periodic_evidence_remains_eligible_until_overdue(tmp_path: Path) -> None:
    baseline, _ = _baseline()
    observation = _periodic_observation(
        repository_sha=baseline.repository_sha,
        replay_report=baseline.replay_report,
    )
    store, ledger = _ledger_with_genesis(tmp_path / "freshness.db")
    try:
        result = execute_fresh_revalidation_operational_handoff_v1(
            policy=_policy(),
            evaluated_at=1800,
            observations=(observation,),
            ledger=ledger,
            candidate=baseline.fingerprint,
            candidate_runtime_identity=baseline.runtime_identity,
            candidate_repository_sha=baseline.repository_sha,
        )
        assert result.periodic_evaluation.state is PeriodicReplayState.DUE
        assert result.handoff.transition.state is (
            ReplayRevalidationBaselineTransitionState.BASELINE_REUSED
        )
    finally:
        store.close()


def test_overdue_periodic_evidence_blocks_before_selection_persistence(tmp_path: Path) -> None:
    baseline, _ = _baseline()
    observation = _periodic_observation(
        repository_sha=baseline.repository_sha,
        replay_report=baseline.replay_report,
    )
    store, ledger = _ledger_with_genesis(tmp_path / "freshness.db")
    try:
        prior = ledger.current_selection()
        with pytest.raises(
            ReplayRevalidationOperationalFreshnessError,
            match="OVERDUE: periodic_replay_overdue",
        ):
            execute_fresh_revalidation_operational_handoff_v1(
                policy=_policy(),
                evaluated_at=2001,
                observations=(observation,),
                ledger=ledger,
                candidate=baseline.fingerprint,
                candidate_runtime_identity=baseline.runtime_identity,
                candidate_repository_sha=baseline.repository_sha,
            )
        assert ledger.current_selection() == prior
        assert len(ledger.selections()) == 1
    finally:
        store.close()


def test_unverifiable_periodic_evidence_blocks_before_selection_persistence(
    tmp_path: Path,
) -> None:
    baseline, _ = _baseline()
    store, ledger = _ledger_with_genesis(tmp_path / "freshness.db")
    try:
        prior = ledger.current_selection()
        with pytest.raises(
            ReplayRevalidationOperationalFreshnessError,
            match="UNVERIFIABLE: periodic_replay_observation_missing",
        ):
            execute_fresh_revalidation_operational_handoff_v1(
                policy=_policy(),
                evaluated_at=500,
                observations=(),
                ledger=ledger,
                candidate=baseline.fingerprint,
                candidate_runtime_identity=baseline.runtime_identity,
                candidate_repository_sha=baseline.repository_sha,
            )
        assert ledger.current_selection() == prior
        assert len(ledger.selections()) == 1
    finally:
        store.close()


def test_freshness_repository_substitution_fails_before_handoff(tmp_path: Path) -> None:
    baseline, _ = _baseline()
    observation = _periodic_observation(
        repository_sha=baseline.repository_sha,
        replay_report=baseline.replay_report,
    )
    store, ledger = _ledger_with_genesis(tmp_path / "freshness.db")
    try:
        with pytest.raises(
            ReplayRevalidationOperationalFreshnessError,
            match="repository SHA does not match",
        ):
            execute_fresh_revalidation_operational_handoff_v1(
                policy=_policy(),
                evaluated_at=1100,
                observations=(observation,),
                ledger=ledger,
                candidate=baseline.fingerprint,
                candidate_runtime_identity=baseline.runtime_identity,
                candidate_repository_sha="b" * 40,
            )
        assert len(ledger.selections()) == 1
    finally:
        store.close()


def test_freshness_bundle_substitution_fails_before_handoff(tmp_path: Path) -> None:
    baseline, _ = _baseline()
    observation = _periodic_observation(
        repository_sha=baseline.repository_sha,
        replay_report=baseline.replay_report,
    )
    substituted = replace(observation, lrd01i_bundle_digest=h("other-bundle"))
    store, ledger = _ledger_with_genesis(tmp_path / "freshness.db")
    try:
        with pytest.raises(
            ReplayRevalidationOperationalFreshnessError,
            match="bundle identity does not match",
        ):
            execute_fresh_revalidation_operational_handoff_v1(
                policy=_policy(),
                evaluated_at=1100,
                observations=(substituted,),
                ledger=ledger,
                candidate=baseline.fingerprint,
                candidate_runtime_identity=baseline.runtime_identity,
                candidate_repository_sha=baseline.repository_sha,
            )
        assert len(ledger.selections()) == 1
    finally:
        store.close()


def test_supplied_replay_must_match_latest_periodic_report_identity(tmp_path: Path) -> None:
    baseline, candidate, runtime, report = _changed_material()
    observation = _periodic_observation(
        repository_sha=runtime.code_sha,
        replay_report=report,
    )
    substituted = replace(
        observation,
        cross_environment_report_digest=h("different-periodic-report"),
    )
    store, ledger = _ledger_with_genesis(tmp_path / "freshness.db")
    try:
        with pytest.raises(
            ReplayRevalidationOperationalFreshnessError,
            match="report identity does not match",
        ):
            execute_fresh_revalidation_operational_handoff_v1(
                policy=_policy(),
                evaluated_at=1100,
                observations=(substituted,),
                ledger=ledger,
                candidate=candidate,
                candidate_runtime_identity=runtime,
                candidate_repository_sha=runtime.code_sha,
                replay_report=report,
                replay_repository_sha=runtime.code_sha,
            )
        assert len(ledger.selections()) == 1
        current = ledger.current_selection()
        assert current is not None
        assert current.current_baseline_digest == baseline.baseline_digest
    finally:
        store.close()


def test_fresh_changed_candidate_with_matching_replay_advances_baseline(tmp_path: Path) -> None:
    baseline, candidate, runtime, report = _changed_material()
    observation = _periodic_observation(
        repository_sha=runtime.code_sha,
        replay_report=report,
    )
    store, ledger = _ledger_with_genesis(tmp_path / "freshness.db")
    try:
        result = execute_fresh_revalidation_operational_handoff_v1(
            policy=_policy(),
            evaluated_at=1100,
            observations=(observation,),
            ledger=ledger,
            candidate=candidate,
            candidate_runtime_identity=runtime,
            candidate_repository_sha=runtime.code_sha,
            replay_report=report,
            replay_repository_sha=runtime.code_sha,
        )
        assert result.periodic_evaluation.state is PeriodicReplayState.CURRENT
        assert result.handoff.transition.state is (
            ReplayRevalidationBaselineTransitionState.BASELINE_ADVANCED
        )
        assert result.handoff.selected_lineage.current_baseline_digest != baseline.baseline_digest
        assert result.handoff.selected_lineage.current_repository_sha == runtime.code_sha
    finally:
        store.close()
