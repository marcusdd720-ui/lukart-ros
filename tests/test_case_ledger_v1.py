from __future__ import annotations

import json
from typing import cast

import pytest

from core.case_ledger import (
    CanonicalCaseLedger,
    CaseId,
    CaseLedgerContractError,
    ContentAddress,
    LedgerEvent,
    ObjectId,
    ObjectRevision,
)
from core.enterprise.contracts import EnterpriseContractError
from core.enterprise.durability import SQLiteProvenanceStore
from core.p3.contracts import RuntimeIdentity, canonical_json


def _runtime(*, provider: str = "provider-a@1") -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="a" * 40,
        schema_version="case.v1",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        provider_identities=(provider,),
        provider_inventory_declared=True,
    )


def _mutable(value: object) -> object:
    return json.loads(canonical_json(value))


def test_object_revision_identity_is_deterministic_and_content_addressed() -> None:
    object_id = ObjectId("OBJ-001")
    left = ObjectRevision.build(
        object_id=object_id,
        schema_version="object.v1",
        content={"b": 2, "a": [1, 2]},
    )
    right = ObjectRevision.build(
        object_id=object_id,
        schema_version="object.v1",
        content={"a": [1, 2], "b": 2},
    )
    changed = ObjectRevision.build(
        object_id=object_id,
        schema_version="object.v1",
        content={"a": [1, 3], "b": 2},
    )
    other_object = ObjectRevision.build(
        object_id=ObjectId("OBJ-002"),
        schema_version="object.v1",
        content={"a": [1, 2], "b": 2},
    )

    assert left.revision_id == right.revision_id
    assert changed.revision_id != left.revision_id
    assert other_object.revision_id != left.revision_id
    assert str(left.revision_id).startswith("sha256:")


def test_object_revision_content_is_deeply_immutable() -> None:
    revision = ObjectRevision.build(
        object_id=ObjectId("OBJ-IMMUTABLE"),
        schema_version="object.v1",
        content={"nested": {"items": [1, 2]}},
    )

    with pytest.raises(TypeError):
        cast(dict[str, object], revision.content)["new"] = "forbidden"
    nested = cast(dict[str, object], revision.content["nested"])
    with pytest.raises(TypeError):
        nested["new"] = "forbidden"
    assert isinstance(revision.content["nested"], dict) is False


def test_unknown_identity_schema_profile_and_algorithm_fail_closed() -> None:
    revision = ObjectRevision.build(
        object_id=ObjectId("OBJ-001"),
        schema_version="object.v1",
        content={"value": 1},
    )
    raw_revision = cast(dict[str, object], _mutable(revision.canonical_dict()))

    unknown_schema = dict(raw_revision)
    unknown_schema["schema"] = "lukart.object-revision.v999"
    with pytest.raises(CaseLedgerContractError, match="unsupported object revision schema"):
        ObjectRevision.from_dict(unknown_schema)

    unknown_profile = dict(raw_revision)
    unknown_profile["canonicalization_profile"] = "unknown-canonicalization"
    with pytest.raises(CaseLedgerContractError, match="unsupported canonicalization profile"):
        ObjectRevision.from_dict(unknown_profile)

    address = cast(dict[str, object], raw_revision["revision_id"])
    unknown_algorithm = dict(address)
    unknown_algorithm["algorithm"] = "future-hash"
    with pytest.raises(CaseLedgerContractError, match="unsupported digest algorithm"):
        ContentAddress.from_dict(unknown_algorithm)


def test_transactional_stream_compare_and_append_is_fail_closed(tmp_path) -> None:
    path = tmp_path / "provenance.db"
    with SQLiteProvenanceStore(path) as store:
        genesis = store.stream_head_digest("case-stream")
        first = store.append(
            stream_id="case-stream",
            event_type="event.v1",
            payload={"value": 1},
            expected_stream_head=genesis,
        )
        assert store.stream_head_digest("case-stream") == first.record_digest

        with pytest.raises(EnterpriseContractError, match="stream head mismatch"):
            store.append(
                stream_id="case-stream",
                event_type="event.v1",
                payload={"value": 2},
                expected_stream_head=genesis,
            )

        assert len(store.verify()) == 1


def test_canonical_ledger_publish_reopen_and_offline_verify(tmp_path) -> None:
    path = tmp_path / "canonical.db"
    case_id = CaseId("CASE-001")
    object_id = ObjectId("OBJ-001")
    first_revision = ObjectRevision.build(
        object_id=object_id,
        schema_version="object.v1",
        content={"status": "claim", "value": 1},
    )
    second_revision = ObjectRevision.build(
        object_id=object_id,
        schema_version="object.v1",
        content={"status": "claim", "value": 2},
    )

    with CanonicalCaseLedger(path) as ledger:
        first = ledger.publish_revision(
            case_id=case_id,
            revision=first_revision,
            runtime_identity=_runtime(),
            expected_head=None,
        )
        assert first.case_sequence == 0
        assert first.previous_event_id is None
        assert first.revision_id == first_revision.revision_id
        assert ledger.head(case_id) == first.event_id

        second = ledger.publish_revision(
            case_id=case_id,
            revision=second_revision,
            runtime_identity=_runtime(),
            expected_head=first.event_id,
        )
        assert second.case_sequence == 1
        assert second.previous_event_id == first.event_id
        assert ledger.head(case_id) == second.event_id

        bundle = ledger.export_case(case_id)
        assert bundle.head_event_id == second.event_id
        verified = CanonicalCaseLedger.verify_export(bundle.canonical_dict())
        assert verified == bundle

    with CanonicalCaseLedger(path) as reopened:
        events = reopened.events(case_id)
        assert tuple(event.event_id for event in events) == (first.event_id, second.event_id)
        assert reopened.export_case(case_id).bundle_digest == bundle.bundle_digest


