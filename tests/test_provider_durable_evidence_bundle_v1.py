from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

import pytest

from core.artifact_escrow_v1 import (
    ArtifactEscrowManifestV1,
    EscrowArtifactBindingV1,
    EscrowBlobIdentityV1,
    EscrowLimitsV1,
)
from core.case_ledger.contracts import ContentAddress
from core.durable_escrow_v1 import (
    MultiLocationReplicationReceiptV1,
    build_multi_location_plan_v1,
    replicate_escrow_manifest_v1,
    verify_location_restore_v1,
)
from core.long_range_replay_v1 import (
    LongRangeReplayManifestV1,
    ReplayArtifactBindingV1,
    ReplayArtifactRole,
    ReplayPreservationStatus,
)
from core.p3.contracts import content_digest
from core.provider_durable_evidence_bundle_v1 import (
    SYNTHETIC_PROVIDER_DRILL_CASE_ID_V1,
    ProviderDurableEvidenceBundleV1Error,
    ProviderDurableEvidenceCaptureV1,
    ProviderSourceLossDrillEvidenceV1,
    parse_aws_s3_profile_v1,
    parse_credential_scope_evidence_v1,
    parse_location_provider_evidence_v1,
    parse_object_lock_evidence_v1,
    parse_provider_pair_report_v1,
)
from core.provider_durable_storage_v1 import (
    build_provider_pair_report_v1,
    verify_s3_location_v1,
)
from scripts.provider_durable_storage_drill import (
    OPERATOR_CONFIG_SCHEMA_V1,
    ProviderDrillOperatorError,
    load_operator_config,
)
from tests.test_provider_durable_storage_v1 import (
    NOW,
    _FakeIam,
    _FakeS3,
    _FakeSts,
    _location,
    _materialize,
    _profile,
)

CODE_SHA = "c" * 40


def _manifest() -> tuple[ArtifactEscrowManifestV1, dict[ReplayArtifactRole, bytes]]:
    logical = {
        role: ContentAddress.for_value(
            {
                "stage": "LRD-01H",
                "case_id": SYNTHETIC_PROVIDER_DRILL_CASE_ID_V1,
                "role": role.value,
            }
        )
        for role in ReplayArtifactRole
    }
    artifacts = tuple(
        ReplayArtifactBindingV1(
            role=role,
            identity=logical[role],
            preservation=ReplayPreservationStatus.PRESERVED,
        )
        for role in ReplayArtifactRole
    )
    long_range = LongRangeReplayManifestV1.build(
        case_id=SYNTHETIC_PROVIDER_DRILL_CASE_ID_V1,
        case_replay_manifest_identity=ContentAddress.for_value(
            {"stage": "LRD-01H", "kind": "synthetic-case-replay"}
        ),
        coverage_matrix_identity=ContentAddress.for_value(
            {"stage": "LRD-01H", "kind": "synthetic-coverage"}
        ),
        code_commit_sha=CODE_SHA,
        code_tree_sha="d" * 40,
        artifacts=artifacts,
        semantic_result_identity=logical[ReplayArtifactRole.SEMANTIC_RESULT],
        presentation_identity=None,
    )
    data_by_role = {
        role: f"LRD-01H bundle test::{role.value}\n".encode()
        for role in ReplayArtifactRole
    }
    bindings = tuple(
        EscrowArtifactBindingV1.build(
            role=role,
            logical_identity=logical[role],
            blob=EscrowBlobIdentityV1.for_bytes(data_by_role[role]),
        )
        for role in ReplayArtifactRole
    )
    return (
        ArtifactEscrowManifestV1.build(
            long_range_manifest=long_range,
            bindings=bindings,
        ),
        data_by_role,
    )


