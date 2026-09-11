from __future__ import annotations

import copy
from pathlib import Path

import pytest

from core.cross_environment_replay_v1 import (
    ReplayExecutionStatus,
    build_replay_receipt,
    build_replay_report,
)
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
from core.replay_revalidation_selected_handoff_v1 import (
    ReplayRevalidationSelectedHandoffError,
    ReplayRevalidationSelectedHandoffV1,
    execute_selected_baseline_revalidation_handoff_v1,
    verify_selected_baseline_revalidation_handoff_v1,
)
from tests.test_replay_revalidation_baseline_transition_v1 import (
    _baseline,
    _changed_material,
)


def _ledger_with_baseline(
    store: SQLiteProvenanceStore,
    baseline: object,
) -> ReplayRevalidationBaselineSelectionLedgerV1:
    lineage = ReplayRevalidationBaselineLineageV1.build(genesis_baseline=baseline)  # type: ignore[arg-type]
    ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
    ledger.append(lineage)
    return ledger


def _semantic_drift_report(report: dict[str, object]) -> dict[str, object]:
    plan = report["plan"]
    profiles = report["profiles"]
    observed = report["observed_environments"]
    assert isinstance(plan, dict)
    assert isinstance(profiles, list)
    assert isinstance(observed, list)
    observed_by_profile = {
        str(item["declared_profile_digest"]): item
        for item in observed
        if isinstance(item, dict)
    }
    receipts: list[dict[str, object]] = []
    for profile in profiles:
        assert isinstance(profile, dict)
        profile_digest = str(profile["profile_digest"])
        receipts.append(
            build_replay_receipt(
                plan=plan,
                profile=profile,
                observed=observed_by_profile[profile_digest],
                verifier_digest=str(profile["replay_verifier_digest"]),
                semantic_result_identity="1" * 64,
                invariant_report_identity="2" * 64,
                lrd01d_classification="SEMANTIC_DRIFT",
                execution_status=ReplayExecutionStatus.VERIFIED,
            )
        )
    return build_replay_report(
        plan=plan,
        profiles=profiles,
        observed_environments=observed,
        receipts=receipts,
    )


def test_missing_current_selection_fails_closed_without_write(tmp_path: Path) -> None:
    _, candidate, runtime, _ = _changed_material()
    with SQLiteProvenanceStore(tmp_path / "handoff.db") as store:
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
        with pytest.raises(
            ReplayRevalidationSelectedHandoffError,
            match="explicit LRD-01R bootstrap",
        ):
            execute_selected_baseline_revalidation_handoff_v1(
                ledger=ledger,
                candidate=candidate,
                candidate_runtime_identity=runtime,
                candidate_repository_sha=runtime.code_sha,
            )
        assert store.verify() == ()


def test_unchanged_candidate_reuses_and_selects_exact_baseline(tmp_path: Path) -> None:
    baseline, _ = _baseline()
    with SQLiteProvenanceStore(tmp_path / "handoff.db") as store:
        ledger = _ledger_with_baseline(store, baseline)
        source = ledger.current_selection()
        assert source is not None
        handoff = execute_selected_baseline_revalidation_handoff_v1(
            ledger=ledger,
            candidate=baseline.fingerprint,
            candidate_runtime_identity=baseline.runtime_identity,
            candidate_repository_sha=baseline.repository_sha,
        )
        assert handoff.source_selection == source
        assert handoff.transition_state is (
            ReplayRevalidationBaselineTransitionState.BASELINE_REUSED
        )
        assert handoff.baseline_changed is False
        assert handoff.persisted_selection.current_baseline_digest == baseline.baseline_digest
        assert ledger.current_selection() == handoff.persisted_selection
        assert len(handoff.persisted_selection.lineage.entries) == 1


