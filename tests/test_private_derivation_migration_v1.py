from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.private_derivation_migration_v1 import (
    CompatibilityStatus,
    ConfigResolution,
    MigrationAction,
    build_derivation_migration_readiness,
    write_migration_readiness_report,
)
from core.private_evidence_derivation_v1 import (
    MAX_TEXT_INPUT_BYTES,
    derive_utf8_text,
    record_environment_bound_text_derivation,
)
from core.private_evidence_v1 import PrivateEvidenceError, PrivateEvidenceStore
from core.private_ocr_replay_v1 import OCR_CONFIG_V1, OCR_TRANSFORM_ID_V1
from core.enterprise.contracts import AuthorizationContext, Permission


class KeyProvider:
    def get_key(self, key_id: str, key_version: int) -> bytes:
        assert key_id == "case-key"
        assert key_version == 1
        return b"M" * 32


def _store(root: Path) -> PrivateEvidenceStore:
    return PrivateEvidenceStore(
        root,
        key_provider=KeyProvider(),
        authorization=AuthorizationContext(
            subject_id="synthetic-migration-worker",
            tenant_id="synthetic-tenant",
            roles=("case-worker",),
            permissions=(Permission.EVIDENCE_READ, Permission.EVIDENCE_WRITE),
            case_ids=("CASE-MIGRATION",),
        ),
        tenant_id="synthetic-tenant",
        case_id="CASE-MIGRATION",
        key_id="case-key",
    )


def _default_utf8_config() -> dict[str, object]:
    return {
        "encoding": "utf-8-strict",
        "newline": "LF",
        "bom": "reject",
        "nul": "reject",
        "max_input_bytes": MAX_TEXT_INPUT_BYTES,
    }


def test_inventory_resolves_current_utf8_and_ocr_profiles_without_mutation(tmp_path: Path) -> None:
    store = _store(tmp_path / "evidence")
    text_source = store.import_bytes(
        b"alpha\r\n",
        source_ref="document-slot:1",
        media_type="text/plain",
    )
    text_derivation = derive_utf8_text(store, text_source)
    image_source = store.import_bytes(
        b"synthetic-image",
        source_ref="document-slot:2",
        media_type="image/png",
    )
    ocr_derivation = record_environment_bound_text_derivation(
        store,
        image_source,
        "synthetic OCR\n",
        transform_id=OCR_TRANSFORM_ID_V1,
        transform_version=1,
        config=dict(OCR_CONFIG_V1),
        tool_identity="synthetic-tool-identity",
    )
    receipt_bytes_before = {
        text_derivation.derivation_receipt_digest: text_derivation.derivation_receipt_path.read_bytes(),
        ocr_derivation.derivation_receipt_digest: ocr_derivation.derivation_receipt_path.read_bytes(),
    }

    report = build_derivation_migration_readiness(store)

    assert report.overall_status == "READY"
    assert report.policy_id.startswith("sha256:")
    assert report.report_id.startswith("sha256:")
    by_receipt = {entry.derivation_receipt_digest: entry for entry in report.entries}
    text_entry = by_receipt[text_derivation.derivation_receipt_digest]
    assert text_entry.compatibility_status == CompatibilityStatus.CURRENT_DETERMINISTIC.value
    assert text_entry.config_resolution == ConfigResolution.KNOWN.value
    assert text_entry.migration_action == MigrationAction.NONE.value
    assert text_entry.resolved_config == _default_utf8_config()
    ocr_entry = by_receipt[ocr_derivation.derivation_receipt_digest]
    assert ocr_entry.compatibility_status == CompatibilityStatus.REPLAY_READY_ENVIRONMENT_BOUND.value
    assert ocr_entry.config_resolution == ConfigResolution.KNOWN.value
    assert ocr_entry.migration_action == MigrationAction.NONE.value
    assert ocr_entry.resolved_config == OCR_CONFIG_V1
    assert text_derivation.derivation_receipt_path.read_bytes() == receipt_bytes_before[
        text_derivation.derivation_receipt_digest
    ]
    assert ocr_derivation.derivation_receipt_path.read_bytes() == receipt_bytes_before[
        ocr_derivation.derivation_receipt_digest
    ]