def test_stale_canonical_head_rejects_without_writing(tmp_path) -> None:
    path = tmp_path / "stale.db"
    case_id = CaseId("CASE-STALE")
    revision = ObjectRevision.build(
        object_id=ObjectId("OBJ-STALE"),
        schema_version="object.v1",
        content={"value": 1},
    )

    with CanonicalCaseLedger(path) as ledger:
        first = ledger.publish_revision(
            case_id=case_id,
            revision=revision,
            runtime_identity=_runtime(),
            expected_head=None,
        )
        with pytest.raises(CaseLedgerContractError, match="canonical case head mismatch"):
            ledger.append_event(
                case_id=case_id,
                event_type="assertion.created.v1",
                runtime_identity=_runtime(),
                payload={"value": "stale"},
                expected_head=None,
            )
        events = ledger.events(case_id)
        assert len(events) == 1
        assert events[0].event_id == first.event_id


def test_case_streams_have_independent_canonical_sequences(tmp_path) -> None:
    path = tmp_path / "multi-case.db"
    case_a = CaseId("CASE-A")
    case_b = CaseId("CASE-B")

    with CanonicalCaseLedger(path) as ledger:
        a0 = ledger.append_event(
            case_id=case_a,
            event_type="evidence.ingested.v1",
            runtime_identity=_runtime(),
            payload={"evidence": "A0"},
            expected_head=None,
        )
        b0 = ledger.append_event(
            case_id=case_b,
            event_type="evidence.ingested.v1",
            runtime_identity=_runtime(),
            payload={"evidence": "B0"},
            expected_head=None,
        )
        a1 = ledger.append_event(
            case_id=case_a,
            event_type="evidence.ingested.v1",
            runtime_identity=_runtime(),
            payload={"evidence": "A1"},
            expected_head=a0.event_id,
        )

        assert a0.case_sequence == 0
        assert b0.case_sequence == 0
        assert a1.case_sequence == 1
        assert a1.previous_event_id == a0.event_id
        assert a1.previous_event_id != b0.event_id


def test_tampered_event_and_bundle_are_rejected_offline(tmp_path) -> None:
    path = tmp_path / "tamper.db"
    case_id = CaseId("CASE-TAMPER")

    with CanonicalCaseLedger(path) as ledger:
        event = ledger.append_event(
            case_id=case_id,
            event_type="evidence.ingested.v1",
            runtime_identity=_runtime(),
            payload={"value": 1},
            expected_head=None,
        )
        raw_event = cast(dict[str, object], _mutable(event.canonical_dict()))
        raw_event["payload"] = {"value": 999}
        with pytest.raises(CaseLedgerContractError, match="event content-address mismatch"):
            LedgerEvent.from_dict(raw_event)

        bundle = ledger.export_case(case_id)
        raw_bundle = cast(dict[str, object], _mutable(bundle.canonical_dict()))
        events = cast(list[object], raw_bundle["events"])
        first = cast(dict[str, object], events[0])
        first["payload"] = {"value": 999}
        with pytest.raises(CaseLedgerContractError):
            CanonicalCaseLedger.verify_export(raw_bundle)


def test_noncanonical_backend_record_in_reserved_stream_fails_closed(tmp_path) -> None:
    path = tmp_path / "rogue.db"
    case_id = CaseId("CASE-ROGUE")
    with SQLiteProvenanceStore(path) as store:
        store.append(
            stream_id="canonical-case-ledger:CASE-ROGUE",
            event_type="legacy.parallel-authority.v1",
            payload={"value": "rogue"},
        )

    with CanonicalCaseLedger(path) as ledger:
        with pytest.raises(CaseLedgerContractError, match="non-canonical record"):
            ledger.events(case_id)


def test_case_event_blast_radius_limit_is_explicit(tmp_path) -> None:
    path = tmp_path / "bounded.db"
    case_id = CaseId("CASE-BOUNDED")

    with CanonicalCaseLedger(path) as ledger:
        first = ledger.append_event(
            case_id=case_id,
            event_type="evidence.ingested.v1",
            runtime_identity=_runtime(),
            payload={"value": 1},
            expected_head=None,
            max_events=1,
        )
        with pytest.raises(CaseLedgerContractError, match="event limit exceeded"):
            ledger.append_event(
                case_id=case_id,
                event_type="evidence.ingested.v1",
                runtime_identity=_runtime(),
                payload={"value": 2},
                expected_head=first.event_id,
                max_events=1,
            )
        assert ledger.head(case_id, max_events=1) == first.event_id


def test_runtime_provider_identity_is_bound_without_provider_specific_logic(tmp_path) -> None:
    path = tmp_path / "providers.db"
    case_id = CaseId("CASE-PROVIDERS")

    with CanonicalCaseLedger(path) as ledger:
        first = ledger.append_event(
            case_id=case_id,
            event_type="reasoning.input.v1",
            runtime_identity=_runtime(provider="provider-a@1"),
            payload={"same": "payload"},
            expected_head=None,
        )
        second = ledger.append_event(
            case_id=case_id,
            event_type="reasoning.input.v1",
            runtime_identity=_runtime(provider="provider-b@7"),
            payload={"same": "payload"},
            expected_head=first.event_id,
        )

    assert first.runtime_identity_digest != second.runtime_identity_digest
    assert first.event_id != second.event_id
