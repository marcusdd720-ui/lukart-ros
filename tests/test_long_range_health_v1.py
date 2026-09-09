from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from core.artifact_escrow_v1 import (
    ArtifactEscrowError,
    ArtifactEscrowManifestV1,
    EscrowArtifactBindingV1,
    EscrowLimitsV1,
    FileSystemEscrowBackendV1,
)
from core.case_ledger.contracts import CaseId, CaseLedgerBundle, ContentAddress, LedgerEvent
from core.case_ledger.ledger import CanonicalCaseLedger
from core.crypto_agility_v1 import CryptoKeyStatus, CryptoTrustKeyV1, CryptoTrustSetV1
from core.enterprise.contracts import AttestationPurpose, AttestationSigner
from core.enterprise.recovery_continuity_v1 import (
    RecoveryConformanceReportV1,
    RecoveryConformanceState,
    RecoveryDrillManifestV1,
    StorageProfileV1,
    run_sqlite_case_recovery_drill,
)
from core.long_range_health_v1 import (
    CryptoRenewalAttestationV1,
    FreshnessPolicyV1,
    HealthDimensionState,
    LongRangeHealthError,
    LongRangeHealthState,
    StoragePortabilityDrillV1,
    evaluate_long_range_health_v1,
    renew_crypto_attestation_v1,
    run_storage_portability_drill_v1,
)
from core.long_range_replay_v1 import (
    LongRangeReplayManifestV1,
    ReplayArtifactBindingV1,
    ReplayArtifactRole,
    ReplayPreservationStatus,
)

CASE_ID = "CASE-LRD-01E-0001"
COMMIT_SHA = "a" * 40
TREE_SHA = "b" * 40


def _key(
    signer: AttestationSigner,
    *,
    status: CryptoKeyStatus = CryptoKeyStatus.ACTIVE,
    not_before: int = 100,
    retire_at: int | None = None,
    predecessor_key_id: str | None = None,
) -> CryptoTrustKeyV1:
    return CryptoTrustKeyV1.from_public_key_bytes(
        key_id=signer.key_id,
        public_key=signer.public_key_bytes(),
        status=status,
        not_before=not_before,
        retire_at=retire_at,
        predecessor_key_id=predecessor_key_id,
        allowed_purposes=(AttestationPurpose.PROVENANCE,),
    )


def _renewal(*, case_id: str = CASE_ID, renewed_at: int = 200) -> CryptoRenewalAttestationV1:
    old = AttestationSigner.generate("old-2026")
    new = AttestationSigner.generate("new-2027")
    old_trust = CryptoTrustSetV1(keys=(_key(old),))
    old_payload = {"artifact": "case-replay", "version": 1}
    historical = old.sign(
        purpose=AttestationPurpose.PROVENANCE,
        subject_digest="c" * 64,
        payload=old_payload,
        issued_at=120,
        expires_at=500,
        nonce="historical",
    )
    current = CryptoTrustSetV1(
        keys=(
            _key(old, status=CryptoKeyStatus.RETIRED, retire_at=180),
            _key(new, not_before=180, predecessor_key_id=old.key_id),
        ),
        previous_trust_set_digest=old_trust.trust_set_digest,
    )
    return renew_crypto_attestation_v1(
        case_id=case_id,
        historical_attestation=historical,
        historical_payload=old_payload,
        historical_trust_set=old_trust,
        current_trust_set=current,
        current_signer=new,
        renewed_at=renewed_at,
        expires_at=600,
        nonce="renewal",
    )


def _logical_identity(role: ReplayArtifactRole) -> ContentAddress:
    return ContentAddress.for_value({"logical-role": role.value})


def _long_range() -> LongRangeReplayManifestV1:
    artifacts = tuple(
        ReplayArtifactBindingV1(
            role=role,
            identity=_logical_identity(role),
            preservation=ReplayPreservationStatus.PRESERVED,
        )
        for role in ReplayArtifactRole
    )
    return LongRangeReplayManifestV1.build(
        case_id=CASE_ID,
        case_replay_manifest_identity=ContentAddress.for_value({"case-replay": CASE_ID}),
        coverage_matrix_identity=ContentAddress.for_value({"coverage": "01E"}),
        code_commit_sha=COMMIT_SHA,
        code_tree_sha=TREE_SHA,
        artifacts=artifacts,
        semantic_result_identity=_logical_identity(ReplayArtifactRole.SEMANTIC_RESULT),
        presentation_identity=None,
    )