def test_nondefault_utf8_config_requires_recovery_candidate(tmp_path: Path) -> None:
    store = _store(tmp_path / "evidence")
    source = store.import_bytes(
        b"alpha\n",
        source_ref="document-slot:1",
        media_type="text/plain",
    )
    derivation = derive_utf8_text(store, source, max_input_bytes=1024)

    report = build_derivation_migration_readiness(store)

    assert report.overall_status == "ACTION_REQUIRED"
    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.compatibility_status == CompatibilityStatus.CONFIG_RECOVERY_REQUIRED.value
    assert entry.config_resolution == ConfigResolution.UNRESOLVED.value
    assert entry.migration_action == MigrationAction.SUPPLY_VERIFIED_CONFIG.value
    assert entry.resolved_config is None


def test_verified_config_candidate_recovers_nondefault_utf8_profile(tmp_path: Path) -> None:
    store = _store(tmp_path / "evidence")
    source = store.import_bytes(
        b"alpha\n",
        source_ref="document-slot:1",
        media_type="text/plain",
    )
    derivation = derive_utf8_text(store, source, max_input_bytes=1024)
    candidate = {
        "encoding": "utf-8-strict",
        "newline": "LF",
        "bom": "reject",
        "nul": "reject",
        "max_input_bytes": 1024,
    }

    report = build_derivation_migration_readiness(
        store,
        config_candidates={derivation.derivation_receipt_digest: candidate},
    )

    assert report.overall_status == "READY"
    entry = report.entries[0]
    assert entry.config_resolution == ConfigResolution.RECOVERED_FROM_VERIFIED_CANDIDATE.value
    assert entry.compatibility_status == CompatibilityStatus.CURRENT_DETERMINISTIC.value
    assert entry.migration_action == MigrationAction.NONE.value
    assert entry.resolved_config == candidate


def test_wrong_or_unknown_config_candidate_fails_closed(tmp_path: Path) -> None:
    store = _store(tmp_path / "evidence")
    source = store.import_bytes(
        b"alpha\n",
        source_ref="document-slot:1",
        media_type="text/plain",
    )
    derivation = derive_utf8_text(store, source, max_input_bytes=1024)
    wrong = {
        "encoding": "utf-8-strict",
        "newline": "LF",
        "bom": "reject",
        "nul": "reject",
        "max_input_bytes": 2048,
    }

    with pytest.raises(PrivateEvidenceError, match="digest mismatch"):
        build_derivation_migration_readiness(
            store,
            config_candidates={derivation.derivation_receipt_digest: wrong},
        )

    with pytest.raises(PrivateEvidenceError, match="unknown derivation"):
        build_derivation_migration_readiness(
            store,
            config_candidates={"sha256:" + "0" * 64: wrong},
        )


def test_unknown_profile_is_explicit_migration_required(tmp_path: Path) -> None:
    store = _store(tmp_path / "evidence")
    source = store.import_bytes(
        b"synthetic-image",
        source_ref="document-slot:1",
        media_type="image/png",
    )
    derivation = record_environment_bound_text_derivation(
        store,
        source,
        "legacy output\n",
        transform_id="lukart.legacy-local-ocr",
        transform_version=1,
        config={"legacy": True},
        tool_identity="legacy-tool",
    )

    report = build_derivation_migration_readiness(store)

    assert report.overall_status == "ACTION_REQUIRED"
    entry = report.entries[0]
    assert entry.derivation_receipt_digest == derivation.derivation_receipt_digest
    assert entry.compatibility_status == CompatibilityStatus.EXPLICIT_MIGRATION_REQUIRED.value
    assert entry.config_resolution == ConfigResolution.UNRESOLVED.value
    assert entry.migration_action == MigrationAction.DEFINE_VERSIONED_MIGRATION.value
    assert entry.resolved_config is None


def test_report_is_digest_bound_private_immutable_and_contains_no_evidence_text(tmp_path: Path) -> None:
    store = _store(tmp_path / "evidence")
    source = store.import_bytes(
        b"private synthetic evidence text\n",
        source_ref="document-slot:1",
        media_type="text/plain",
    )
    derive_utf8_text(store, source)
    report = build_derivation_migration_readiness(store)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    with pytest.raises(PrivateEvidenceError, match="outside the public repository"):
        write_migration_readiness_report(report, repo_root / "report.json", repo_root=repo_root)

    target = tmp_path / "private" / "migration-report.json"
    assert write_migration_readiness_report(report, target, repo_root=repo_root) == target
    assert write_migration_readiness_report(report, target, repo_root=repo_root) == target
    payload = target.read_bytes()
    assert b"private synthetic evidence text" not in payload
    assert b"document-slot:1" not in payload

    changed = replace(report, overall_status="DIFFERENT")
    with pytest.raises(PrivateEvidenceError, match="divergence"):
        write_migration_readiness_report(changed, target, repo_root=repo_root)
