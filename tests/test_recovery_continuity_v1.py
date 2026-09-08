from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from core.case_ledger.contracts import CaseId, CaseLedgerBundle, ContentAddress, LedgerEvent
from core.case_ledger.ledger import CanonicalCaseLedger
from core.enterprise.durability import SQLiteProvenanceStore
from core.enterprise.recovery_continuity_v1 import (
    RecoveryConformanceState,
    RecoveryContinuityV1Error,
    RecoveryDrillManifestV1,
    StorageProfileV1,
    evaluate_recovery_conformance,
    run_sqlite_case_recovery_drill,
)


def _profile(*, config: str = "default", backend: str = "sqlite-provenance") -> StorageProfileV1:
    return StorageProfileV1.from_configuration(
        backend_kind=backend,
        implementation_id="core.enterprise.durability.SQLiteProvenanceStore",
        implementation_version="v1",
        storage_schema="provenance-v1",
        public_configuration={"profile": config, "journal_mode": "WAL", "synchronous": "FULL"},
    )


def _bundle(*, payload_value: str = "alpha") -> CaseLedgerBundle:
    case_id = CaseId("CASE-DR-02")
    event = LedgerEvent.build(
        case_id=case_id,
        case_sequence=0,
        event_type="recovery.seed.v1",
        runtime_identity_digest=ContentAddress.for_value({"runtime": "dr-02-test"}),
        payload={"value": payload_value},
        previous_event_id=None,
    )
    return CaseLedgerBundle.build(case_id=case_id, events=(event,))


def _seed(path: Path, bundle: CaseLedgerBundle) -> None:
    with CanonicalCaseLedger(path) as ledger:
        restored = ledger.restore_case(bundle.case_id, bundle.canonical_dict())
        assert restored == bundle


def test_storage_profile_roundtrip_is_content_addressed_and_strict() -> None:
    profile = _profile()
    assert StorageProfileV1.from_dict(profile.canonical_dict()) == profile

    tampered = deepcopy(profile.canonical_dict())
    tampered["implementation_version"] = "v2"
    with pytest.raises(RecoveryContinuityV1Error, match="digest mismatch"):
        StorageProfileV1.from_dict(tampered)

    unknown = deepcopy(profile.canonical_dict())
    unknown["secret"] = "must-not-be-accepted"
    with pytest.raises(RecoveryContinuityV1Error, match="unknown=secret"):
        StorageProfileV1.from_dict(unknown)


def test_recovery_drill_preserves_exact_product_bundle_and_head(tmp_path: Path) -> None:
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    bundle = _bundle()
    _seed(source_path, bundle)

    source_profile = _profile(config="source")
    target_profile = _profile(config="target")
    manifest, report = run_sqlite_case_recovery_drill(
        source_path=source_path,
        target_path=target_path,
        case_id=bundle.case_id,
        source_profile=source_profile,
        target_profile=target_profile,
    )

    assert manifest.source_profile_digest == source_profile.profile_digest
    assert manifest.target_profile_digest == target_profile.profile_digest
    assert manifest.source_bundle_digest == bundle.bundle_digest.digest
    assert bundle.head_event_id is not None
    assert manifest.source_head_event_digest == bundle.head_event_id.digest
    assert report.state is RecoveryConformanceState.PASS
    assert report.violations == ()
    assert report.restored_bundle_digest == bundle.bundle_digest.digest
    assert report.restored_head_event_digest == bundle.head_event_id.digest

    with CanonicalCaseLedger(target_path) as target:
        assert target.export_case(bundle.case_id) == bundle

    assert RecoveryDrillManifestV1.from_dict(manifest.canonical_dict()) == manifest
    assert report.__class__.from_dict(report.canonical_dict()) == report


def test_recovery_drill_refuses_nonempty_target_without_overwrite(tmp_path: Path) -> None:
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    source_bundle = _bundle(payload_value="source")
    target_bundle = _bundle(payload_value="preexisting")
    _seed(source_path, source_bundle)
    _seed(target_path, target_bundle)

    with pytest.raises(RecoveryContinuityV1Error, match="restore refused"):
        run_sqlite_case_recovery_drill(
            source_path=source_path,
            target_path=target_path,
            case_id=source_bundle.case_id,
            source_profile=_profile(config="source"),
            target_profile=_profile(config="target"),
        )

    with CanonicalCaseLedger(target_path) as target:
        assert target.export_case(target_bundle.case_id) == target_bundle


def test_recovery_conformance_reports_product_identity_mismatch(tmp_path: Path) -> None:
    source_path = tmp_path / "source.db"
    expected = _bundle(payload_value="expected")
    different = _bundle(payload_value="different")
    _seed(source_path, expected)

    with SQLiteProvenanceStore(source_path) as source_store:
        source_identity = source_store.state_identity()

    manifest = RecoveryDrillManifestV1.build(
        source_profile=_profile(config="source"),
        target_profile=_profile(config="target"),
        source_bundle=expected,
        source_backend_identity=source_identity,
    )
    report = evaluate_recovery_conformance(
        manifest=manifest,
        restored_bundle=different,
        target_backend_identity=source_identity,
    )

    assert report.state is RecoveryConformanceState.FAIL
    assert "bundle_digest_mismatch" in report.violations
    assert "head_event_mismatch" in report.violations


def test_sqlite_drill_rejects_undeclared_backend_support(tmp_path: Path) -> None:
    source_path = tmp_path / "source.db"
    bundle = _bundle()
    _seed(source_path, bundle)

    with pytest.raises(RecoveryContinuityV1Error, match="unsupported source backend"):
        run_sqlite_case_recovery_drill(
            source_path=source_path,
            target_path=tmp_path / "target.db",
            case_id=bundle.case_id,
            source_profile=_profile(backend="future-db"),
            target_profile=_profile(),
        )


def test_manifest_and_report_tampering_fail_closed(tmp_path: Path) -> None:
    source_path = tmp_path / "source.db"
    target_path = tmp_path / "target.db"
    bundle = _bundle()
    _seed(source_path, bundle)
    manifest, report = run_sqlite_case_recovery_drill(
        source_path=source_path,
        target_path=target_path,
        case_id=bundle.case_id,
        source_profile=_profile(config="source"),
        target_profile=_profile(config="target"),
    )

    tampered_manifest = deepcopy(manifest.canonical_dict())
    tampered_manifest["source_event_count"] = 0
    with pytest.raises(RecoveryContinuityV1Error):
        RecoveryDrillManifestV1.from_dict(tampered_manifest)

    tampered_report = deepcopy(report.canonical_dict())
    tampered_report["restored_event_count"] = 999
    with pytest.raises(RecoveryContinuityV1Error, match="digest mismatch"):
        report.__class__.from_dict(tampered_report)
