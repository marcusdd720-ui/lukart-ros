from __future__ import annotations

import copy
from pathlib import Path

import pytest

from core.enterprise.contracts import EnterpriseContractError
from core.enterprise.durability import SQLiteProvenanceStore
from core.replay_revalidation_baseline_lineage_v1 import (
    ReplayRevalidationBaselineLineageV1,
)
from core.replay_revalidation_baseline_selection_v1 import (
    REVALIDATION_BASELINE_SELECTION_EVENT_TYPE_V1,
    REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1,
    ReplayRevalidationBaselineSelectionError,
    ReplayRevalidationBaselineSelectionLedgerV1,
    ReplayRevalidationBaselineSelectionV1,
    verify_revalidation_baseline_selection_v1,
)
from tests.test_replay_revalidation_baseline_lineage_v1 import (
    _blocked_and_advanced_entries,
    _unchanged_entry,
)
from tests.test_replay_revalidation_baseline_transition_v1 import _baseline, h


def _empty_lineage() -> ReplayRevalidationBaselineLineageV1:
    baseline, _ = _baseline()
    return ReplayRevalidationBaselineLineageV1.build(genesis_baseline=baseline)


def _lineages() -> tuple[
    ReplayRevalidationBaselineLineageV1,
    ReplayRevalidationBaselineLineageV1,
    ReplayRevalidationBaselineLineageV1,
]:
    baseline, blocked, advanced = _blocked_and_advanced_entries()
    genesis = ReplayRevalidationBaselineLineageV1.build(genesis_baseline=baseline)
    blocked_lineage = genesis.append(blocked)
    advanced_lineage = blocked_lineage.append(advanced)
    return genesis, blocked_lineage, advanced_lineage


def _store(path: Path) -> SQLiteProvenanceStore:
    return SQLiteProvenanceStore(path)


def test_first_selection_persists_and_round_trips(tmp_path: Path) -> None:
    lineage = _empty_lineage()
    with _store(tmp_path / "selection.db") as store:
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
        selection = ledger.append(lineage)
        assert selection.lineage == lineage
        assert ledger.current_selection() == selection
        assert ledger.selections() == (selection,)
        assert verify_revalidation_baseline_selection_v1(selection) == selection.selection_digest
        assert len(store.verify()) == 1


def test_reopen_recovers_same_current_selection(tmp_path: Path) -> None:
    path = tmp_path / "selection.db"
    _, blocked_lineage, _ = _lineages()
    with _store(path) as store:
        expected = ReplayRevalidationBaselineSelectionLedgerV1(store).append(blocked_lineage)
    with _store(path) as reopened:
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(reopened)
        assert ledger.current_selection() == expected
        assert ledger.selections() == (expected,)


def test_strict_blocked_only_extension_updates_selection_without_baseline_change(
    tmp_path: Path,
) -> None:
    genesis, blocked_lineage, _ = _lineages()
    with _store(tmp_path / "selection.db") as store:
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
        first = ledger.append(genesis)
        second = ledger.append(blocked_lineage)
        assert second.previous_selection_digest == first.selection_digest
        assert second.lineage_digest != first.lineage_digest
        assert second.current_baseline_digest == first.current_baseline_digest
        assert second.current_repository_sha == first.current_repository_sha
        assert ledger.current_selection() == second


def test_successful_extension_advances_current_baseline(tmp_path: Path) -> None:
    _, blocked_lineage, advanced_lineage = _lineages()
    with _store(tmp_path / "selection.db") as store:
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
        previous = ledger.append(blocked_lineage)
        selected = ledger.append(advanced_lineage)
        assert selected.previous_selection_digest == previous.selection_digest
        assert selected.current_baseline_digest == advanced_lineage.current_baseline_digest
        assert selected.current_repository_sha == advanced_lineage.current_repository_sha
        assert selected.current_baseline_digest != previous.current_baseline_digest


