from __future__ import annotations

import inspect
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

import core.durable_escrow_v1 as durable_module
from core.artifact_escrow_v1 import (
    ArtifactEscrowManifestV1,
    EscrowArtifactBindingV1,
    EscrowLimitsV1,
    FileSystemEscrowBackendV1,
)
from core.case_ledger.contracts import ContentAddress
from core.durable_escrow_v1 import (
    CapabilityEvidenceStateV1,
    DurabilityCapabilityEvidenceV1,
    DurabilityCapabilityV1,
    DurableEscrowLocationV1,
    DurableEscrowV1Error,
    ExternalDurabilityEvidenceStateV1,
    LocationRestoreReportV1,
    MultiLocationConformanceReportV1,
    MultiLocationEscrowPlanV1,
    MultiLocationReplicationReceiptV1,
    RestoreConformanceStateV1,
    build_multi_location_conformance_report_v1,
    build_multi_location_plan_v1,
    replicate_escrow_manifest_v1,
    verify_location_restore_v1,
)
from core.enterprise.recovery_continuity_v1 import StorageProfileV1
from core.long_range_replay_v1 import (
    LongRangeReplayManifestV1,
    ReplayArtifactBindingV1,
    ReplayArtifactRole,
    ReplayPreservationStatus,
)
from core.p3.contracts import content_digest

COMMIT_SHA = "a" * 40
TREE_SHA = "b" * 40
CASE_ID = "CASE-LRD-01G-0001"


def _logical_identity(role: ReplayArtifactRole) -> ContentAddress:
    return ContentAddress.for_value({"logical-role": role.value})


def _long_range_manifest(*, case_id: str = CASE_ID) -> LongRangeReplayManifestV1:
    artifacts = tuple(
        ReplayArtifactBindingV1(
            role=role,
            identity=_logical_identity(role),
            preservation=ReplayPreservationStatus.PRESERVED,
        )
        for role in ReplayArtifactRole
    )
    return LongRangeReplayManifestV1.build(
        case_id=case_id,
        case_replay_manifest_identity=ContentAddress.for_value({"case-replay": case_id}),
        coverage_matrix_identity=ContentAddress.for_value({"coverage": "LRD-01A"}),
        code_commit_sha=COMMIT_SHA,
        code_tree_sha=TREE_SHA,
        artifacts=artifacts,
        semantic_result_identity=_logical_identity(ReplayArtifactRole.SEMANTIC_RESULT),
        presentation_identity=None,
    )


def _materialize_source(
    root: Path,
) -> tuple[FileSystemEscrowBackendV1, ArtifactEscrowManifestV1, EscrowLimitsV1]:
    limits = EscrowLimitsV1()
    long_range = _long_range_manifest()
    backend = FileSystemEscrowBackendV1(root)
    bindings: list[EscrowArtifactBindingV1] = []
    by_role = {item.role: item for item in long_range.artifacts}
    for role in ReplayArtifactRole:
        data = f"durable-bytes::{role.value}".encode()
        blob = backend.publish(data, limits=limits)
        bindings.append(
            EscrowArtifactBindingV1.build(
                role=role,
                logical_identity=by_role[role].identity,
                blob=blob,
            )
        )
    escrow = ArtifactEscrowManifestV1.build(
        long_range_manifest=long_range,
        bindings=bindings,
    )
    return backend, escrow, limits


def _capabilities() -> tuple[DurabilityCapabilityEvidenceV1, ...]:
    items: list[DurabilityCapabilityEvidenceV1] = []
    engineering = {
        DurabilityCapabilityV1.EXACT_BYTE_VERIFICATION,
        DurabilityCapabilityV1.IMMUTABLE_PUBLICATION,
    }
    for capability in DurabilityCapabilityV1:
        if capability in engineering:
            items.append(
                DurabilityCapabilityEvidenceV1(
                    capability=capability,
                    state=CapabilityEvidenceStateV1.VERIFIED,
                    evidence_digest=content_digest(
                        {"implemented-capability": capability.value}
                    ),
                )
            )
        else:
            items.append(
                DurabilityCapabilityEvidenceV1(
                    capability=capability,
                    state=CapabilityEvidenceStateV1.UNVERIFIED,
                )
            )
    return tuple(items)


def _profile(name: str) -> StorageProfileV1:
    return StorageProfileV1.from_configuration(
        backend_kind="filesystem-escrow-v1",
        implementation_id="core.artifact_escrow_v1.FileSystemEscrowBackendV1",
        implementation_version="1",
        storage_schema="sha256-prefix-v1",
        public_configuration={"location": name},
    )


