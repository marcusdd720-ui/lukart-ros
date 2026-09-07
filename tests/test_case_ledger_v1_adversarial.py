from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from typing import cast

import pytest

from core.case_ledger import CaseLedgerContractError, ObjectId, ObjectRevision
from core.enterprise.contracts import EnterpriseContractError
from core.enterprise.durability import SQLiteProvenanceStore


def test_canonical_mapping_rejects_non_string_keys_instead_of_normalizing() -> None:
    unsafe = cast(Mapping[str, object], {1: "numeric", "1": "string"})

    with pytest.raises(CaseLedgerContractError, match="keys must be strings"):
        ObjectRevision.build(
            object_id=ObjectId("OBJ-KEY-COLLISION"),
            schema_version="object.v1",
            content=unsafe,
        )


def test_preexisting_durable_tamper_blocks_append_without_new_record(tmp_path) -> None:
    path = tmp_path / "tampered-before-append.db"
    with SQLiteProvenanceStore(path) as store:
        first = store.append(
            stream_id="case-stream",
            event_type="event.v1",
            payload={"value": 1},
        )

    raw = sqlite3.connect(path)
    try:
        raw.execute(
            "UPDATE provenance SET payload_json = ? WHERE sequence = 0",
            ('{"value":999}',),
        )
        raw.commit()
    finally:
        raw.close()

    with SQLiteProvenanceStore(path) as store:
        with pytest.raises(EnterpriseContractError, match="payload digest mismatch"):
            store.append(
                stream_id="case-stream",
                event_type="event.v1",
                payload={"value": 2},
                expected_stream_head=first.record_digest,
            )

    raw = sqlite3.connect(path)
    try:
        record_count = raw.execute("SELECT COUNT(*) FROM provenance").fetchone()
    finally:
        raw.close()

    assert record_count == (1,)