def test_duplicate_noop_selection_fails_closed(tmp_path: Path) -> None:
    lineage = _empty_lineage()
    with _store(tmp_path / "selection.db") as store:
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
        ledger.append(lineage)
        with pytest.raises(ReplayRevalidationBaselineSelectionError, match="no-op"):
            ledger.append(lineage)
        assert len(ledger.selections()) == 1


def test_rollback_to_shorter_lineage_fails_closed(tmp_path: Path) -> None:
    genesis, blocked_lineage, _ = _lineages()
    with _store(tmp_path / "selection.db") as store:
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
        ledger.append(blocked_lineage)
        with pytest.raises(ReplayRevalidationBaselineSelectionError, match="rollback"):
            ledger.append(genesis)
        assert len(ledger.selections()) == 1


def test_alternative_nonprefix_extension_fails_as_fork(tmp_path: Path) -> None:
    baseline, blocked, advanced = _blocked_and_advanced_entries()
    assert advanced.resulting_baseline is not None
    prior = ReplayRevalidationBaselineLineageV1.build(
        genesis_baseline=baseline,
        entries=(blocked,),
    )
    alternate = ReplayRevalidationBaselineLineageV1.build(
        genesis_baseline=baseline,
        entries=(advanced, _unchanged_entry(advanced.resulting_baseline)),
    )
    with _store(tmp_path / "selection.db") as store:
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
        ledger.append(prior)
        with pytest.raises(ReplayRevalidationBaselineSelectionError, match="fork|reorder"):
            ledger.append(alternate)


def test_previous_selection_digest_tamper_is_semantically_rejected(tmp_path: Path) -> None:
    lineage = _empty_lineage()
    forged = ReplayRevalidationBaselineSelectionV1(
        lineage=lineage,
        previous_selection_digest=h("wrong-selection-parent"),
    )
    with _store(tmp_path / "selection.db") as store:
        store.append(
            stream_id=REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1,
            event_type=REVALIDATION_BASELINE_SELECTION_EVENT_TYPE_V1,
            payload=forged.canonical_dict(),
            expected_stream_head=store.stream_head_digest(
                REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1
            ),
        )
        assert len(store.verify()) == 1
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
        with pytest.raises(
            ReplayRevalidationBaselineSelectionError,
            match="previous selection digest mismatch",
        ):
            ledger.selections()


def test_summary_and_selection_digest_tamper_fail_closed(tmp_path: Path) -> None:
    lineage = _empty_lineage()
    selection = ReplayRevalidationBaselineSelectionV1(lineage=lineage)
    tampered_values: tuple[tuple[str, object], ...] = (
        ("lineage_digest", h("wrong-lineage")),
        ("current_baseline_digest", h("wrong-baseline")),
        ("current_repository_sha", "f" * 40),
        ("selection_digest", h("wrong-selection")),
    )
    for index, (field, value) in enumerate(tampered_values):
        payload = copy.deepcopy(selection.canonical_dict())
        payload[field] = value
        with _store(tmp_path / f"tamper-{index}.db") as store:
            store.append(
                stream_id=REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1,
                event_type=REVALIDATION_BASELINE_SELECTION_EVENT_TYPE_V1,
                payload=payload,
                expected_stream_head=store.stream_head_digest(
                    REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1
                ),
            )
            assert len(store.verify()) == 1
            ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
            with pytest.raises(ReplayRevalidationBaselineSelectionError):
                ledger.selections()


def test_unknown_event_type_in_selection_stream_fails_closed(tmp_path: Path) -> None:
    with _store(tmp_path / "selection.db") as store:
        store.append(
            stream_id=REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1,
            event_type="lrd.revalidation-baseline-selection.unknown",
            payload={"unexpected": "event"},
            expected_stream_head=store.stream_head_digest(
                REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1
            ),
        )
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
        with pytest.raises(ReplayRevalidationBaselineSelectionError, match="unknown event type"):
            ledger.selections()