def _location(
    name: str,
    *,
    profile: StorageProfileV1 | None = None,
    failure_domain: str | None = None,
    credential_domain: str | None = None,
) -> DurableEscrowLocationV1:
    return DurableEscrowLocationV1.build(
        storage_profile=profile or _profile(name),
        location_id=f"location-{name}",
        failure_domain_id=failure_domain or f"failure-{name}",
        credential_domain_id=credential_domain or f"credential-{name}",
        capabilities=_capabilities(),
    )


def _replicated_fixture(
    tmp_path: Path,
) -> tuple[
    FileSystemEscrowBackendV1,
    FileSystemEscrowBackendV1,
    ArtifactEscrowManifestV1,
    EscrowLimitsV1,
    DurableEscrowLocationV1,
    DurableEscrowLocationV1,
    MultiLocationEscrowPlanV1,
    MultiLocationReplicationReceiptV1,
]:
    source_backend, escrow, limits = _materialize_source(tmp_path / "location-a")
    target_backend = FileSystemEscrowBackendV1(tmp_path / "location-b")
    source_location = _location("a")
    target_location = _location("b")
    plan = build_multi_location_plan_v1(
        expected_case_id=CASE_ID,
        escrow_manifest=escrow,
        source_location=source_location,
        target_location=target_location,
    )
    receipt = replicate_escrow_manifest_v1(
        plan=plan,
        escrow_manifest=escrow,
        source_location=source_location,
        target_location=target_location,
        source_backend=source_backend,
        target_backend=target_backend,
        limits=limits,
    )
    return (
        source_backend,
        target_backend,
        escrow,
        limits,
        source_location,
        target_location,
        plan,
        receipt,
    )


def _stored_path(backend: FileSystemEscrowBackendV1, digest: str) -> Path:
    return backend.root / "sha256" / digest[:2] / digest


def test_location_has_fixed_capability_inventory_and_round_trips() -> None:
    location = _location("a")

    assert {item.capability for item in location.capabilities} == set(
        DurabilityCapabilityV1
    )
    assert DurableEscrowLocationV1.from_dict(location.canonical_dict()) == location
    assert location.external_evidence_complete() is False


def test_engineering_capability_must_be_verified() -> None:
    capabilities = list(_capabilities())
    index = next(
        index
        for index, item in enumerate(capabilities)
        if item.capability is DurabilityCapabilityV1.EXACT_BYTE_VERIFICATION
    )
    capabilities[index] = DurabilityCapabilityEvidenceV1(
        capability=DurabilityCapabilityV1.EXACT_BYTE_VERIFICATION,
        state=CapabilityEvidenceStateV1.UNVERIFIED,
    )

    with pytest.raises(DurableEscrowV1Error, match="engineering capability must be VERIFIED"):
        DurableEscrowLocationV1.build(
            storage_profile=_profile("a"),
            location_id="location-a",
            failure_domain_id="failure-a",
            credential_domain_id="credential-a",
            capabilities=capabilities,
        )


def test_generic_location_cannot_self_verify_external_durability() -> None:
    capabilities = list(_capabilities())
    index = next(
        index
        for index, item in enumerate(capabilities)
        if item.capability is DurabilityCapabilityV1.WORM_OBJECT_LOCK
    )
    capabilities[index] = DurabilityCapabilityEvidenceV1(
        capability=DurabilityCapabilityV1.WORM_OBJECT_LOCK,
        state=CapabilityEvidenceStateV1.VERIFIED,
        evidence_digest=content_digest({"caller-claim": "worm"}),
    )

    with pytest.raises(DurableEscrowV1Error, match="cannot self-verify external durability"):
        DurableEscrowLocationV1.build(
            storage_profile=_profile("a"),
            location_id="location-a",
            failure_domain_id="failure-a",
            credential_domain_id="credential-a",
            capabilities=capabilities,
        )


def test_multi_location_requires_independent_profiles_failure_and_credentials(
    tmp_path: Path,
) -> None:
    _backend, escrow, _limits = _materialize_source(tmp_path / "source")
    source = _location("a")

    with pytest.raises(DurableEscrowV1Error, match="location identities must differ"):
        build_multi_location_plan_v1(
            expected_case_id=CASE_ID,
            escrow_manifest=escrow,
            source_location=source,
            target_location=source,
        )

    shared_profile = _profile("shared")
    with pytest.raises(DurableEscrowV1Error, match="storage profiles must differ"):
        build_multi_location_plan_v1(
            expected_case_id=CASE_ID,
            escrow_manifest=escrow,
            source_location=_location("a", profile=shared_profile),
            target_location=_location("b", profile=shared_profile),
        )

    with pytest.raises(DurableEscrowV1Error, match="failure domains must differ"):
        build_multi_location_plan_v1(
            expected_case_id=CASE_ID,
            escrow_manifest=escrow,
            source_location=_location("a", failure_domain="shared-failure"),
            target_location=_location("b", failure_domain="shared-failure"),
        )

    with pytest.raises(DurableEscrowV1Error, match="credential domains must differ"):
        build_multi_location_plan_v1(
            expected_case_id=CASE_ID,
            escrow_manifest=escrow,
            source_location=_location("a", credential_domain="shared-credential"),
            target_location=_location("b", credential_domain="shared-credential"),
        )


