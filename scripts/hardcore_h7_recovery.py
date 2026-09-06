from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from core.enterprise import EnterpriseContractError, SQLiteProvenanceStore
from core.p3.contracts import content_digest, require_hex_digest

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "enterprise_v1.json"


def _git_head() -> str:
    completed = subprocess.run(
        ("git", "-C", str(ROOT), "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _expect_failure(action: object, marker: str) -> dict[str, object]:
    if not callable(action):
        raise RuntimeError("H7 adversarial action must be callable")
    try:
        action()
    except EnterpriseContractError as exc:
        if marker not in str(exc):
            raise RuntimeError(f"unexpected H7 denial reason: {exc}") from exc
        return {"denied": True, "reason_class": marker}
    raise RuntimeError(f"H7 boundary unexpectedly accepted condition: {marker}")


def _seed(store: SQLiteProvenanceStore, count: int) -> None:
    store.append_batch(
        tuple(
            (
                "case-h7",
                "evidence",
                {"evidence_id": f"H7-EV-{index}", "value": index},
            )
            for index in range(count)
        )
    )


def build_h7_evidence(candidate_sha: str) -> dict[str, object]:
    candidate = require_hex_digest(candidate_sha, field_name="candidate_sha", lengths=(40,))
    head = require_hex_digest(_git_head(), field_name="head_sha", lengths=(40,))
    if candidate != head:
        raise RuntimeError(f"exact-SHA mismatch: checked-out HEAD {head} != candidate {candidate}")

    policy_document = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    h7 = policy_document.get("h7_recovery_rollback")
    if not isinstance(h7, dict):
        raise RuntimeError("H7 recovery policy is missing")
    required = {
        "recovery_identity_schema": "lukart.recovery-identity.v1",
        "atomic_batch_persistence": True,
        "staged_restore_before_replace": True,
        "provenance_identity_required": True,
        "semantic_identity_required": True,
        "corrupt_snapshot": "FAIL",
        "blast_radius_breach": "FAIL",
        "silent_partial_recovery": False,
    }
    for key, expected in required.items():
        if h7.get(key) != expected:
            raise RuntimeError(f"H7 policy mismatch for {key}: {h7.get(key)!r} != {expected!r}")
    max_records = h7.get("max_restore_records")
    if not isinstance(max_records, int) or max_records < 1:
        raise RuntimeError("H7 max_restore_records must be a positive integer")

    with tempfile.TemporaryDirectory(prefix="lukart-h7-") as directory:
        root = Path(directory)
        live_path = root / "live.db"
        snapshot_path = root / "checkpoint.db"
        corrupt_path = root / "corrupt.db"

        with SQLiteProvenanceStore(live_path) as live:
            _seed(live, 3)
            checkpoint = live.state_identity()
            live.backup_to(snapshot_path)
            live.append(
                stream_id="case-h7",
                event_type="promotion",
                payload={"candidate": "F-H7"},
            )
            newer = live.state_identity()
        if checkpoint == newer:
            raise RuntimeError("H7 rollback fixture did not create a newer state")

        restored = SQLiteProvenanceStore.restore_verified(
            snapshot_path,
            live_path,
            max_records=max_records,
        )
        try:
            rolled_back = restored.state_identity()
        finally:
            restored.close()
        if rolled_back != checkpoint:
            raise RuntimeError("H7 rollback did not restore exact semantic/provenance identity")

        with SQLiteProvenanceStore(live_path) as live:
            before_invalid_batch = live.state_identity()
            invalid_batch = _expect_failure(
                lambda: live.append_batch(
                    (
                        ("case-h7", "reasoning", {"decision": "ABSTAIN"}),
                        ("case-h7", "", {"invalid": True}),
                    )
                ),
                "stream_id and event_type",
            )
            if live.state_identity() != before_invalid_batch:
                raise RuntimeError("H7 invalid batch partially persisted")

        shutil.copyfile(snapshot_path, corrupt_path)
        connection = sqlite3.connect(corrupt_path)
        try:
            connection.execute(
                "UPDATE provenance SET payload_json = ? WHERE sequence = 0",
                ('{"evidence_id":"H7-TAMPER"}',),
            )
            connection.commit()
        finally:
            connection.close()
        with SQLiteProvenanceStore(live_path) as live:
            before_corrupt_restore = live.state_identity()
        corrupt_denial = _expect_failure(
            lambda: SQLiteProvenanceStore.restore_verified(
                corrupt_path,
                live_path,
                max_records=max_records,
            ),
            "payload digest mismatch",
        )
        with SQLiteProvenanceStore(live_path) as live:
            if live.state_identity() != before_corrupt_restore:
                raise RuntimeError("H7 corrupt restore changed destination state")

        limit_denial = _expect_failure(
            lambda: SQLiteProvenanceStore.restore_verified(
                snapshot_path,
                live_path,
                max_records=checkpoint.record_count - 1,
            ),
            "blast-radius",
        )

    evidence_body: dict[str, object] = {
        "schema": "lukart.hardcore.h7-recovery-rollback-evidence.v1",
        "candidate_sha": candidate,
        "checked_out_head_sha": head,
        "policy_digest": content_digest(h7),
        "checkpoint_identity": checkpoint.canonical_dict(),
        "checkpoint_identity_digest": checkpoint.digest(),
        "newer_identity_digest": newer.digest(),
        "restored_identity_digest": rolled_back.digest(),
        "rollback_exact": rolled_back == checkpoint,
        "recovery_blast_radius_records": checkpoint.record_count,
        "max_restore_records": max_records,
        "adversarial_denials": {
            "partial_batch": invalid_batch,
            "corrupt_snapshot": corrupt_denial,
            "blast_radius": limit_denial,
        },
        "state": "CONTROL_PASS",
    }
    evidence_body["evidence_digest"] = content_digest(evidence_body)
    return evidence_body


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate H7 recovery, rollback and failure containment"
    )
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--output", default="build/hardcore/h7-recovery-rollback.json")
    args = parser.parse_args()

    evidence = build_h7_evidence(args.candidate_sha)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("H7_RECOVERY_ROLLBACK=PASS")
    print(f"H7_CANDIDATE_SHA={evidence['candidate_sha']}")
    print(f"H7_EVIDENCE_DIGEST={evidence['evidence_digest']}")
    print(f"H7_EVIDENCE_PATH={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
