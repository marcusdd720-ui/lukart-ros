from __future__ import annotations

from pathlib import Path

import pytest

from core.enterprise.durability import SQLiteProvenanceStore
from core.replay_revalidation_baseline_lineage_v1 import (
    ReplayRevalidationBaselineLineageV1,
)
from core.replay_revalidation_baseline_selection_v1 import (
    ReplayRevalidationBaselineSelectionLedgerV1,
)
from core.replay_revalidation_baseline_transition_v1 import (
    ReplayRevalidationBaselineTransitionState,
)
from core.replay_revalidation_fulfilment_v1 import ReplayRevalidationFulfilmentState
from core.replay_revalidation_invalidation_v1 import ReplayRevalidationState
from core.replay_revalidation_operational_handoff_v1 import (
    ReplayRevalidationOperationalHandoffError,
    execute_revalidation_operational_handoff_v1,
)
from tests.test_replay_revalidation_baseline_transition_v1 import (
    _baseline,
    _changed_material,
    _fingerprint,
    _runtime,
)
from tests.test_replay_revalidation_candidate_snapshot_v1 import _snapshot


def _ledger_with_genesis(
    path: Path,
) -> tuple[SQLiteProvenanceStore, ReplayRevalidationBaselineSelectionLedgerV1]:
    baseline, _ = _baseline()
    store = SQLiteProvenanceStore(path)
    ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
    ledger.append(ReplayRevalidationBaselineLineageV1.build(genesis_baseline=baseline))
    return store, ledger