def _capture(
    *,
    source_policy_arn: str = "arn:aws:iam::acct-a:role/escrow-a",
    source_principal_arn: str = "arn:aws:iam::acct-a:role/escrow-a",
    source_s3: _FakeS3 | None = None,
) -> ProviderDurableEvidenceCaptureV1:
    escrow, data_by_role = _manifest()
    source_profile = _profile(
        "bundle-a",
        region="eu-central-1",
        owner="account-alpha",
        credential_domain="credential-alpha",
        policy_source_arn=source_policy_arn,
    )
    target_profile = _profile(
        "bundle-b",
        region="eu-west-1",
        owner="account-beta",
        credential_domain="credential-beta",
        policy_source_arn="arn:aws:iam::acct-b:role/escrow-b",
    )
    source_s3 = source_s3 or _FakeS3(
        bucket=source_profile.bucket,
        owner="account-alpha",
        region=source_profile.region,
    )
    target_s3 = _FakeS3(
        bucket=target_profile.bucket,
        owner="account-beta",
        region=target_profile.region,
    )
    from core.provider_durable_storage_v1 import AwsS3ObjectLockEscrowBackendV1

    source = AwsS3ObjectLockEscrowBackendV1(
        s3_client=source_s3,
        profile=source_profile,
    )
    target = AwsS3ObjectLockEscrowBackendV1(
        s3_client=target_s3,
        profile=target_profile,
    )
    _materialize(source, escrow, data_by_role)
    source_location = _location(source_profile, "bundle-a")
    target_location = _location(target_profile, "bundle-b")
    plan = build_multi_location_plan_v1(
        expected_case_id=SYNTHETIC_PROVIDER_DRILL_CASE_ID_V1,
        escrow_manifest=escrow,
        source_location=source_location,
        target_location=target_location,
    )
    replication = replicate_escrow_manifest_v1(
        plan=plan,
        escrow_manifest=escrow,
        source_location=source_location,
        target_location=target_location,
        source_backend=source,
        target_backend=target,
        limits=EscrowLimitsV1(),
    )
    source_evidence, source_scope = verify_s3_location_v1(
        expected_case_id=SYNTHETIC_PROVIDER_DRILL_CASE_ID_V1,
        escrow_manifest=escrow,
        generic_location=source_location,
        backend=source,
        s3_client=source_s3,
        sts_client=_FakeSts(
            account="account-alpha",
            arn=source_principal_arn,
        ),
        iam_client=_FakeIam(),
        observed_at=NOW,
        limits=EscrowLimitsV1(),
    )
    target_evidence, target_scope = verify_s3_location_v1(
        expected_case_id=SYNTHETIC_PROVIDER_DRILL_CASE_ID_V1,
        escrow_manifest=escrow,
        generic_location=target_location,
        backend=target,
        s3_client=target_s3,
        sts_client=_FakeSts(
            account="account-beta",
            arn="arn:aws:iam::acct-b:role/escrow-b",
        ),
        iam_client=_FakeIam(),
        observed_at=NOW,
        limits=EscrowLimitsV1(),
    )
    pair = build_provider_pair_report_v1(
        source_location=source_location,
        target_location=target_location,
        source_evidence=source_evidence,
        target_evidence=target_evidence,
    )
    return ProviderDurableEvidenceCaptureV1(
        code_sha=CODE_SHA,
        case_id=SYNTHETIC_PROVIDER_DRILL_CASE_ID_V1,
        escrow_manifest=escrow,
        source_profile=source_profile,
        target_profile=target_profile,
        source_location=source_location,
        target_location=target_location,
        source_versions=source.version_bindings(),
        target_versions=target.version_bindings(),
        source_credential_scope=source_scope,
        target_credential_scope=target_scope,
        source_evidence=source_evidence,
        target_evidence=target_evidence,
        plan=plan,
        replication_receipt=replication,
        pair_report=pair,
    )


def _drill(capture: ProviderDurableEvidenceCaptureV1) -> ProviderSourceLossDrillEvidenceV1:
    target_profile = capture.target_profile
    target_s3 = _FakeS3(
        bucket=target_profile.bucket,
        owner="account-beta",
        region=target_profile.region,
    )
    from core.provider_durable_storage_v1 import AwsS3ObjectLockEscrowBackendV1

    data_by_digest = {
        binding.blob.digest: f"LRD-01H bundle test::{binding.role.value}\n".encode()
        for binding in capture.escrow_manifest.bindings
    }
    for version in capture.target_versions:
        target_s3.objects[(version.key, version.version_id)] = data_by_digest[
            version.blob_digest
        ]
    target = AwsS3ObjectLockEscrowBackendV1(
        s3_client=target_s3,
        profile=target_profile,
        version_bindings=capture.target_versions,
    )
    target_evidence, target_scope = verify_s3_location_v1(
        expected_case_id=capture.case_id,
        escrow_manifest=capture.escrow_manifest,
        generic_location=capture.target_location,
        backend=target,
        s3_client=target_s3,
        sts_client=_FakeSts(
            account="account-beta",
            arn="arn:aws:iam::acct-b:role/escrow-b",
        ),
        iam_client=_FakeIam(),
        observed_at=NOW,
        limits=EscrowLimitsV1(),
    )
    restore = verify_location_restore_v1(
        expected_case_id=capture.case_id,
        escrow_manifest=capture.escrow_manifest,
        location=capture.target_location,
        backend=target,
        limits=EscrowLimitsV1(),
    )
    return ProviderSourceLossDrillEvidenceV1(
        capture=capture,
        post_loss_target_credential_scope=target_scope,
        post_loss_target_evidence=target_evidence,
        target_restore=restore,
        source_unavailability_evidence_digest=content_digest(
            {"external-source-unavailability": "synthetic-test-only"}
        ),
    )


