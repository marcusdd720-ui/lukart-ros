"""Synthetic fail-closed provenance/hash/tamper regressions for Canonical Case Ledger."""

import json

import pytest

from core.case_ledger.contracts import CaseId, CaseLedgerContractError
from core.case_ledger.ledger import CanonicalCaseLedger
from core.p3.contracts import RuntimeIdentity, canonical_json


def _runtime() -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="1" * 40,
        schema_version="synthetic-case-test-v1",
        config_digest="2" * 64,
        corpus_digest="3" * 64,
    )


def _portable_dict(value: object) -> dict[str, object]:
    decoded = json.loads(canonical_json(value))
    assert isinstance(decoded, dict)
    return decoded


def test_export_roundtrip_verifies_and_preserves_content_identity(tmp_path) -> None:
    case_id = CaseId("synthetic-case-integrity")

    with CanonicalCaseLedger(tmp_path / "ledger.db") as ledger:
        ledger.append_event(
            case_id=case_id,
            event_type="synthetic.integrity.event.v1",
            runtime_identity=_runtime(),
            payload={"marker": "ORIGINAL"},
            expected_head=None,
        )
        bundle = ledger.export_case(case_id)

    verified = CanonicalCaseLedger.verify_export(_portable_dict(bundle.canonical_dict()))

    assert verified == bundle


def test_payload_tamper_is_rejected_fail_closed(tmp_path) -> None:
    case_id = CaseId("synthetic-case-tamper")

    with CanonicalCaseLedger(tmp_path / "ledger.db") as ledger:
        ledger.append_event(
            case_id=case_id,
            event_type="synthetic.integrity.event.v1",
            runtime_identity=_runtime(),
            payload={"marker": "ORIGINAL"},
            expected_head=None,
        )
        serialized = _portable_dict(ledger.export_case(case_id).canonical_dict())

    events = serialized["events"]
    assert isinstance(events, list)
    first = events[0]
    assert isinstance(first, dict)
    payload = first["payload"]
    assert isinstance(payload, dict)
    payload["marker"] = "TAMPERED"

    with pytest.raises(CaseLedgerContractError):
        CanonicalCaseLedger.verify_export(serialized)


def test_restore_refuses_to_merge_into_nonempty_case_stream(tmp_path) -> None:
    case_id = CaseId("synthetic-case-restore")

    with CanonicalCaseLedger(tmp_path / "source.db") as source:
        source.append_event(
            case_id=case_id,
            event_type="synthetic.integrity.event.v1",
            runtime_identity=_runtime(),
            payload={"marker": "SOURCE"},
            expected_head=None,
        )
        bundle = _portable_dict(source.export_case(case_id).canonical_dict())

    with CanonicalCaseLedger(tmp_path / "target.db") as target:
        target.append_event(
            case_id=case_id,
            event_type="synthetic.preexisting.event.v1",
            runtime_identity=_runtime(),
            payload={"marker": "PREEXISTING"},
            expected_head=None,
        )
        with pytest.raises(
            CaseLedgerContractError,
            match="restore target case stream is not empty",
        ):
            target.restore_case(case_id, bundle)