def test_replication_preserves_exact_blob_set_and_round_trips(tmp_path: Path) -> None:
    (
        _source_backend,
        target_backend,
        escrow,
        limits,
        _source_location,
        _target_location,
        plan,
        receipt,
    ) = _replicated_fixture(tmp_path)

    assert receipt.plan_digest == plan.plan_digest
    assert receipt.replicated_blob_count == len(escrow.bindings)
    assert receipt.replicated_bytes == sum(item.blob.size for item in escrow.bindings)
    assert MultiLocationEscrowPlanV1.from_dict(plan.canonical_dict()) == plan
    assert MultiLocationReplicationReceiptV1.from_dict(receipt.canonical_dict()) == receipt
    for binding in escrow.bindings:
        target_backend.read(binding.blob, limits=limits)


def test_target_restore_passes_after_source_location_is_destroyed(tmp_path: Path) -> None:
    (
        source_backend,
        target_backend,
        escrow,
        limits,
        _source_location,
        target_location,
        _plan,
        _receipt,
    ) = _replicated_fixture(tmp_path)
    shutil.rmtree(source_backend.root)

    report = verify_location_restore_v1(
        expected_case_id=CASE_ID,
        escrow_manifest=escrow,
        location=target_location,
        backend=target_backend,
        limits=limits,
    )

    assert report.state is RestoreConformanceStateV1.PASS
    assert report.verified_blob_count == len(escrow.bindings)
    assert report.verified_bytes == sum(item.blob.size for item in escrow.bindings)
    assert LocationRestoreReportV1.from_dict(report.canonical_dict()) == report


def test_target_tamper_is_fail_closed_restore_evidence(tmp_path: Path) -> None:
    (
        _source_backend,
        target_backend,
        escrow,
        limits,
        _source_location,
        target_location,
        _plan,
        _receipt,
    ) = _replicated_fixture(tmp_path)
    binding = escrow.bindings[0]
    stored = _stored_path(target_backend, binding.blob.digest)
    stored.chmod(0o600)
    mutated = bytearray(stored.read_bytes())
    mutated[0] ^= 0x01
    stored.write_bytes(mutated)

    report = verify_location_restore_v1(
        expected_case_id=CASE_ID,
        escrow_manifest=escrow,
        location=target_location,
        backend=target_backend,
        limits=limits,
    )

    assert report.state is RestoreConformanceStateV1.FAIL
    assert report.verified_blob_count == len(escrow.bindings) - 1
    assert any("verified_read_failed" in item for item in report.violations)


def test_missing_target_blob_is_fail_closed_restore_evidence(tmp_path: Path) -> None:
    (
        _source_backend,
        target_backend,
        escrow,
        limits,
        _source_location,
        target_location,
        _plan,
        _receipt,
    ) = _replicated_fixture(tmp_path)
    binding = escrow.bindings[0]
    stored = _stored_path(target_backend, binding.blob.digest)
    stored.chmod(0o600)
    stored.unlink()

    report = verify_location_restore_v1(
        expected_case_id=CASE_ID,
        escrow_manifest=escrow,
        location=target_location,
        backend=target_backend,
        limits=limits,
    )

    assert report.state is RestoreConformanceStateV1.FAIL
    assert report.verified_blob_count == len(escrow.bindings) - 1


def test_case_and_location_substitution_fail_closed(tmp_path: Path) -> None:
    (
        source_backend,
        target_backend,
        escrow,
        limits,
        source_location,
        target_location,
        plan,
        _receipt,
    ) = _replicated_fixture(tmp_path)

    with pytest.raises(DurableEscrowV1Error, match="tenant/case scope mismatch"):
        build_multi_location_plan_v1(
            expected_case_id="CASE-OTHER",
            escrow_manifest=escrow,
            source_location=source_location,
            target_location=target_location,
        )

    with pytest.raises(DurableEscrowV1Error, match="target location substitution rejected"):
        replicate_escrow_manifest_v1(
            plan=plan,
            escrow_manifest=escrow,
            source_location=source_location,
            target_location=_location("c"),
            source_backend=source_backend,
            target_backend=target_backend,
            limits=limits,
        )


