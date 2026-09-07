from __future__ import annotations

import json
import sqlite3
from typing import cast

import pytest

from core.case_ledger import CanonicalCaseLedger, CaseId, CaseLedgerContractError
from core.p3.contracts import RuntimeIdentity, canonical_json


def _runtime() -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="a" * 40,
        schema_version="case.v1",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        provider_identities=("provider-a@1",),
        provider_inventory_declared=True,
    )


def _mutable(value: object) -> dict[str, object]:
    decoded = json.loads(canonical_json(value))
    assert isinstance(decoded, dict)
    return cast(dict[str, object], decoded)


def _two_event_bundle(tmp_path):
    source_path = tmp_path / "source.db"
    case_id = CaseId("CASE-DR01")
    with CanonicalCaseLedger(source_path) as source:
        first = source.append_event(
            case_id=case_id,
            event_type="evidence.ingested.v1",
            runtime_identity=_runtime(),
            payload={"evidence": "A"},
            expected_head=None,
        )
        source.append_event(
            case_id=case_id,
            event_type="reasoning.input.v1",
            runtime_identity=_runtime(),
            payload={"input": "B"},
            expected_head=first.event_id,
        )
        return case_id, source.export_case(case_id)


def test_dr01_portable_restore_preserves_canonical_identity_across_backend_position(tmp_path) -> None:
    case_id, bundle = _two_event_bundle(tmp_path)
    target_path = tmp_path / "target.db"

    with CanonicalCaseLedger(target_path) as target:
        other_case = CaseId("CASE-OTHER")
        target.append_event(
            case_id=other_case,
            event_type="evidence.ingested.v1",
            runtime_identity=_runtime(),
            payload={"other": True},
            expected_head=None,
        )

        restored = target.restore_case(case_id, bundle.canonical_dict())

        assert restored == bundle
        assert restored.bundle_digest == bundle.bundle_digest
        assert restored.head_event_id == bundle.head_event_id
        assert tuple(event.event_id for event in restored.events) == tuple(
            event.event_id for event in bundle.events
        )
        assert target.export_case(case_id) == bundle
        assert len(target.events(other_case)) == 1


def test_dr01_offline_verifier_rejects_unbound_bundle_metadata(tmp_path) -> None:
    _case_id, bundle = _two_event_bundle(tmp_path)

    wrong_count = _mutable(bundle.canonical_dict())
    wrong_count["event_count"] = 999
    with pytest.raises(CaseLedgerContractError, match="unbound or inconsistent fields"):
        CanonicalCaseLedger.verify_export(wrong_count)

    wrong_head = _mutable(bundle.canonical_dict())
    wrong_head["head_event_id"] = None
    with pytest.raises(CaseLedgerContractError, match="unbound or inconsistent fields"):
        CanonicalCaseLedger.verify_export(wrong_head)

    extra_field = _mutable(bundle.canonical_dict())
    extra_field["parallel_truth"] = "forbidden"
    with pytest.raises(CaseLedgerContractError, match="unbound or inconsistent fields"):
        CanonicalCaseLedger.verify_export(extra_field)


def test_dr01_tampered_bundle_is_rejected_before_target_write(tmp_path) -> None:
    case_id, bundle = _two_event_bundle(tmp_path)
    tampered = _mutable(bundle.canonical_dict())
    events = cast(list[object], tampered["events"])
    first = cast(dict[str, object], events[0])
    first["payload"] = {"evidence": "tampered"}

    target_path = tmp_path / "tampered-target.db"
    with CanonicalCaseLedger(target_path) as target:
        with pytest.raises(CaseLedgerContractError):
            target.restore_case(case_id, tampered)
        assert target.events(case_id) == ()


def test_dr01_restore_rejects_wrong_case_and_nonempty_target_without_mutation(tmp_path) -> None:
    case_id, bundle = _two_event_bundle(tmp_path)
    target_path = tmp_path / "conflict-target.db"

    with CanonicalCaseLedger(target_path) as target:
        wrong_case = CaseId("CASE-WRONG")
        with pytest.raises(CaseLedgerContractError, match="does not match target case_id"):
            target.restore_case(wrong_case, bundle.canonical_dict())
        assert target.events(wrong_case) == ()
        assert target.events(case_id) == ()

        existing = target.append_event(
            case_id=case_id,
            event_type="evidence.ingested.v1",
            runtime_identity=_runtime(),
            payload={"existing": True},
            expected_head=None,
        )
        with pytest.raises(CaseLedgerContractError, match="target case stream is not empty"):
            target.restore_case(case_id, bundle.canonical_dict())
        assert target.head(case_id) == existing.event_id
        assert len(target.events(case_id)) == 1


def test_dr01_mid_batch_failure_rolls_back_entire_case_restore(tmp_path) -> None:
    case_id, bundle = _two_event_bundle(tmp_path)
    target_path = tmp_path / "rollback-target.db"

    with CanonicalCaseLedger(target_path) as target:
        raw = sqlite3.connect(target_path)
        try:
            raw.execute(
                """
                CREATE TRIGGER dr01_fail_second
                BEFORE INSERT ON provenance
                WHEN NEW.payload_json LIKE '%\"case_sequence\":1%'
                BEGIN
                    SELECT RAISE(ABORT, 'dr01 injected failure');
                END
                """
            )
            raw.commit()
        finally:
            raw.close()

        with pytest.raises(CaseLedgerContractError, match="restore transaction failed"):
            target.restore_case(case_id, bundle.canonical_dict())

        assert target.events(case_id) == ()
        check = sqlite3.connect(target_path)
        try:
            count = check.execute("SELECT COUNT(*) FROM provenance").fetchone()
        finally:
            check.close()
        assert count == (0,)


def test_dr01_restore_enforces_bounded_case_size_before_write(tmp_path) -> None:
    case_id, bundle = _two_event_bundle(tmp_path)
    target_path = tmp_path / "bounded-target.db"

    with CanonicalCaseLedger(target_path) as target:
        with pytest.raises(CaseLedgerContractError, match="event limit exceeded"):
            target.restore_case(case_id, bundle.canonical_dict(), max_events=1)
        assert target.events(case_id) == ()


def test_dr01_empty_bundle_restore_is_verified_noop(tmp_path) -> None:
    case_id = CaseId("CASE-EMPTY-DR01")
    source_path = tmp_path / "empty-source.db"
    target_path = tmp_path / "empty-target.db"

    with CanonicalCaseLedger(source_path) as source:
        bundle = source.export_case(case_id)

    with CanonicalCaseLedger(target_path) as target:
        restored = target.restore_case(case_id, bundle.canonical_dict())
        assert restored == bundle
        assert target.events(case_id) == ()
