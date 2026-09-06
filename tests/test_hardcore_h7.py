from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from core.enterprise import EnterpriseContractError, RecoveryIdentity, SQLiteProvenanceStore


def _seed(store: SQLiteProvenanceStore, count: int = 3) -> None:
    store.append_batch(
        tuple(
            (
                "case-a",
                "evidence",
                {"evidence_id": f"EV-{index}", "value": index},
            )
            for index in range(count)
        )
    )


def test_h7_recovery_identity_survives_reopen_exactly(tmp_path: Path) -> None:
    path = tmp_path / "ledger.db"
    with SQLiteProvenanceStore(path) as store:
        _seed(store)
        before = store.state_identity()
    with SQLiteProvenanceStore(path) as reopened:
        after = reopened.state_identity()
    assert isinstance(after, RecoveryIdentity)
    assert after == before
    assert len(after.digest()) == 64


def test_h7_invalid_batch_cannot_partially_persist(tmp_path: Path) -> None:
    path = tmp_path / "ledger.db"
    with SQLiteProvenanceStore(path) as store:
        _seed(store, count=1)
        before = store.state_identity()
        with pytest.raises(EnterpriseContractError, match="stream_id and event_type"):
            store.append_batch(
                (
                    ("case-a", "reasoning", {"decision": "ABSTAIN"}),
                    ("case-a", "", {"invalid": True}),
                )
            )
        assert store.state_identity() == before


def test_h7_backup_restore_preserves_semantic_and_provenance_identity(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    snapshot = tmp_path / "snapshot.db"
    restored_path = tmp_path / "restored.db"
    with SQLiteProvenanceStore(source) as store:
        _seed(store)
        expected = store.state_identity()
        assert store.backup_to(snapshot) == expected.head_digest

    restored = SQLiteProvenanceStore.restore_verified(
        snapshot,
        restored_path,
        max_records=10,
    )
    try:
        assert restored.state_identity() == expected
    finally:
        restored.close()


def test_h7_verified_snapshot_can_rollback_newer_state(tmp_path: Path) -> None:
    live = tmp_path / "live.db"
    snapshot = tmp_path / "checkpoint.db"
    with SQLiteProvenanceStore(live) as store:
        _seed(store, count=2)
        checkpoint = store.state_identity()
        store.backup_to(snapshot)
        store.append(
            stream_id="case-a",
            event_type="promotion",
            payload={"candidate": "F-1"},
        )
        newer = store.state_identity()
    assert newer != checkpoint

    rolled_back = SQLiteProvenanceStore.restore_verified(snapshot, live, max_records=10)
    try:
        assert rolled_back.state_identity() == checkpoint
        assert rolled_back.state_identity() != newer
    finally:
        rolled_back.close()


def test_h7_corrupt_snapshot_fails_before_destination_replacement(tmp_path: Path) -> None:
    live = tmp_path / "live.db"
    snapshot = tmp_path / "checkpoint.db"
    corrupt = tmp_path / "corrupt.db"
    with SQLiteProvenanceStore(live) as store:
        _seed(store, count=2)
        live_identity = store.state_identity()
        store.backup_to(snapshot)
    shutil.copyfile(snapshot, corrupt)

    connection = sqlite3.connect(corrupt)
    try:
        connection.execute(
            "UPDATE provenance SET payload_json = ? WHERE sequence = 0",
            ('{"evidence_id":"EV-TAMPERED"}',),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(EnterpriseContractError, match="payload digest mismatch"):
        SQLiteProvenanceStore.restore_verified(corrupt, live, max_records=10)
    with SQLiteProvenanceStore(live) as unchanged:
        assert unchanged.state_identity() == live_identity


def test_h7_restore_blast_radius_limit_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    snapshot = tmp_path / "snapshot.db"
    destination = tmp_path / "destination.db"
    with SQLiteProvenanceStore(source) as store:
        _seed(store, count=4)
        store.backup_to(snapshot)
    with SQLiteProvenanceStore(destination) as store:
        _seed(store, count=1)
        destination_identity = store.state_identity()

    with pytest.raises(EnterpriseContractError, match="blast-radius"):
        SQLiteProvenanceStore.restore_verified(snapshot, destination, max_records=3)
    with SQLiteProvenanceStore(destination) as unchanged:
        assert unchanged.state_identity() == destination_identity