def test_engineering_conformance_passes_without_fabricating_external_durability(
    tmp_path: Path,
) -> None:
    (
        source_backend,
        target_backend,
        escrow,
        limits,
        source_location,
        target_location,
        plan,
        receipt,
    ) = _replicated_fixture(tmp_path)
    source_restore = verify_location_restore_v1(
        expected_case_id=CASE_ID,
        escrow_manifest=escrow,
        location=source_location,
        backend=source_backend,
        limits=limits,
    )
    target_restore = verify_location_restore_v1(
        expected_case_id=CASE_ID,
        escrow_manifest=escrow,
        location=target_location,
        backend=target_backend,
        limits=limits,
    )

    report = build_multi_location_conformance_report_v1(
        plan=plan,
        replication_receipt=receipt,
        source_location=source_location,
        target_location=target_location,
        source_restore=source_restore,
        target_restore=target_restore,
    )

    assert report.state is RestoreConformanceStateV1.PASS
    assert (
        report.external_durability_evidence
        is ExternalDurabilityEvidenceStateV1.INCOMPLETE
    )
    assert report.ten_year_durability_claim is False
    assert MultiLocationConformanceReportV1.from_dict(report.canonical_dict()) == report


def test_aggregate_conformance_fails_when_one_location_restore_fails(
    tmp_path: Path,
) -> None:
    (
        source_backend,
        target_backend,
        escrow,
        limits,
        source_location,
        target_location,
        plan,
        receipt,
    ) = _replicated_fixture(tmp_path)
    binding = escrow.bindings[0]
    stored = _stored_path(target_backend, binding.blob.digest)
    stored.chmod(0o600)
    stored.unlink()
    source_restore = verify_location_restore_v1(
        expected_case_id=CASE_ID,
        escrow_manifest=escrow,
        location=source_location,
        backend=source_backend,
        limits=limits,
    )
    target_restore = verify_location_restore_v1(
        expected_case_id=CASE_ID,
        escrow_manifest=escrow,
        location=target_location,
        backend=target_backend,
        limits=limits,
    )

    report = build_multi_location_conformance_report_v1(
        plan=plan,
        replication_receipt=receipt,
        source_location=source_location,
        target_location=target_location,
        source_restore=source_restore,
        target_restore=target_restore,
    )

    assert report.state is RestoreConformanceStateV1.FAIL
    assert report.violations == ("target_location_restore_failed",)


def test_unknown_fields_and_digest_tampering_fail_closed(tmp_path: Path) -> None:
    (
        _source_backend,
        _target_backend,
        _escrow,
        _limits,
        source_location,
        _target_location,
        plan,
        receipt,
    ) = _replicated_fixture(tmp_path)
    location_raw = deepcopy(source_location.canonical_dict())
    location_raw["future_field"] = "forbidden"
    with pytest.raises(DurableEscrowV1Error, match="unknown=future_field"):
        DurableEscrowLocationV1.from_dict(location_raw)

    plan_raw = deepcopy(plan.canonical_dict())
    plan_raw["plan_digest"] = "f" * 64
    with pytest.raises(DurableEscrowV1Error, match="plan digest mismatch"):
        MultiLocationEscrowPlanV1.from_dict(plan_raw)

    receipt_raw = deepcopy(receipt.canonical_dict())
    receipt_raw["receipt_digest"] = "e" * 64
    with pytest.raises(DurableEscrowV1Error, match="receipt digest mismatch"):
        MultiLocationReplicationReceiptV1.from_dict(receipt_raw)


def test_ten_year_claim_is_structurally_rejected(tmp_path: Path) -> None:
    (
        source_backend,
        target_backend,
        escrow,
        limits,
        source_location,
        target_location,
        plan,
        receipt,
    ) = _replicated_fixture(tmp_path)
    source_restore = verify_location_restore_v1(
        expected_case_id=CASE_ID,
        escrow_manifest=escrow,
        location=source_location,
        backend=source_backend,
        limits=limits,
    )
    target_restore = verify_location_restore_v1(
        expected_case_id=CASE_ID,
        escrow_manifest=escrow,
        location=target_location,
        backend=target_backend,
        limits=limits,
    )
    report = build_multi_location_conformance_report_v1(
        plan=plan,
        replication_receipt=receipt,
        source_location=source_location,
        target_location=target_location,
        source_restore=source_restore,
        target_restore=target_restore,
    )
    raw = deepcopy(report.canonical_dict())
    raw["ten_year_durability_claim"] = True

    with pytest.raises(DurableEscrowV1Error, match="cannot claim ten-year durability"):
        MultiLocationConformanceReportV1.from_dict(raw)


def test_module_has_no_product_or_canonical_ledger_write_authority() -> None:
    source = inspect.getsource(durable_module)

    assert "CanonicalCaseLedger" not in source
    assert "append_event(" not in source
    assert "restore_case(" not in source
    assert "ProductRuntime" not in source