def test_changed_without_replay_records_blocked_attempt_and_keeps_baseline(
    tmp_path: Path,
) -> None:
    baseline, candidate, runtime, _ = _changed_material()
    with SQLiteProvenanceStore(tmp_path / "handoff.db") as store:
        ledger = _ledger_with_baseline(store, baseline)
        handoff = execute_selected_baseline_revalidation_handoff_v1(
            ledger=ledger,
            candidate=candidate,
            candidate_runtime_identity=runtime,
            candidate_repository_sha=runtime.code_sha,
        )
        assert handoff.transition_state is (
            ReplayRevalidationBaselineTransitionState.REVALIDATION_REQUIRED
        )
        assert handoff.baseline_changed is False
        assert handoff.persisted_selection.current_baseline_digest == baseline.baseline_digest
        assert handoff.persisted_selection.current_repository_sha == baseline.repository_sha
        assert handoff.persisted_selection.lineage.blocked_attempt_count == 1


def test_valid_replay_after_blocked_attempt_advances_selected_baseline(
    tmp_path: Path,
) -> None:
    baseline, candidate, runtime, report = _changed_material()
    with SQLiteProvenanceStore(tmp_path / "handoff.db") as store:
        ledger = _ledger_with_baseline(store, baseline)
        blocked = execute_selected_baseline_revalidation_handoff_v1(
            ledger=ledger,
            candidate=candidate,
            candidate_runtime_identity=runtime,
            candidate_repository_sha=runtime.code_sha,
        )
        advanced = execute_selected_baseline_revalidation_handoff_v1(
            ledger=ledger,
            candidate=candidate,
            candidate_runtime_identity=runtime,
            candidate_repository_sha=runtime.code_sha,
            replay_report=report,
            replay_repository_sha=runtime.code_sha,
        )
        assert blocked.transition_state is (
            ReplayRevalidationBaselineTransitionState.REVALIDATION_REQUIRED
        )
        assert advanced.source_selection == blocked.persisted_selection
        assert advanced.transition_state is (
            ReplayRevalidationBaselineTransitionState.BASELINE_ADVANCED
        )
        assert advanced.baseline_changed is True
        assert advanced.persisted_selection.current_repository_sha == runtime.code_sha
        assert advanced.persisted_selection.lineage.transition_count == 2
        assert advanced.persisted_selection.lineage.baseline_advance_count == 1


def test_valid_replay_can_advance_directly(tmp_path: Path) -> None:
    baseline, candidate, runtime, report = _changed_material()
    with SQLiteProvenanceStore(tmp_path / "handoff.db") as store:
        ledger = _ledger_with_baseline(store, baseline)
        handoff = execute_selected_baseline_revalidation_handoff_v1(
            ledger=ledger,
            candidate=candidate,
            candidate_runtime_identity=runtime,
            candidate_repository_sha=runtime.code_sha,
            replay_report=report,
            replay_repository_sha=runtime.code_sha,
        )
        assert handoff.transition_state is (
            ReplayRevalidationBaselineTransitionState.BASELINE_ADVANCED
        )
        assert handoff.persisted_selection.current_repository_sha == runtime.code_sha
        assert handoff.persisted_selection.current_baseline_digest != baseline.baseline_digest


def test_semantic_drift_is_persisted_as_blocked_failure(tmp_path: Path) -> None:
    baseline, candidate, runtime, report = _changed_material()
    drift_report = _semantic_drift_report(report)
    with SQLiteProvenanceStore(tmp_path / "handoff.db") as store:
        ledger = _ledger_with_baseline(store, baseline)
        handoff = execute_selected_baseline_revalidation_handoff_v1(
            ledger=ledger,
            candidate=candidate,
            candidate_runtime_identity=runtime,
            candidate_repository_sha=runtime.code_sha,
            replay_report=drift_report,
            replay_repository_sha=runtime.code_sha,
        )
        assert handoff.transition_state is (
            ReplayRevalidationBaselineTransitionState.REVALIDATION_FAILED
        )
        assert handoff.baseline_changed is False
        assert handoff.persisted_selection.current_baseline_digest == baseline.baseline_digest


def test_candidate_sha_substitution_fails_before_selection_write(tmp_path: Path) -> None:
    baseline, candidate, runtime, _ = _changed_material()
    with SQLiteProvenanceStore(tmp_path / "handoff.db") as store:
        ledger = _ledger_with_baseline(store, baseline)
        before = ledger.selections()
        with pytest.raises(ReplayRevalidationSelectedHandoffError):
            execute_selected_baseline_revalidation_handoff_v1(
                ledger=ledger,
                candidate=candidate,
                candidate_runtime_identity=runtime,
                candidate_repository_sha="c" * 40,
            )
        assert ledger.selections() == before