def test_capture_and_drill_round_trip_strictly() -> None:
    capture = _capture()
    restored_capture = ProviderDurableEvidenceCaptureV1.from_dict(
        capture.canonical_dict()
    )
    assert restored_capture == capture
    assert restored_capture.capture_digest == capture.capture_digest

    drill = _drill(capture)
    restored_drill = ProviderSourceLossDrillEvidenceV1.from_dict(
        drill.canonical_dict()
    )
    assert restored_drill == drill
    assert restored_drill.drill_digest == drill.drill_digest
    assert restored_drill.status.value == "CAPTURED_NOT_CLOSURE_AUTHORITY"


@pytest.mark.parametrize(
    ("parser", "selector"),
    [
        (parse_aws_s3_profile_v1, lambda capture: capture.source_profile.canonical_dict()),
        (
            parse_credential_scope_evidence_v1,
            lambda capture: capture.source_credential_scope.canonical_dict(),
        ),
        (
            parse_object_lock_evidence_v1,
            lambda capture: capture.source_evidence.object_evidence[0].canonical_dict(),
        ),
        (
            parse_location_provider_evidence_v1,
            lambda capture: capture.source_evidence.canonical_dict(),
        ),
        (parse_provider_pair_report_v1, lambda capture: capture.pair_report.canonical_dict()),
    ],
)
def test_all_provider_evidence_parsers_reject_unknown_fields(
    parser: Callable[[Mapping[str, object]], object],
    selector: Callable[[ProviderDurableEvidenceCaptureV1], dict[str, object]],
) -> None:
    raw = selector(_capture())
    raw["unexpected"] = True
    with pytest.raises(ProviderDurableEvidenceBundleV1Error, match="unknown=unexpected"):
        parser(raw)


def test_capture_rejects_digest_tampering() -> None:
    raw = _capture().canonical_dict()
    raw["capture_digest"] = "0" * 64
    with pytest.raises(ProviderDurableEvidenceBundleV1Error, match="capture digest mismatch"):
        ProviderDurableEvidenceCaptureV1.from_dict(raw)


def test_nested_provider_evidence_digest_tampering_is_rejected() -> None:
    raw = _capture().canonical_dict()
    source = cast(dict[str, object], raw["source_evidence"])
    source["evidence_digest"] = "0" * 64
    with pytest.raises(
        ProviderDurableEvidenceBundleV1Error,
        match="location provider evidence digest mismatch",
    ):
        ProviderDurableEvidenceCaptureV1.from_dict(raw)


def test_old_verifier_principal_substitution_cannot_enter_closure_bundle() -> None:
    with pytest.raises(
        ProviderDurableEvidenceBundleV1Error,
        match="policy evidence principal does not match STS storage principal",
    ):
        _capture(
            source_policy_arn="arn:aws:iam::acct-a:role/different-policy-role",
            source_principal_arn="arn:aws:iam::acct-a:role/actual-storage-role",
        )


class _MissingRequestIdS3(_FakeS3):
    def _response(self, request_id: str) -> dict[str, object]:
        if request_id == "hold":
            return {"ResponseMetadata": {}}
        return super()._response(request_id)


