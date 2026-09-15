"""Synthetic regression coverage for Canonical Case Ledger case isolation."""

import pytest

from core.case_ledger.contracts import CaseId, CaseLedgerContractError
from core.case_ledger.ledger import CanonicalCaseLedger
from core.p3.contracts import RuntimeIdentity


def _runtime() -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="1" * 40,
        schema_version="synthetic-case-test-v1",
        config_digest="2" * 64,
        corpus_digest="3" * 64,
    )


def test_independent_case_streams_never_cross_contaminate(tmp_path) -> None:
    case_a = CaseId("synthetic-case-a")
    case_b = CaseId("synthetic-case-b")

    with CanonicalCaseLedger(tmp_path / "ledger.db") as ledger:
        event_a = ledger.append_event(
            case_id=case_a,
            event_type="synthetic.case-a.event.v1",
            runtime_identity=_runtime(),
            payload={"marker": "A-ONLY"},
            expected_head=None,
        )
        event_b = ledger.append_event(
            case_id=case_b,
            event_type="synthetic.case-b.event.v1",
            runtime_identity=_runtime(),
            payload={"marker": "B-ONLY"},
            expected_head=None,
        )

        events_a = ledger.events(case_a)
        events_b = ledger.events(case_b)
        export_a = ledger.export_case(case_a)

    assert events_a == (event_a,)
    assert events_b == (event_b,)
    assert event_b not in events_a
    assert all(event.case_id == case_a for event in export_a.events)
    assert all(event.payload.get("marker") != "B-ONLY" for event in export_a.events)


def test_restore_rejects_bundle_for_a_different_case(tmp_path) -> None:
    case_a = CaseId("synthetic-case-a")
    case_b = CaseId("synthetic-case-b")

    with CanonicalCaseLedger(tmp_path / "source.db") as source:
        source.append_event(
            case_id=case_a,
            event_type="synthetic.case-a.event.v1",
            runtime_identity=_runtime(),
            payload={"marker": "A-ONLY"},
            expected_head=None,
        )
        bundle = source.export_case(case_a).canonical_dict()

    with CanonicalCaseLedger(tmp_path / "target.db") as target:
        with pytest.raises(
            CaseLedgerContractError,
            match="restore bundle case_id does not match target case_id",
        ):
            target.restore_case(case_b, bundle)