def test_candidate_snapshot_handoff_inputs_compose_with_operational_handoff(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot()
    candidate, candidate_runtime, repository_sha = snapshot.handoff_inputs()
    store, ledger = _ledger_with_genesis(tmp_path / "handoff.db")
    try:
        prior = ledger.current_selection()
        assert prior is not None
        result = execute_revalidation_operational_handoff_v1(
            ledger=ledger,
            candidate=candidate,
            candidate_runtime_identity=candidate_runtime,
            candidate_repository_sha=repository_sha,
        )
        assert result.decision.state is ReplayRevalidationState.REVALIDATION_REQUIRED
        assert (
            result.decision.candidate_fingerprint_digest
            == snapshot.fingerprint.fingerprint_digest
        )
        assert result.fulfilment.state is ReplayRevalidationFulfilmentState.REVALIDATION_REQUIRED
        assert (
            result.fulfilment.candidate_fingerprint_digest
            == snapshot.fingerprint.fingerprint_digest
        )
        assert result.fulfilment.candidate_repository_sha == snapshot.candidate_repository_sha
        assert result.transition.state is (
            ReplayRevalidationBaselineTransitionState.REVALIDATION_REQUIRED
        )
        assert result.selected_lineage.current_baseline == prior.lineage.current_baseline
    finally:
        store.close()


def test_handoff_requires_existing_selected_lineage(tmp_path: Path) -> None:
    baseline, plan = _baseline()
    with SQLiteProvenanceStore(tmp_path / "handoff.db") as store:
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
        with pytest.raises(
            ReplayRevalidationOperationalHandoffError,
            match="requires an existing selected baseline lineage",
        ):
            execute_revalidation_operational_handoff_v1(
                ledger=ledger,
                candidate=_fingerprint(baseline.runtime_identity, plan),
                candidate_runtime_identity=baseline.runtime_identity,
                candidate_repository_sha=baseline.repository_sha,
            )


def test_unchanged_candidate_reuses_baseline_and_persists_strict_extension(
    tmp_path: Path,
) -> None:
    store, ledger = _ledger_with_genesis(tmp_path / "handoff.db")
    try:
        prior = ledger.current_selection()
        assert prior is not None
        baseline = prior.lineage.current_baseline
        result = execute_revalidation_operational_handoff_v1(
            ledger=ledger,
            candidate=baseline.fingerprint,
            candidate_runtime_identity=baseline.runtime_identity,
            candidate_repository_sha=baseline.repository_sha,
        )
        assert result.decision.state is ReplayRevalidationState.UNCHANGED
        assert result.fulfilment.state is ReplayRevalidationFulfilmentState.BASELINE_REUSABLE
        assert result.transition.state is ReplayRevalidationBaselineTransitionState.BASELINE_REUSED
        assert result.selected_lineage.transition_count == prior.lineage.transition_count + 1
        assert result.selected_lineage.current_baseline == baseline
        assert ledger.current_selection() == result.resulting_selection
        assert result.resulting_selection.previous_selection_digest == prior.selection_digest
    finally:
        store.close()


def test_changed_candidate_without_replay_persists_blocked_attempt_without_advancing(
    tmp_path: Path,
) -> None:
    baseline, candidate, runtime, _ = _changed_material()
    store = SQLiteProvenanceStore(tmp_path / "handoff.db")
    try:
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
        initial = ReplayRevalidationBaselineLineageV1.build(genesis_baseline=baseline)
        prior = ledger.append(initial)
        result = execute_revalidation_operational_handoff_v1(
            ledger=ledger,
            candidate=candidate,
            candidate_runtime_identity=runtime,
            candidate_repository_sha=runtime.code_sha,
        )
        assert result.decision.state is ReplayRevalidationState.REVALIDATION_REQUIRED
        assert result.fulfilment.state is ReplayRevalidationFulfilmentState.REVALIDATION_REQUIRED
        assert result.transition.state is (
            ReplayRevalidationBaselineTransitionState.REVALIDATION_REQUIRED
        )
        assert result.selected_lineage.blocked_attempt_count == 1
        assert result.selected_lineage.current_baseline_digest == baseline.baseline_digest
        assert result.resulting_selection.current_repository_sha == baseline.repository_sha
        assert result.resulting_selection.previous_selection_digest == prior.selection_digest
    finally:
        store.close()


def test_changed_candidate_with_verified_replay_advances_and_persists_baseline(
    tmp_path: Path,
) -> None:
    baseline, candidate, runtime, report = _changed_material()
    store = SQLiteProvenanceStore(tmp_path / "handoff.db")
    try:
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
        ledger.append(ReplayRevalidationBaselineLineageV1.build(genesis_baseline=baseline))
        result = execute_revalidation_operational_handoff_v1(
            ledger=ledger,
            candidate=candidate,
            candidate_runtime_identity=runtime,
            candidate_repository_sha=runtime.code_sha,
            replay_report=report,
            replay_repository_sha=runtime.code_sha,
        )
        assert result.fulfilment.state is ReplayRevalidationFulfilmentState.REVALIDATED
        assert result.transition.state is (
            ReplayRevalidationBaselineTransitionState.BASELINE_ADVANCED
        )
        assert result.selected_lineage.baseline_advance_count == 1
        assert result.selected_lineage.current_repository_sha == runtime.code_sha
        assert result.resulting_selection.current_repository_sha == runtime.code_sha
        assert result.resulting_selection.current_baseline_digest != baseline.baseline_digest
    finally:
        store.close()


def test_duplicate_identical_blocked_handoff_fails_closed_without_second_selection(
    tmp_path: Path,
) -> None:
    baseline, candidate, runtime, _ = _changed_material()
    store = SQLiteProvenanceStore(tmp_path / "handoff.db")
    try:
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
        ledger.append(ReplayRevalidationBaselineLineageV1.build(genesis_baseline=baseline))
        first = execute_revalidation_operational_handoff_v1(
            ledger=ledger,
            candidate=candidate,
            candidate_runtime_identity=runtime,
            candidate_repository_sha=runtime.code_sha,
        )
        with pytest.raises(ReplayRevalidationOperationalHandoffError, match="duplicate transition"):
            execute_revalidation_operational_handoff_v1(
                ledger=ledger,
                candidate=candidate,
                candidate_runtime_identity=runtime,
                candidate_repository_sha=runtime.code_sha,
            )
        assert ledger.current_selection() == first.resulting_selection
        assert len(ledger.selections()) == 2
    finally:
        store.close()


def test_candidate_repository_substitution_fails_before_persistence(tmp_path: Path) -> None:
    baseline, candidate, runtime, _ = _changed_material()
    store = SQLiteProvenanceStore(tmp_path / "handoff.db")
    try:
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
        ledger.append(ReplayRevalidationBaselineLineageV1.build(genesis_baseline=baseline))
        prior = ledger.current_selection()
        with pytest.raises(
            ReplayRevalidationOperationalHandoffError,
            match="substitution|repository SHA",
        ):
            execute_revalidation_operational_handoff_v1(
                ledger=ledger,
                candidate=candidate,
                candidate_runtime_identity=runtime,
                candidate_repository_sha="c" * 40,
            )
        assert ledger.current_selection() == prior
        assert len(ledger.selections()) == 1
    finally:
        store.close()


def test_candidate_fingerprint_runtime_substitution_fails_before_persistence(
    tmp_path: Path,
) -> None:
    baseline, plan = _baseline()
    store = SQLiteProvenanceStore(tmp_path / "handoff.db")
    try:
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
        ledger.append(ReplayRevalidationBaselineLineageV1.build(genesis_baseline=baseline))
        candidate_runtime = _runtime("b" * 40)
        substituted_runtime = _runtime("c" * 40)
        candidate = _fingerprint(candidate_runtime, plan)
        with pytest.raises(
            ReplayRevalidationOperationalHandoffError,
            match="substitution",
        ):
            execute_revalidation_operational_handoff_v1(
                ledger=ledger,
                candidate=candidate,
                candidate_runtime_identity=substituted_runtime,
                candidate_repository_sha=substituted_runtime.code_sha,
            )
        assert len(ledger.selections()) == 1
    finally:
        store.close()


def test_handoff_does_not_gain_unapproved_authority(tmp_path: Path) -> None:
    store, ledger = _ledger_with_genesis(tmp_path / "handoff.db")
    try:
        selection = ledger.current_selection()
        assert selection is not None
        baseline = selection.lineage.current_baseline
        result = execute_revalidation_operational_handoff_v1(
            ledger=ledger,
            candidate=baseline.fingerprint,
            candidate_runtime_identity=baseline.runtime_identity,
            candidate_repository_sha=baseline.repository_sha,
        )
        assert result.selection_persistence_authority is True
        assert result.scheduler_authority is False
        assert result.repository_change_detection_authority is False
        assert result.replay_execution_authority is False
        assert result.mutable_pointer_authority is False
        assert result.release_authority is False
        assert result.product_write_authority is False
        assert result.ccl_write_authority is False
        assert result.storage_authority is False
        assert result.provider_authority is False
    finally:
        store.close()