def test_old_verifier_missing_request_id_cannot_enter_closure_bundle() -> None:
    profile = _profile(
        "bundle-a",
        region="eu-central-1",
        owner="account-alpha",
        credential_domain="credential-alpha",
        policy_source_arn="arn:aws:iam::acct-a:role/escrow-a",
    )
    s3 = _MissingRequestIdS3(
        bucket=profile.bucket,
        owner="account-alpha",
        region=profile.region,
    )
    with pytest.raises(
        ProviderDurableEvidenceBundleV1Error,
        match="five exact provider request identifiers",
    ):
        _capture(source_s3=s3)


def test_capture_is_structurally_synthetic_only() -> None:
    capture = _capture()
    with pytest.raises(ProviderDurableEvidenceBundleV1Error, match="synthetic-only"):
        ProviderDurableEvidenceCaptureV1(
            code_sha=capture.code_sha,
            case_id="CASE-REAL-001",
            escrow_manifest=capture.escrow_manifest,
            source_profile=capture.source_profile,
            target_profile=capture.target_profile,
            source_location=capture.source_location,
            target_location=capture.target_location,
            source_versions=capture.source_versions,
            target_versions=capture.target_versions,
            source_credential_scope=capture.source_credential_scope,
            target_credential_scope=capture.target_credential_scope,
            source_evidence=capture.source_evidence,
            target_evidence=capture.target_evidence,
            plan=capture.plan,
            replication_receipt=capture.replication_receipt,
            pair_report=capture.pair_report,
        )


def test_forged_closure_status_is_rejected() -> None:
    raw = _drill(_capture()).canonical_dict()
    raw["status"] = "CLOSED / ENGINEERING PASS"
    with pytest.raises(
        ProviderDurableEvidenceBundleV1Error,
        match="unknown provider drill",
    ):
        ProviderSourceLossDrillEvidenceV1.from_dict(raw)


def test_source_unavailability_digest_tampering_is_rejected() -> None:
    raw = _drill(_capture()).canonical_dict()
    raw["source_unavailability_evidence_digest"] = "0" * 64
    with pytest.raises(
        ProviderDurableEvidenceBundleV1Error,
        match="drill evidence digest mismatch",
    ):
        ProviderSourceLossDrillEvidenceV1.from_dict(raw)


def _operator_config() -> dict[str, object]:
    return {
        "schema": OPERATOR_CONFIG_SCHEMA_V1,
        "source": {
            "aws_profile": "lrd-source-storage",
            "auditor_aws_profile": "lrd-source-auditor",
            "region": "eu-central-1",
            "bucket": "synthetic-lrd-source",
            "key_prefix": "lrd/01h/source",
            "expected_bucket_owner": "account-alpha",
            "credential_domain_id": "credential-alpha",
            "policy_source_arn": "arn:aws:iam::acct-a:role/escrow-a",
        },
        "target": {
            "aws_profile": "lrd-target-storage",
            "auditor_aws_profile": "lrd-target-auditor",
            "region": "eu-west-1",
            "bucket": "synthetic-lrd-target",
            "key_prefix": "lrd/01h/target",
            "expected_bucket_owner": "account-beta",
            "credential_domain_id": "credential-beta",
            "policy_source_arn": "arn:aws:iam::acct-b:role/escrow-b",
        },
    }


def test_operator_config_is_strict_and_secret_fields_are_rejected(tmp_path: Path) -> None:
    raw = _operator_config()
    source = cast(dict[str, object], raw["source"])
    source["secret_access_key"] = "must-never-be-accepted"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ProviderDrillOperatorError, match="unknown=secret_access_key"):
        load_operator_config(path)


def test_operator_config_requires_distinct_storage_profiles(tmp_path: Path) -> None:
    raw = _operator_config()
    target = cast(dict[str, object], raw["target"])
    target["aws_profile"] = "lrd-source-storage"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ProviderDrillOperatorError, match="profiles must be distinct"):
        load_operator_config(path)


def test_operator_config_accepts_secret_free_external_file(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(_operator_config()), encoding="utf-8")
    config = load_operator_config(path)
    assert config.source.provider_profile.region == "eu-central-1"
    assert config.target.provider_profile.region == "eu-west-1"


def test_replication_receipt_parser_remains_existing_01g_authority() -> None:
    capture = _capture()
    parsed = MultiLocationReplicationReceiptV1.from_dict(
        capture.replication_receipt.canonical_dict()
    )
    assert parsed == capture.replication_receipt