def _escrow(
    root: Path,
) -> tuple[FileSystemEscrowBackendV1, LongRangeReplayManifestV1, ArtifactEscrowManifestV1]:
    limits = EscrowLimitsV1()
    lrd = _long_range()
    backend = FileSystemEscrowBackendV1(root)
    bindings = []
    for artifact in lrd.artifacts:
        blob = backend.publish(f"bytes::{artifact.role.value}".encode(), limits=limits)
        bindings.append(
            EscrowArtifactBindingV1.build(
                role=artifact.role,
                logical_identity=artifact.identity,
                blob=blob,
            )
        )
    return backend, lrd, ArtifactEscrowManifestV1.build(
        long_range_manifest=lrd,
        bindings=bindings,
    )


def _profile(label: str) -> StorageProfileV1:
    return StorageProfileV1.from_configuration(
        backend_kind="filesystem-escrow",
        implementation_id="core.artifact_escrow_v1.FileSystemEscrowBackendV1",
        implementation_version="v1",
        storage_schema="sha256-content-addressed-v1",
        public_configuration={"location_label": label},
    )


def _bundle() -> CaseLedgerBundle:
    case_id = CaseId(CASE_ID)
    event = LedgerEvent.build(
        case_id=case_id,
        case_sequence=0,
        event_type="lrd.health.seed.v1",
        runtime_identity_digest=ContentAddress.for_value({"runtime": "01e-test"}),
        payload={"value": "alpha"},
        previous_event_id=None,
    )
    return CaseLedgerBundle.build(case_id=case_id, events=(event,))


def _recovery(
    tmp_path: Path,
) -> tuple[RecoveryDrillManifestV1, RecoveryConformanceReportV1]:
    source = tmp_path / "source.db"
    target = tmp_path / "target.db"
    bundle = _bundle()
    with CanonicalCaseLedger(source) as ledger:
        ledger.restore_case(bundle.case_id, bundle.canonical_dict())
    source_profile = StorageProfileV1.from_configuration(
        backend_kind="sqlite-provenance",
        implementation_id="core.enterprise.durability.SQLiteProvenanceStore",
        implementation_version="v1",
        storage_schema="provenance-v1",
        public_configuration={"location": "source"},
    )
    target_profile = StorageProfileV1.from_configuration(
        backend_kind="sqlite-provenance",
        implementation_id="core.enterprise.durability.SQLiteProvenanceStore",
        implementation_version="v1",
        storage_schema="provenance-v1",
        public_configuration={"location": "target"},
    )
    return run_sqlite_case_recovery_drill(
        source_path=source,
        target_path=target,
        case_id=bundle.case_id,
        source_profile=source_profile,
        target_profile=target_profile,
    )


def test_crypto_renewal_verifies_old_proof_and_adds_chained_current_proof() -> None:
    renewal = _renewal()
    assert renewal.subject_digest == "c" * 64
    assert renewal.renewed_attestation.subject_digest == renewal.subject_digest
    assert renewal.current_trust_set_digest != renewal.historical_trust_set_digest
    assert len(renewal.renewal_digest) == 64
    assert CryptoRenewalAttestationV1.from_dict(renewal.canonical_dict()) == renewal


def test_crypto_renewal_rejects_unchained_trust_set() -> None:
    old = AttestationSigner.generate("old")
    new = AttestationSigner.generate("new")
    old_trust = CryptoTrustSetV1(keys=(_key(old),))
    historical = old.sign(
        purpose=AttestationPurpose.PROVENANCE,
        subject_digest="d" * 64,
        payload={"x": 1},
        issued_at=120,
        expires_at=500,
        nonce="old",
    )
    unchained = CryptoTrustSetV1(keys=(_key(new, not_before=180),))
    with pytest.raises(LongRangeHealthError, match="not chained"):
        renew_crypto_attestation_v1(
            case_id=CASE_ID,
            historical_attestation=historical,
            historical_payload={"x": 1},
            historical_trust_set=old_trust,
            current_trust_set=unchained,
            current_signer=new,
            renewed_at=200,
            expires_at=500,
            nonce="new",
        )


