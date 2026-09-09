from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from core.artifact_escrow_v1 import (
    ArtifactEscrowError,
    ArtifactEscrowManifestV1,
    EscrowArtifactBindingV1,
    EscrowBlobIdentityV1,
    EscrowLimitsV1,
)
from core.case_ledger.contracts import ContentAddress
from core.durable_escrow_v1 import (
    CapabilityEvidenceStateV1,
    DurabilityCapabilityEvidenceV1,
    DurabilityCapabilityV1,
    DurableEscrowLocationV1,
    RestoreConformanceStateV1,
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
from core.provider_durable_storage_v1 import (
    AwsLegalHoldStateV1,
    AwsRetentionModeV1,
    AwsS3ObjectLockEscrowBackendV1,
    AwsS3ObjectLockProfileV1,
    AwsS3ObjectVersionIdentityV1,
    ProviderDurablePairReportV1,
    ProviderDurableStorageV1Error,
    ProviderEvidenceStateV1,
    build_provider_pair_report_v1,
    verify_credential_scope_v1,
    verify_object_lock_version_v1,
    verify_s3_location_v1,
)

CASE_ID = "CASE-LRD-01H-SYNTHETIC"
NOW = datetime(2030, 1, 2, 12, 0, tzinfo=UTC)


class _Body:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.closed = False

    def read(self, amt: int | None = None) -> bytes:
        if self.closed:
            raise RuntimeError("body is closed")
        if amt is None:
            return self.data
        return self.data[:amt]

    def close(self) -> None:
        self.closed = True


class _FakeS3:
    retain_until: datetime | None

    def __init__(
        self,
        *,
        bucket: str,
        owner: str,
        region: str,
        retention_mode: str | None = "COMPLIANCE",
        retain_until: datetime | None = None,
        legal_hold: str = "OFF",
        object_lock_enabled: bool = True,
    ) -> None:
        self.bucket = bucket
        self.owner = owner
        self.region = region
        self.retention_mode = retention_mode
        self.retain_until = retain_until or NOW + timedelta(days=365)
        self.legal_hold = legal_hold
        self.object_lock_enabled = object_lock_enabled
        self._next_version = 1
        self.objects: dict[tuple[str, str], bytes] = {}
        self.fail_reads = False

    def _owner(self, kwargs: dict[str, object]) -> None:
        if kwargs.get("ExpectedBucketOwner") != self.owner:
            raise PermissionError("wrong bucket owner")
        if kwargs.get("Bucket") != self.bucket:
            raise FileNotFoundError("wrong bucket")

    def _response(self, request_id: str) -> dict[str, object]:
        return {"ResponseMetadata": {"RequestId": request_id}}

    def put_object(self, **kwargs: object) -> dict[str, object]:
        raw = dict(kwargs)
        self._owner(raw)
        body = raw.get("Body")
        key = raw.get("Key")
        if not isinstance(body, bytes) or not isinstance(key, str):
            raise TypeError("malformed put")
        version = f"v-{self._next_version}"
        self._next_version += 1
        self.objects[(key, version)] = body
        return {**self._response("put"), "VersionId": version}

    def get_object(self, **kwargs: object) -> dict[str, object]:
        raw = dict(kwargs)
        self._owner(raw)
        if self.fail_reads:
            raise FileNotFoundError("source unavailable")
        key = raw.get("Key")
        version = raw.get("VersionId")
        if not isinstance(key, str) or not isinstance(version, str):
            raise TypeError("malformed get")
        data = self.objects[(key, version)]
        return {
            **self._response("get"),
            "VersionId": version,
            "Body": _Body(data),
        }

    def get_bucket_location(self, **kwargs: object) -> dict[str, object]:
        raw = dict(kwargs)
        self._owner(raw)
        value: str | None = None if self.region == "us-east-1" else self.region
        return {**self._response("region"), "LocationConstraint": value}

    def get_object_lock_configuration(self, **kwargs: object) -> dict[str, object]:
        raw = dict(kwargs)
        self._owner(raw)
        enabled = "Enabled" if self.object_lock_enabled else "Disabled"
        return {
            **self._response("lock"),
            "ObjectLockConfiguration": {"ObjectLockEnabled": enabled},
        }

    def get_object_retention(self, **kwargs: object) -> dict[str, object]:
        raw = dict(kwargs)
        self._owner(raw)
        self._require_version(raw)
        retention: dict[str, object] = {}
        if self.retention_mode is not None:
            retention["Mode"] = self.retention_mode
        if self.retain_until is not None:
            retention["RetainUntilDate"] = self.retain_until
        return {**self._response("retention"), "Retention": retention}

    def get_object_legal_hold(self, **kwargs: object) -> dict[str, object]:
        raw = dict(kwargs)
        self._owner(raw)
        self._require_version(raw)
        return {
            **self._response("hold"),
            "LegalHold": {"Status": self.legal_hold},
        }

    def _require_version(self, kwargs: dict[str, object]) -> None:
        key = kwargs.get("Key")
        version = kwargs.get("VersionId")
        if not isinstance(key, str) or not isinstance(version, str):
            raise TypeError("missing exact version")
        if (key, version) not in self.objects:
            raise FileNotFoundError("missing exact version")


class _FakeSts:
    def __init__(self, *, account: str, arn: str) -> None:
        self.account = account
        self.arn = arn

    def get_caller_identity(self, **kwargs: object) -> dict[str, object]:
        assert not kwargs
        return {
            "Account": self.account,
            "Arn": self.arn,
            "ResponseMetadata": {"RequestId": "sts"},
        }


class _FakeIam:
    def __init__(self, *, overreach: set[str] | None = None) -> None:
        self.overreach = overreach or set()

    def simulate_principal_policy(self, **kwargs: object) -> dict[str, object]:
        raw = dict(kwargs)
        actions = raw.get("ActionNames")
        if not isinstance(actions, list):
            raise TypeError("ActionNames must be a list")
        evaluations: list[dict[str, object]] = []
        required = {
            "s3:GetBucketLocation",
            "s3:GetBucketObjectLockConfiguration",
            "s3:GetObjectLegalHold",
            "s3:GetObjectRetention",
            "s3:GetObjectVersion",
            "s3:PutObject",
        }
        for action in actions:
            assert isinstance(action, str)
            decision = (
                "allowed"
                if action in required or action in self.overreach
                else "implicitDeny"
            )
            evaluations.append(
                {"EvalActionName": action, "EvalDecision": decision}
            )
        return {"EvaluationResults": evaluations}


def _profile(
    name: str,
    *,
    region: str,
    owner: str,
    credential_domain: str,
    policy_source_arn: str | None = None,
) -> AwsS3ObjectLockProfileV1:
    return AwsS3ObjectLockProfileV1(
        region=region,
        bucket=f"synthetic-{name}",
        key_prefix=f"escrow/{name}",
        expected_bucket_owner=owner,
        credential_domain_id=credential_domain,
        policy_source_arn=policy_source_arn,
    )


def _engineering_capabilities() -> tuple[DurabilityCapabilityEvidenceV1, ...]:
    result: list[DurabilityCapabilityEvidenceV1] = []
    engineering = {
        DurabilityCapabilityV1.EXACT_BYTE_VERIFICATION,
        DurabilityCapabilityV1.IMMUTABLE_PUBLICATION,
    }
    for capability in DurabilityCapabilityV1:
        if capability in engineering:
            result.append(
                DurabilityCapabilityEvidenceV1(
                    capability=capability,
                    state=CapabilityEvidenceStateV1.VERIFIED,
                    evidence_digest=content_digest({"synthetic": capability.value}),
                )
            )
        else:
            result.append(
                DurabilityCapabilityEvidenceV1(
                    capability=capability,
                    state=CapabilityEvidenceStateV1.UNVERIFIED,
                )
            )
    return tuple(result)


def _location(profile: AwsS3ObjectLockProfileV1, name: str) -> DurableEscrowLocationV1:
    return DurableEscrowLocationV1.build(
        storage_profile=profile.storage_profile(),
        location_id=f"location-{name}",
        failure_domain_id=f"failure-{name}",
        credential_domain_id=profile.credential_domain_id,
        capabilities=_engineering_capabilities(),
    )


def _logical_identity(role: ReplayArtifactRole) -> ContentAddress:
    return ContentAddress.for_value({"synthetic-role": role.value})


def _manifest() -> tuple[ArtifactEscrowManifestV1, dict[ReplayArtifactRole, bytes]]:
    artifacts = tuple(
        ReplayArtifactBindingV1(
            role=role,
            identity=_logical_identity(role),
            preservation=ReplayPreservationStatus.PRESERVED,
        )
        for role in ReplayArtifactRole
    )
    long_range = LongRangeReplayManifestV1.build(
        case_id=CASE_ID,
        case_replay_manifest_identity=ContentAddress.for_value({"case-replay": CASE_ID}),
        coverage_matrix_identity=ContentAddress.for_value({"coverage": "synthetic"}),
        code_commit_sha="a" * 40,
        code_tree_sha="b" * 40,
        artifacts=artifacts,
        semantic_result_identity=_logical_identity(ReplayArtifactRole.SEMANTIC_RESULT),
        presentation_identity=None,
    )
    data_by_role = {
        role: f"provider-durable::{role.value}".encode() for role in ReplayArtifactRole
    }
    bindings = tuple(
        EscrowArtifactBindingV1.build(
            role=role,
            logical_identity=_logical_identity(role),
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


def _materialize(
    backend: AwsS3ObjectLockEscrowBackendV1,
    escrow: ArtifactEscrowManifestV1,
    data_by_role: dict[ReplayArtifactRole, bytes],
) -> None:
    limits = EscrowLimitsV1()
    for binding in escrow.bindings:
        assert backend.publish(data_by_role[binding.role], limits=limits) == binding.blob


def test_profile_is_secret_free_content_addressed_and_backend_neutral() -> None:
    profile = _profile(
        "a",
        region="eu-central-1",
        owner="account-alpha",
        credential_domain="credential-alpha",
    )

    storage = profile.storage_profile()
    assert storage.backend_kind == "aws-s3-object-lock-v1"
    assert profile.profile_digest == content_digest(profile.canonical_body())
    assert "secret" not in str(profile.canonical_dict()).lower()


def test_backend_requires_exact_version_and_verified_sha256_reread() -> None:
    profile = _profile(
        "a",
        region="eu-central-1",
        owner="account-alpha",
        credential_domain="credential-alpha",
    )
    s3 = _FakeS3(bucket=profile.bucket, owner="account-alpha", region=profile.region)
    backend = AwsS3ObjectLockEscrowBackendV1(s3_client=s3, profile=profile)
    limits = EscrowLimitsV1()
    data = b"exact-provider-bytes"
    identity = backend.publish(data, limits=limits)

    version = backend.version_identity(identity)
    assert version.version_id == "v-1"
    assert backend.read(identity, limits=limits) == data
    assert AwsS3ObjectVersionIdentityV1.from_dict(version.canonical_dict()) == version


def test_backend_rejects_stale_or_missing_version() -> None:
    profile = _profile(
        "a",
        region="eu-central-1",
        owner="account-alpha",
        credential_domain="credential-alpha",
    )
    s3 = _FakeS3(bucket=profile.bucket, owner="account-alpha", region=profile.region)
    limits = EscrowLimitsV1()
    identity = EscrowBlobIdentityV1.for_bytes(b"bytes")
    backend = AwsS3ObjectLockEscrowBackendV1(s3_client=s3, profile=profile)

    with pytest.raises(ArtifactEscrowError, match="VersionId"):
        backend.read(identity, limits=limits)

    wrong = AwsS3ObjectVersionIdentityV1(
        profile_digest=profile.profile_digest,
        bucket=profile.bucket,
        key=profile.object_key(identity),
        version_id="stale-version",
        blob_digest=identity.digest,
        blob_size=identity.size,
    )
    rebound = AwsS3ObjectLockEscrowBackendV1(
        s3_client=s3,
        profile=profile,
        version_bindings=(wrong,),
    )
    with pytest.raises(ArtifactEscrowError, match="read failed"):
        rebound.read(identity, limits=limits)


def test_version_binding_rejects_wrong_bucket_and_profile() -> None:
    profile = _profile(
        "a",
        region="eu-central-1",
        owner="account-alpha",
        credential_domain="credential-alpha",
    )
    s3 = _FakeS3(bucket=profile.bucket, owner="account-alpha", region=profile.region)
    identity = EscrowBlobIdentityV1.for_bytes(b"bytes")
    wrong = AwsS3ObjectVersionIdentityV1(
        profile_digest=profile.profile_digest,
        bucket="different-bucket",
        key=profile.object_key(identity),
        version_id="v-x",
        blob_digest=identity.digest,
        blob_size=identity.size,
    )

    with pytest.raises(ProviderDurableStorageV1Error, match="different bucket"):
        AwsS3ObjectLockEscrowBackendV1(
            s3_client=s3,
            profile=profile,
            version_bindings=(wrong,),
        )


def test_active_compliance_retention_is_provider_verified() -> None:
    profile = _profile(
        "a",
        region="eu-central-1",
        owner="account-alpha",
        credential_domain="credential-alpha",
    )
    s3 = _FakeS3(bucket=profile.bucket, owner="account-alpha", region=profile.region)
    sts = _FakeSts(account="account-alpha", arn="arn:aws:iam::acct:role/escrow-a")
    backend = AwsS3ObjectLockEscrowBackendV1(s3_client=s3, profile=profile)
    identity = backend.publish(b"bytes", limits=EscrowLimitsV1())

    evidence = verify_object_lock_version_v1(
        s3_client=s3,
        sts_client=sts,
        profile=profile,
        version=backend.version_identity(identity),
        observed_at=NOW,
    )

    assert evidence.state is ProviderEvidenceStateV1.VERIFIED
    assert evidence.retention_mode is AwsRetentionModeV1.COMPLIANCE
    assert evidence.legal_hold is AwsLegalHoldStateV1.OFF


def test_governance_mode_never_promotes_to_worm_verified() -> None:
    profile = _profile(
        "a",
        region="eu-central-1",
        owner="account-alpha",
        credential_domain="credential-alpha",
    )
    s3 = _FakeS3(
        bucket=profile.bucket,
        owner="account-alpha",
        region=profile.region,
        retention_mode="GOVERNANCE",
    )
    sts = _FakeSts(account="account-alpha", arn="arn:aws:iam::acct:role/escrow-a")
    backend = AwsS3ObjectLockEscrowBackendV1(s3_client=s3, profile=profile)
    identity = backend.publish(b"bytes", limits=EscrowLimitsV1())

    evidence = verify_object_lock_version_v1(
        s3_client=s3,
        sts_client=sts,
        profile=profile,
        version=backend.version_identity(identity),
        observed_at=NOW,
    )

    assert evidence.state is ProviderEvidenceStateV1.FAIL
    assert "governance_retention_not_worm" in evidence.violations


@pytest.mark.parametrize(
    ("mode", "retain_until", "expected"),
    [
        (None, None, "missing_retention"),
        ("COMPLIANCE", NOW - timedelta(seconds=1), "expired_retention"),
    ],
)
def test_missing_or_expired_retention_fails_closed(
    mode: str | None,
    retain_until: datetime | None,
    expected: str,
) -> None:
    profile = _profile(
        "a",
        region="eu-central-1",
        owner="account-alpha",
        credential_domain="credential-alpha",
    )
    s3 = _FakeS3(
        bucket=profile.bucket,
        owner="account-alpha",
        region=profile.region,
        retention_mode=mode,
        retain_until=retain_until,
    )
    if mode is None:
        s3.retain_until = None
    sts = _FakeSts(account="account-alpha", arn="arn:aws:iam::acct:role/escrow-a")
    backend = AwsS3ObjectLockEscrowBackendV1(s3_client=s3, profile=profile)
    identity = backend.publish(b"bytes", limits=EscrowLimitsV1())

    evidence = verify_object_lock_version_v1(
        s3_client=s3,
        sts_client=sts,
        profile=profile,
        version=backend.version_identity(identity),
        observed_at=NOW,
    )

    assert evidence.state is ProviderEvidenceStateV1.FAIL
    assert expected in evidence.violations


def test_wrong_bucket_owner_fails_at_provider_boundary() -> None:
    profile = _profile(
        "a",
        region="eu-central-1",
        owner="wrong-owner",
        credential_domain="credential-alpha",
    )
    s3 = _FakeS3(bucket=profile.bucket, owner="actual-owner", region=profile.region)
    backend = AwsS3ObjectLockEscrowBackendV1(s3_client=s3, profile=profile)

    with pytest.raises(ArtifactEscrowError, match="publication failed"):
        backend.publish(b"bytes", limits=EscrowLimitsV1())


def test_credential_scope_requires_denial_of_destructive_actions() -> None:
    profile = _profile(
        "a",
        region="eu-central-1",
        owner="account-alpha",
        credential_domain="credential-alpha",
        policy_source_arn="arn:aws:iam::acct:role/escrow-a",
    )

    verified = verify_credential_scope_v1(iam_client=_FakeIam(), profile=profile)
    assert verified.state is ProviderEvidenceStateV1.VERIFIED

    overreach = verify_credential_scope_v1(
        iam_client=_FakeIam(overreach={"s3:BypassGovernanceRetention"}),
        profile=profile,
    )
    assert overreach.state is ProviderEvidenceStateV1.FAIL
    assert "credential_overreach:s3:BypassGovernanceRetention" in overreach.violations


def test_missing_policy_simulator_is_unverified_not_implicit_pass() -> None:
    profile = _profile(
        "a",
        region="eu-central-1",
        owner="account-alpha",
        credential_domain="credential-alpha",
    )

    result = verify_credential_scope_v1(iam_client=None, profile=profile)

    assert result.state is ProviderEvidenceStateV1.UNVERIFIED
    assert result.violations == ("iam_policy_simulation_unavailable",)


def test_whole_location_and_pair_require_exact_provider_evidence() -> None:
    escrow, data_by_role = _manifest()
    source_profile = _profile(
        "a",
        region="eu-central-1",
        owner="account-alpha",
        credential_domain="credential-alpha",
        policy_source_arn="arn:aws:iam::acct:role/escrow-a",
    )
    target_profile = _profile(
        "b",
        region="eu-west-1",
        owner="account-beta",
        credential_domain="credential-beta",
        policy_source_arn="arn:aws:iam::acct:role/escrow-b",
    )
    source_s3 = _FakeS3(
        bucket=source_profile.bucket,
        owner="account-alpha",
        region=source_profile.region,
    )
    target_s3 = _FakeS3(
        bucket=target_profile.bucket,
        owner="account-beta",
        region=target_profile.region,
    )
    source = AwsS3ObjectLockEscrowBackendV1(
        s3_client=source_s3,
        profile=source_profile,
    )
    target = AwsS3ObjectLockEscrowBackendV1(
        s3_client=target_s3,
        profile=target_profile,
    )
    _materialize(source, escrow, data_by_role)
    _materialize(target, escrow, data_by_role)
    source_location = _location(source_profile, "a")
    target_location = _location(target_profile, "b")

    source_evidence, source_scope = verify_s3_location_v1(
        expected_case_id=CASE_ID,
        escrow_manifest=escrow,
        generic_location=source_location,
        backend=source,
        s3_client=source_s3,
        sts_client=_FakeSts(
            account="account-alpha",
            arn="arn:aws:iam::acct:role/escrow-a",
        ),
        iam_client=_FakeIam(),
        observed_at=NOW,
        limits=EscrowLimitsV1(),
    )
    target_evidence, target_scope = verify_s3_location_v1(
        expected_case_id=CASE_ID,
        escrow_manifest=escrow,
        generic_location=target_location,
        backend=target,
        s3_client=target_s3,
        sts_client=_FakeSts(
            account="account-beta",
            arn="arn:aws:iam::acct:role/escrow-b",
        ),
        iam_client=_FakeIam(),
        observed_at=NOW,
        limits=EscrowLimitsV1(),
    )

    assert source_scope.state is ProviderEvidenceStateV1.VERIFIED
    assert target_scope.state is ProviderEvidenceStateV1.VERIFIED
    assert source_evidence.state is ProviderEvidenceStateV1.VERIFIED
    assert target_evidence.state is ProviderEvidenceStateV1.VERIFIED
    report = build_provider_pair_report_v1(
        source_location=source_location,
        target_location=target_location,
        source_evidence=source_evidence,
        target_evidence=target_evidence,
    )
    assert report.state is ProviderEvidenceStateV1.VERIFIED
    assert report.distinct_regions is True
    assert report.distinct_principals is True
    assert report.ten_year_durability_claim is False


def test_pair_rejects_region_principal_and_credential_collisions() -> None:
    escrow, data_by_role = _manifest()
    profile_a = _profile(
        "a",
        region="eu-central-1",
        owner="account-alpha",
        credential_domain="same-credential",
        policy_source_arn="arn:aws:iam::acct:role/shared",
    )
    profile_b = _profile(
        "b",
        region="eu-central-1",
        owner="account-alpha",
        credential_domain="same-credential",
        policy_source_arn="arn:aws:iam::acct:role/shared",
    )
    s3_a = _FakeS3(bucket=profile_a.bucket, owner="account-alpha", region=profile_a.region)
    s3_b = _FakeS3(bucket=profile_b.bucket, owner="account-alpha", region=profile_b.region)
    backend_a = AwsS3ObjectLockEscrowBackendV1(s3_client=s3_a, profile=profile_a)
    backend_b = AwsS3ObjectLockEscrowBackendV1(s3_client=s3_b, profile=profile_b)
    _materialize(backend_a, escrow, data_by_role)
    _materialize(backend_b, escrow, data_by_role)
    location_a = _location(profile_a, "a")
    location_b = _location(profile_b, "b")
    sts = _FakeSts(account="account-alpha", arn="arn:aws:iam::acct:role/shared")
    evidence_a, _ = verify_s3_location_v1(
        expected_case_id=CASE_ID,
        escrow_manifest=escrow,
        generic_location=location_a,
        backend=backend_a,
        s3_client=s3_a,
        sts_client=sts,
        iam_client=_FakeIam(),
        observed_at=NOW,
        limits=EscrowLimitsV1(),
    )
    evidence_b, _ = verify_s3_location_v1(
        expected_case_id=CASE_ID,
        escrow_manifest=escrow,
        generic_location=location_b,
        backend=backend_b,
        s3_client=s3_b,
        sts_client=sts,
        iam_client=_FakeIam(),
        observed_at=NOW,
        limits=EscrowLimitsV1(),
    )

    report = build_provider_pair_report_v1(
        source_location=location_a,
        target_location=location_b,
        source_evidence=evidence_a,
        target_evidence=evidence_b,
    )

    assert report.state is ProviderEvidenceStateV1.FAIL
    assert set(report.violations) == {
        "credential_domain_collision",
        "provider_principal_collision",
        "provider_region_collision",
    }


def test_replication_and_target_restore_survive_source_loss() -> None:
    escrow, data_by_role = _manifest()
    source_profile = _profile(
        "a",
        region="eu-central-1",
        owner="account-alpha",
        credential_domain="credential-alpha",
    )
    target_profile = _profile(
        "b",
        region="eu-west-1",
        owner="account-beta",
        credential_domain="credential-beta",
    )
    source_s3 = _FakeS3(
        bucket=source_profile.bucket,
        owner="account-alpha",
        region=source_profile.region,
    )
    target_s3 = _FakeS3(
        bucket=target_profile.bucket,
        owner="account-beta",
        region=target_profile.region,
    )
    source = AwsS3ObjectLockEscrowBackendV1(
        s3_client=source_s3,
        profile=source_profile,
    )
    target = AwsS3ObjectLockEscrowBackendV1(
        s3_client=target_s3,
        profile=target_profile,
    )
    _materialize(source, escrow, data_by_role)
    source_location = _location(source_profile, "a")
    target_location = _location(target_profile, "b")
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
        source_backend=source,
        target_backend=target,
        limits=EscrowLimitsV1(),
    )
    assert receipt.replicated_blob_count == len(escrow.bindings)

    source_s3.fail_reads = True
    with pytest.raises(ArtifactEscrowError):
        source.read(escrow.bindings[0].blob, limits=EscrowLimitsV1())

    target_restore = verify_location_restore_v1(
        expected_case_id=CASE_ID,
        escrow_manifest=escrow,
        location=target_location,
        backend=target,
        limits=EscrowLimitsV1(),
    )
    assert target_restore.state is RestoreConformanceStateV1.PASS


def test_missing_target_object_fails_restore() -> None:
    escrow, data_by_role = _manifest()
    profile = _profile(
        "a",
        region="eu-central-1",
        owner="account-alpha",
        credential_domain="credential-alpha",
    )
    s3 = _FakeS3(bucket=profile.bucket, owner="account-alpha", region=profile.region)
    backend = AwsS3ObjectLockEscrowBackendV1(s3_client=s3, profile=profile)
    _materialize(backend, escrow, data_by_role)
    first = backend.version_identity(escrow.bindings[0].blob)
    del s3.objects[(first.key, first.version_id)]

    report = verify_location_restore_v1(
        expected_case_id=CASE_ID,
        escrow_manifest=escrow,
        location=_location(profile, "a"),
        backend=backend,
        limits=EscrowLimitsV1(),
    )

    assert report.state is RestoreConformanceStateV1.FAIL


def test_ten_year_claim_is_structurally_rejected() -> None:
    digest = content_digest({"synthetic": "evidence"})
    with pytest.raises(ProviderDurableStorageV1Error, match="ten-year SLA"):
        ProviderDurablePairReportV1(
            source_evidence_digest=digest,
            target_evidence_digest=content_digest({"synthetic": "target"}),
            source_location_digest=content_digest({"location": "source"}),
            target_location_digest=content_digest({"location": "target"}),
            distinct_regions=True,
            distinct_principals=True,
            distinct_credential_domains=True,
            state=ProviderEvidenceStateV1.VERIFIED,
            violations=(),
            ten_year_durability_claim=True,
        )


def test_unknown_fields_and_digest_tampering_fail_closed() -> None:
    profile = _profile(
        "a",
        region="eu-central-1",
        owner="account-alpha",
        credential_domain="credential-alpha",
    )
    s3 = _FakeS3(bucket=profile.bucket, owner="account-alpha", region=profile.region)
    backend = AwsS3ObjectLockEscrowBackendV1(s3_client=s3, profile=profile)
    identity = backend.publish(b"bytes", limits=EscrowLimitsV1())
    version = backend.version_identity(identity)
    raw = cast(dict[str, object], version.canonical_dict())
    raw["unknown"] = True
    with pytest.raises(ProviderDurableStorageV1Error, match="unknown=unknown"):
        AwsS3ObjectVersionIdentityV1.from_dict(raw)

    tampered = version.canonical_dict()
    tampered["version_digest"] = "0" * 64
    with pytest.raises(ProviderDurableStorageV1Error, match="digest mismatch"):
        AwsS3ObjectVersionIdentityV1.from_dict(tampered)