def test_unrelated_stream_does_not_change_selection_semantics(tmp_path: Path) -> None:
    lineage = _empty_lineage()
    with _store(tmp_path / "selection.db") as store:
        ledger = ReplayRevalidationBaselineSelectionLedgerV1(store)
        selection = ledger.append(lineage)
        store.append(
            stream_id="unrelated:test-stream",
            event_type="unrelated.event.v1",
            payload={"value": "independent"},
            expected_stream_head=store.stream_head_digest("unrelated:test-stream"),
        )
        assert len(store.verify()) == 2
        assert ledger.selections() == (selection,)
        assert ledger.current_selection() == selection


def test_authority_and_unknown_field_injection_fail_closed(tmp_path: Path) -> None:
    selection = ReplayRevalidationBaselineSelectionV1(lineage=_empty_lineage())
    authorities = (
        "mutable_pointer_authority",
        "scheduler_authority",
        "release_authority",
        "product_write_authority",
        "ccl_write_authority",
        "storage_authority",
        "provider_authority",
    )
    payloads: list[dict[str, object]] = []
    for authority in authorities:
        payload = copy.deepcopy(selection.canonical_dict())
        payload[authority] = True
        payloads.append(payload)
    persistence = copy.deepcopy(selection.canonical_dict())
    persistence["selection_persistence_authority"] = False
    payloads.append(persistence)
    unknown = copy.deepcopy(selection.canonical_dict())
    unknown["latest_selection_pointer"] = selection.selection_digest
    payloads.append(unknown)

    for index, payload in enumerate(payloads):
        with _store(tmp_path / f"authority-{index}.db") as store:
            store.append(
                stream_id=REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1,
                event_type=REVALIDATION_BASELINE_SELECTION_EVENT_TYPE_V1,
                payload=payload,
                expected_stream_head=store.stream_head_digest(
                    REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1
                ),
            )
            with pytest.raises(ReplayRevalidationBaselineSelectionError):
                ReplayRevalidationBaselineSelectionLedgerV1(store).selections()


def test_semantic_tamper_can_pass_store_hash_chain_but_not_selection_verifier(
    tmp_path: Path,
) -> None:
    selection = ReplayRevalidationBaselineSelectionV1(lineage=_empty_lineage())
    payload = copy.deepcopy(selection.canonical_dict())
    payload["current_baseline_digest"] = h("semantically-wrong-baseline")
    with _store(tmp_path / "selection.db") as store:
        store.append(
            stream_id=REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1,
            event_type=REVALIDATION_BASELINE_SELECTION_EVENT_TYPE_V1,
            payload=payload,
            expected_stream_head=store.stream_head_digest(
                REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1
            ),
        )
        assert len(store.verify()) == 1
        with pytest.raises(ReplayRevalidationBaselineSelectionError):
            ReplayRevalidationBaselineSelectionLedgerV1(store).selections()


def test_stream_head_compare_and_append_rejects_genesis_stale_race(
    tmp_path: Path,
) -> None:
    path = tmp_path / "selection.db"
    lineage = _empty_lineage()
    selection = ReplayRevalidationBaselineSelectionV1(lineage=lineage)
    first = _store(path)
    second = _store(path)
    try:
        stale_genesis = first.stream_head_digest(
            REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1
        )
        second.append(
            stream_id=REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1,
            event_type=REVALIDATION_BASELINE_SELECTION_EVENT_TYPE_V1,
            payload=selection.canonical_dict(),
            expected_stream_head=stale_genesis,
        )
        with pytest.raises(EnterpriseContractError, match="stream head mismatch"):
            first.append(
                stream_id=REVALIDATION_BASELINE_SELECTION_STREAM_ID_V1,
                event_type=REVALIDATION_BASELINE_SELECTION_EVENT_TYPE_V1,
                payload=selection.canonical_dict(),
                expected_stream_head=stale_genesis,
            )
    finally:
        first.close()
        second.close()