def test_revoked_historical_proof_cannot_be_renewed() -> None:
    old = AttestationSigner.generate("old")
    new = AttestationSigner.generate("new")
    revoked = CryptoTrustSetV1(keys=(_key(old, status=CryptoKeyStatus.REVOKED),))
    historical = old.sign(
        purpose=AttestationPurpose.PROVENANCE,
        subject_digest="d" * 64,
        payload={"x": 1},
        issued_at=120,
        expires_at=500,
        nonce="old",
    )
    current = CryptoTrustSetV1(
        keys=(_key(new, not_before=180),),
        previous_trust_set_digest=revoked.trust_set_digest,
    )
    with pytest.raises(ValueError, match="revoked"):
        renew_crypto_attestation_v1(
            case_id=CASE_ID,
            historical_attestation=historical,
            historical_payload={"x": 1},
            historical_trust_set=revoked,
            current_trust_set=current,
            current_signer=new,
            renewed_at=200,
            expires_at=500,
            nonce="new",
        )


def test_crypto_renewal_unknown_field_and_digest_tamper_fail_closed() -> None:
    renewal = _renewal()
    unknown = renewal.canonical_dict()
    unknown["trust_override"] = True
    with pytest.raises(LongRangeHealthError, match="unknown=trust_override"):
        CryptoRenewalAttestationV1.from_dict(unknown)
    tampered = deepcopy(renewal.canonical_dict())
    tampered["case_id"] = "OTHER"
    with pytest.raises(LongRangeHealthError, match="digest mismatch"):
        CryptoRenewalAttestationV1.from_dict(tampered)


def test_portability_drill_migrates_every_preserved_blob_and_rereads_target(tmp_path: Path) -> None:
    source, lrd, escrow = _escrow(tmp_path / "source")
    target = FileSystemEscrowBackendV1(tmp_path / "target")
    drill = run_storage_portability_drill_v1(
        long_range_manifest=lrd,
        escrow_manifest=escrow,
        source=source,
        target=target,
        source_profile=_profile("source"),
        target_profile=_profile("target"),
        limits=EscrowLimitsV1(),
        observed_at=300,
    )
    assert drill.artifact_count == len(escrow.bindings)
    assert drill.total_bytes == sum(item.blob.size for item in escrow.bindings)
    assert len(drill.migrated_blob_set_digest) == 64
    assert StoragePortabilityDrillV1.from_dict(drill.canonical_dict()) == drill
    for binding in escrow.bindings:
        assert target.read(binding.blob, limits=EscrowLimitsV1()) == source.read(
            binding.blob, limits=EscrowLimitsV1()
        )


def test_portability_source_tamper_fails_closed(tmp_path: Path) -> None:
    source, lrd, escrow = _escrow(tmp_path / "source")
    binding = escrow.bindings[0]
    stored = source.root / "sha256" / binding.blob.digest[:2] / binding.blob.digest
    stored.chmod(0o600)
    data = bytearray(stored.read_bytes())
    data[0] ^= 1
    stored.write_bytes(data)
    with pytest.raises(ArtifactEscrowError, match="digest mismatch"):
        run_storage_portability_drill_v1(
            long_range_manifest=lrd,
            escrow_manifest=escrow,
            source=source,
            target=FileSystemEscrowBackendV1(tmp_path / "target"),
            source_profile=_profile("source"),
            target_profile=_profile("target"),
            limits=EscrowLimitsV1(),
            observed_at=300,
        )


def test_portability_requires_distinct_storage_profile_identity(tmp_path: Path) -> None:
    source, lrd, escrow = _escrow(tmp_path / "source")
    profile = _profile("same")
    with pytest.raises(LongRangeHealthError, match="distinct storage profiles"):
        run_storage_portability_drill_v1(
            long_range_manifest=lrd,
            escrow_manifest=escrow,
            source=source,
            target=FileSystemEscrowBackendV1(tmp_path / "target"),
            source_profile=profile,
            target_profile=profile,
            limits=EscrowLimitsV1(),
            observed_at=300,
        )


def test_fresh_health_requires_fresh_crypto_portability_and_recovery(tmp_path: Path) -> None:
    renewal = _renewal(renewed_at=900)
    source, lrd, escrow = _escrow(tmp_path / "escrow-source")
    portability = run_storage_portability_drill_v1(
        long_range_manifest=lrd,
        escrow_manifest=escrow,
        source=source,
        target=FileSystemEscrowBackendV1(tmp_path / "escrow-target"),
        source_profile=_profile("source"),
        target_profile=_profile("target"),
        limits=EscrowLimitsV1(),
        observed_at=920,
    )
    manifest, recovery = _recovery(tmp_path)
    report = evaluate_long_range_health_v1(
        case_id=CASE_ID,
        drift_report_digest="e" * 64,
        evaluated_at=1000,
        policy=FreshnessPolicyV1(200, 200, 200),
        crypto_renewal=renewal,
        portability_drill=portability,
        recovery_manifest=manifest,
        recovery_report=recovery,
        recovery_observed_at=950,
    )
    assert report.state is LongRangeHealthState.HEALTHY
    assert report.violations == ()
    assert report.crypto_state is HealthDimensionState.FRESH