def test_stale_source_race_cannot_overwrite_competing_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline, candidate, runtime, _ = _changed_material()
    path = tmp_path / "handoff.db"
    first_store = SQLiteProvenanceStore(path)
    second_store = SQLiteProvenanceStore(path)
    try:
        first = _ledger_with_baseline(first_store, baseline)
        second = ReplayRevalidationBaselineSelectionLedgerV1(second_store)
        original_append = first.append
        raced = False

        def racing_append(lineage: ReplayRevalidationBaselineLineageV1):
            nonlocal raced
            if not raced:
                raced = True
                execute_selected_baseline_revalidation_handoff_v1(
                    ledger=second,
                    candidate=candidate,
                    candidate_runtime_identity=runtime,
                    candidate_repository_sha=runtime.code_sha,
                )
            return original_append(lineage)

        monkeypatch.setattr(first, "append", racing_append)
        with pytest.raises(
            ReplayRevalidationSelectedHandoffError,
            match="compare-and-append",
        ):
            execute_selected_baseline_revalidation_handoff_v1(
                ledger=first,
                candidate=candidate,
                candidate_runtime_identity=runtime,
                candidate_repository_sha=runtime.code_sha,
            )
        selections = second.selections()
        assert len(selections) == 2
        assert selections[-1].lineage.blocked_attempt_count == 1
    finally:
        first_store.close()
        second_store.close()


def test_duplicate_unchanged_transition_replay_fails_closed(tmp_path: Path) -> None:
    baseline, _ = _baseline()
    with SQLiteProvenanceStore(tmp_path / "handoff.db") as store:
        ledger = _ledger_with_baseline(store, baseline)
        execute_selected_baseline_revalidation_handoff_v1(
            ledger=ledger,
            candidate=baseline.fingerprint,
            candidate_runtime_identity=baseline.runtime_identity,
            candidate_repository_sha=baseline.repository_sha,
        )
        before = ledger.selections()
        with pytest.raises(
            ReplayRevalidationSelectedHandoffError,
            match="duplicate transition",
        ):
            execute_selected_baseline_revalidation_handoff_v1(
                ledger=ledger,
                candidate=baseline.fingerprint,
                candidate_runtime_identity=baseline.runtime_identity,
                candidate_repository_sha=baseline.repository_sha,
            )
        assert ledger.selections() == before


def test_handoff_receipt_round_trips_and_verifier_recomputes_evidence(
    tmp_path: Path,
) -> None:
    baseline, candidate, runtime, report = _changed_material()
    with SQLiteProvenanceStore(tmp_path / "handoff.db") as store:
        ledger = _ledger_with_baseline(store, baseline)
        source = ledger.current_selection()
        assert source is not None
        handoff = execute_selected_baseline_revalidation_handoff_v1(
            ledger=ledger,
            candidate=candidate,
            candidate_runtime_identity=runtime,
            candidate_repository_sha=runtime.code_sha,
            replay_report=report,
            replay_repository_sha=runtime.code_sha,
        )
        restored = ReplayRevalidationSelectedHandoffV1.from_dict(
            handoff.canonical_dict()
        )
        assert restored == handoff
        assert verify_selected_baseline_revalidation_handoff_v1(
            restored,
            source_selection=source,
            candidate=candidate,
            candidate_runtime_identity=runtime,
            candidate_repository_sha=runtime.code_sha,
            replay_report=report,
            replay_repository_sha=runtime.code_sha,
        ) == handoff.handoff_digest


def test_nested_receipt_tamper_and_authority_injection_fail_closed(
    tmp_path: Path,
) -> None:
    baseline, candidate, runtime, _ = _changed_material()
    with SQLiteProvenanceStore(tmp_path / "handoff.db") as store:
        ledger = _ledger_with_baseline(store, baseline)
        handoff = execute_selected_baseline_revalidation_handoff_v1(
            ledger=ledger,
            candidate=candidate,
            candidate_runtime_identity=runtime,
            candidate_repository_sha=runtime.code_sha,
        )
    nested = copy.deepcopy(handoff.canonical_dict())
    decision = nested["decision"]
    assert isinstance(decision, dict)
    decision["candidate_fingerprint_digest"] = "f" * 64
    with pytest.raises(ReplayRevalidationSelectedHandoffError):
        ReplayRevalidationSelectedHandoffV1.from_dict(nested)

    authority = copy.deepcopy(handoff.canonical_dict())
    authority["scheduler_authority"] = True
    with pytest.raises(
        ReplayRevalidationSelectedHandoffError,
        match="scheduler_authority",
    ):
        ReplayRevalidationSelectedHandoffV1.from_dict(authority)

    unknown = copy.deepcopy(handoff.canonical_dict())
    unknown["latest_baseline_pointer"] = handoff.persisted_selection_digest
    with pytest.raises(ReplayRevalidationSelectedHandoffError, match="unknown"):
        ReplayRevalidationSelectedHandoffV1.from_dict(unknown)


def test_verifier_rejects_candidate_or_replay_substitution(tmp_path: Path) -> None:
    baseline, candidate, runtime, report = _changed_material()
    with SQLiteProvenanceStore(tmp_path / "handoff.db") as store:
        ledger = _ledger_with_baseline(store, baseline)
        source = ledger.current_selection()
        assert source is not None
        handoff = execute_selected_baseline_revalidation_handoff_v1(
            ledger=ledger,
            candidate=candidate,
            candidate_runtime_identity=runtime,
            candidate_repository_sha=runtime.code_sha,
            replay_report=report,
            replay_repository_sha=runtime.code_sha,
        )
        with pytest.raises(ReplayRevalidationSelectedHandoffError):
            verify_selected_baseline_revalidation_handoff_v1(
                handoff,
                source_selection=source,
                candidate=candidate,
                candidate_runtime_identity=runtime,
                candidate_repository_sha="c" * 40,
                replay_report=report,
                replay_repository_sha=runtime.code_sha,
            )
        with pytest.raises(ReplayRevalidationSelectedHandoffError):
            verify_selected_baseline_revalidation_handoff_v1(
                handoff,
                source_selection=source,
                candidate=candidate,
                candidate_runtime_identity=runtime,
                candidate_repository_sha=runtime.code_sha,
                replay_report=report,
                replay_repository_sha="c" * 40,
            )


def test_unrelated_provenance_stream_does_not_change_handoff(tmp_path: Path) -> None:
    baseline, candidate, runtime, _ = _changed_material()
    with SQLiteProvenanceStore(tmp_path / "handoff.db") as store:
        ledger = _ledger_with_baseline(store, baseline)
        store.append(
            stream_id="unrelated:handoff-test",
            event_type="unrelated.event.v1",
            payload={"value": "independent"},
            expected_stream_head=store.stream_head_digest("unrelated:handoff-test"),
        )
        handoff = execute_selected_baseline_revalidation_handoff_v1(
            ledger=ledger,
            candidate=candidate,
            candidate_runtime_identity=runtime,
            candidate_repository_sha=runtime.code_sha,
        )
        assert ledger.current_selection() == handoff.persisted_selection
        assert handoff.persisted_selection.lineage.blocked_attempt_count == 1


def test_reopen_recovers_resulting_selected_lineage(tmp_path: Path) -> None:
    baseline, candidate, runtime, report = _changed_material()
    path = tmp_path / "handoff.db"
    with SQLiteProvenanceStore(path) as store:
        ledger = _ledger_with_baseline(store, baseline)
        handoff = execute_selected_baseline_revalidation_handoff_v1(
            ledger=ledger,
            candidate=candidate,
            candidate_runtime_identity=runtime,
            candidate_repository_sha=runtime.code_sha,
            replay_report=report,
            replay_repository_sha=runtime.code_sha,
        )
        expected = handoff.persisted_selection
    with SQLiteProvenanceStore(path) as reopened:
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(reopened)
        assert ledger.current_selection() == expected
        assert ledger.current_selection() is not None
        assert ledger.current_selection().current_repository_sha == runtime.code_sha