def test_historical_pass_cannot_hide_stale_current_evidence(tmp_path: Path) -> None:
    renewal = _renewal(renewed_at=100)
    source, lrd, escrow = _escrow(tmp_path / "escrow-source")
    portability = run_storage_portability_drill_v1(
        long_range_manifest=lrd,
        escrow_manifest=escrow,
        source=source,
        target=FileSystemEscrowBackendV1(tmp_path / "escrow-target"),
        source_profile=_profile("source"),
        target_profile=_profile("target"),
        limits=EscrowLimitsV1(),
        observed_at=100,
    )
    manifest, recovery = _recovery(tmp_path)
    report = evaluate_long_range_health_v1(
        case_id=CASE_ID,
        drift_report_digest="e" * 64,
        evaluated_at=1000,
        policy=FreshnessPolicyV1(100, 100, 100),
        crypto_renewal=renewal,
        portability_drill=portability,
        recovery_manifest=manifest,
        recovery_report=recovery,
        recovery_observed_at=100,
    )
    assert report.state is LongRangeHealthState.STALE
    assert set(report.violations) == {
        "crypto_renewal_stale",
        "portability_drill_stale",
        "recovery_drill_stale",
    }


def test_missing_evidence_is_unverifiable_not_healthy() -> None:
    report = evaluate_long_range_health_v1(
        case_id=CASE_ID,
        drift_report_digest="e" * 64,
        evaluated_at=1000,
        policy=FreshnessPolicyV1(100, 100, 100),
        crypto_renewal=None,
        portability_drill=None,
        recovery_manifest=None,
        recovery_report=None,
        recovery_observed_at=None,
    )
    assert report.state is LongRangeHealthState.UNVERIFIABLE
    assert report.crypto_state is HealthDimensionState.MISSING
    assert report.portability_state is HealthDimensionState.MISSING
    assert report.recovery_state is HealthDimensionState.MISSING


def test_future_timestamp_and_cross_case_substitution_fail_closed() -> None:
    with pytest.raises(LongRangeHealthError, match="future"):
        evaluate_long_range_health_v1(
            case_id=CASE_ID,
            drift_report_digest="e" * 64,
            evaluated_at=100,
            policy=FreshnessPolicyV1(100, 100, 100),
            crypto_renewal=_renewal(renewed_at=101),
            portability_drill=None,
            recovery_manifest=None,
            recovery_report=None,
            recovery_observed_at=None,
        )
    with pytest.raises(LongRangeHealthError, match="case scope mismatch"):
        evaluate_long_range_health_v1(
            case_id=CASE_ID,
            drift_report_digest="e" * 64,
            evaluated_at=1000,
            policy=FreshnessPolicyV1(1000, 1000, 1000),
            crypto_renewal=_renewal(case_id="OTHER", renewed_at=200),
            portability_drill=None,
            recovery_manifest=None,
            recovery_report=None,
            recovery_observed_at=None,
        )


def test_failed_recovery_is_degraded_not_fresh(tmp_path: Path) -> None:
    manifest, recovery = _recovery(tmp_path)
    failed = RecoveryConformanceReportV1(
        manifest_digest=recovery.manifest_digest,
        target_backend_identity_digest=recovery.target_backend_identity_digest,
        restored_bundle_digest=recovery.restored_bundle_digest,
        restored_head_event_digest=recovery.restored_head_event_digest,
        restored_event_count=recovery.restored_event_count,
        state=RecoveryConformanceState.FAIL,
        violations=("forced_failure",),
    )
    report = evaluate_long_range_health_v1(
        case_id=CASE_ID,
        drift_report_digest="e" * 64,
        evaluated_at=1000,
        policy=FreshnessPolicyV1(1000, 1000, 1000),
        crypto_renewal=None,
        portability_drill=None,
        recovery_manifest=manifest,
        recovery_report=failed,
        recovery_observed_at=900,
    )
    assert report.state is LongRangeHealthState.DEGRADED
    assert report.recovery_state is HealthDimensionState.FAIL
