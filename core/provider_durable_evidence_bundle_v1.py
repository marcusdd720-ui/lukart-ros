"""LRD-01H closure-grade provider evidence preservation and offline verification.

This module hardens the provider-verification last mile without creating a new
storage, Product, CCL, Gold, trust, release, or certification authority. It
serializes only secret-free evidence already produced by LRD-01C/01G/01H and
rejects identity/provenance ambiguity on reload.

A valid bundle proves internal consistency of captured provider responses. It
does not prove that serialized bytes originated at AWS, does not validate the
semantics of opaque source-unavailability evidence, and is never by itself an
external durability or ten-year certification.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from core.artifact_escrow_v1 import ArtifactEscrowManifestV1
from core.durable_escrow_v1 import (
    DurableEscrowLocationV1,
    LocationRestoreReportV1,
    MultiLocationEscrowPlanV1,
    MultiLocationReplicationReceiptV1,
    RestoreConformanceStateV1,
)
from core.p3.contracts import content_digest, require_hex_digest
from core.provider_durable_storage_v1 import (
    AWS_CREDENTIAL_SCOPE_SCHEMA_V1,
    AWS_LOCATION_EVIDENCE_SCHEMA_V1,
    AWS_OBJECT_LOCK_EVIDENCE_SCHEMA_V1,
    AWS_S3_PROFILE_SCHEMA_V1,
    PROVIDER_PAIR_REPORT_SCHEMA_V1,
    AwsCredentialScopeEvidenceV1,
    AwsLegalHoldStateV1,
    AwsLocationProviderEvidenceV1,
    AwsObjectLockEvidenceV1,
    AwsRetentionModeV1,
    AwsS3ObjectLockProfileV1,
    AwsS3ObjectVersionIdentityV1,
    ProviderDurablePairReportV1,
    ProviderEvidenceStateV1,
)

PROVIDER_EVIDENCE_CAPTURE_SCHEMA_V1 = "lukart.provider-durable-evidence-capture.v1"
PROVIDER_SOURCE_LOSS_DRILL_SCHEMA_V1 = "lukart.provider-source-loss-drill-evidence.v1"
PROVIDER_EVIDENCE_AUTHORITY_V1 = "captured-provider-evidence-not-closure-authority"
SOURCE_UNAVAILABILITY_EVIDENCE_KIND_V1 = "opaque-external-evidence-digest"
SYNTHETIC_PROVIDER_DRILL_CASE_ID_V1 = "CASE-LRD-01H-SYNTHETIC-PROVIDER-DRILL"

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ProviderDurableEvidenceBundleV1Error(ValueError):
    """Fail-closed LRD-01H evidence preservation/verification violation."""


class ProviderDrillEvidenceStatusV1(StrEnum):
    CAPTURED_NOT_CLOSURE_AUTHORITY = "CAPTURED_NOT_CLOSURE_AUTHORITY"


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProviderDurableEvidenceBundleV1Error(
            f"{field_name} must be nonblank and already canonical"
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ProviderDurableEvidenceBundleV1Error(
            f"{field_name} cannot contain control characters"
        )
    return value


def _digest(value: object, *, field_name: str) -> str:
    try:
        return require_hex_digest(
            _text(value, field_name=field_name), field_name=field_name
        )
    except ValueError as exc:
        raise ProviderDurableEvidenceBundleV1Error(str(exc)) from exc


def _sha(value: object, *, field_name: str) -> str:
    result = _text(value, field_name=field_name)
    if _SHA_RE.fullmatch(result) is None:
        raise ProviderDurableEvidenceBundleV1Error(
            f"{field_name} must be an exact lowercase 40-character Git SHA"
        )
    return result


def _strict_keys(
    value: Mapping[str, object],
    *,
    expected: frozenset[str],
    field_name: str,
) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = ",".join(sorted(expected - actual)) or "-"
    unknown = ",".join(sorted(actual - expected)) or "-"
    raise ProviderDurableEvidenceBundleV1Error(
        f"{field_name} key contract violation: missing={missing}; unknown={unknown}"
    )


def _mapping(value: object, *, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ProviderDurableEvidenceBundleV1Error(f"{field_name} must be an object")
    return cast(Mapping[str, object], value)


def _mapping_list(value: object, *, field_name: str) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        raise ProviderDurableEvidenceBundleV1Error(f"{field_name} must be a list")
    return [_mapping(item, field_name=f"{field_name} item") for item in value]


def _string_tuple(value: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ProviderDurableEvidenceBundleV1Error(f"{field_name} must be a list")
    return tuple(_text(item, field_name=f"{field_name} item") for item in value)


def _bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ProviderDurableEvidenceBundleV1Error(f"{field_name} must be boolean")
    return value


def _policy_source_matches_sts_principal_v1(
    *,
    policy_source_arn: str,
    sts_principal_arn: str,
) -> bool:
    """Bind IAM simulation to the same caller, including an AssumeRole session.

    AWS STS reports an assumed role as
    ``arn:<partition>:sts::<account>:assumed-role/<role-name>/<session>`` while
    IAM policy simulation addresses the backing role as
    ``arn:<partition>:iam::<account>:role/<optional-path>/<role-name>``.
    Exact equality remains valid for direct principals. The assumed-role mapping
    accepts only the same partition, account and terminal role name.
    """

    if policy_source_arn == sts_principal_arn:
        return True
    policy = policy_source_arn.split(":", 5)
    caller = sts_principal_arn.split(":", 5)
    if len(policy) != 6 or len(caller) != 6:
        return False
    if policy[0] != "arn" or caller[0] != "arn":
        return False
    if policy[1] != caller[1] or policy[4] != caller[4]:
        return False
    if policy[2] != "iam" or caller[2] != "sts":
        return False
    if policy[3] or caller[3]:
        return False
    if not policy[5].startswith("role/"):
        return False
    if not caller[5].startswith("assumed-role/"):
        return False
    policy_segments = policy[5].split("/")
    caller_segments = caller[5].split("/")
    if len(policy_segments) < 2 or len(caller_segments) != 3:
        return False
    role_name = policy_segments[-1]
    assumed_role_name = caller_segments[1]
    session_name = caller_segments[2]
    return bool(role_name and session_name and role_name == assumed_role_name)


def parse_aws_s3_profile_v1(value: Mapping[str, object]) -> AwsS3ObjectLockProfileV1:
    """Strictly deserialize one secret-free AWS S3 Object Lock profile."""

    _strict_keys(
        value,
        expected=frozenset(
            {
                "schema",
                "region",
                "bucket",
                "key_prefix",
                "expected_bucket_owner",
                "credential_domain_id",
                "policy_source_arn",
                "profile_digest",
            }
        ),
        field_name="AWS S3 Object Lock profile",
    )
    policy_source = value.get("policy_source_arn")
    if policy_source is not None:
        policy_source = _text(policy_source, field_name="policy_source_arn")
    result = AwsS3ObjectLockProfileV1(
        schema=_text(value.get("schema"), field_name="schema"),
        region=_text(value.get("region"), field_name="region"),
        bucket=_text(value.get("bucket"), field_name="bucket"),
        key_prefix=_text(value.get("key_prefix"), field_name="key_prefix"),
        expected_bucket_owner=_text(
            value.get("expected_bucket_owner"), field_name="expected_bucket_owner"
        ),
        credential_domain_id=_text(
            value.get("credential_domain_id"), field_name="credential_domain_id"
        ),
        policy_source_arn=cast(str | None, policy_source),
    )
    if result.schema != AWS_S3_PROFILE_SCHEMA_V1:
        raise ProviderDurableEvidenceBundleV1Error("unsupported AWS S3 profile schema")
    if (
        _digest(value.get("profile_digest"), field_name="profile_digest")
        != result.profile_digest
    ):
        raise ProviderDurableEvidenceBundleV1Error("AWS S3 profile digest mismatch")
    return result


def parse_credential_scope_evidence_v1(
    value: Mapping[str, object],
) -> AwsCredentialScopeEvidenceV1:
    """Strictly deserialize least-privilege IAM simulation evidence."""

    _strict_keys(
        value,
        expected=frozenset(
            {
                "schema",
                "policy_source_arn",
                "required_allowed",
                "forbidden_denied",
                "state",
                "violations",
                "evidence_digest",
            }
        ),
        field_name="AWS credential-scope evidence",
    )
    try:
        state = ProviderEvidenceStateV1(_text(value.get("state"), field_name="state"))
    except ValueError as exc:
        raise ProviderDurableEvidenceBundleV1Error(
            "unknown provider evidence state"
        ) from exc
    result = AwsCredentialScopeEvidenceV1(
        schema=_text(value.get("schema"), field_name="schema"),
        policy_source_arn=_text(
            value.get("policy_source_arn"), field_name="policy_source_arn"
        ),
        required_allowed=_string_tuple(
            value.get("required_allowed"), field_name="required_allowed"
        ),
        forbidden_denied=_string_tuple(
            value.get("forbidden_denied"), field_name="forbidden_denied"
        ),
        state=state,
        violations=_string_tuple(value.get("violations"), field_name="violations"),
    )
    if result.schema != AWS_CREDENTIAL_SCOPE_SCHEMA_V1:
        raise ProviderDurableEvidenceBundleV1Error(
            "unsupported AWS credential-scope evidence schema"
        )
    if (
        _digest(value.get("evidence_digest"), field_name="evidence_digest")
        != result.evidence_digest
    ):
        raise ProviderDurableEvidenceBundleV1Error(
            "AWS credential-scope evidence digest mismatch"
        )
    return result


def parse_object_lock_evidence_v1(
    value: Mapping[str, object],
) -> AwsObjectLockEvidenceV1:
    """Strictly deserialize one exact-version Object Lock observation."""

    _strict_keys(
        value,
        expected=frozenset(
            {
                "schema",
                "version_digest",
                "observed_region",
                "principal_account",
                "principal_arn",
                "object_lock_enabled",
                "retention_mode",
                "retain_until_utc",
                "legal_hold",
                "state",
                "violations",
                "provider_request_ids",
                "evidence_digest",
            }
        ),
        field_name="AWS Object Lock evidence",
    )
    raw_mode = value.get("retention_mode")
    mode: AwsRetentionModeV1 | None = None
    if raw_mode is not None:
        try:
            mode = AwsRetentionModeV1(_text(raw_mode, field_name="retention_mode"))
        except ValueError as exc:
            raise ProviderDurableEvidenceBundleV1Error(
                "unknown Object Lock retention mode"
            ) from exc
    try:
        hold = AwsLegalHoldStateV1(
            _text(value.get("legal_hold"), field_name="legal_hold")
        )
        state = ProviderEvidenceStateV1(_text(value.get("state"), field_name="state"))
    except ValueError as exc:
        raise ProviderDurableEvidenceBundleV1Error(
            "unknown Object Lock evidence enum"
        ) from exc
    retain_until = value.get("retain_until_utc")
    if retain_until is not None:
        retain_until = _text(retain_until, field_name="retain_until_utc")
    result = AwsObjectLockEvidenceV1(
        schema=_text(value.get("schema"), field_name="schema"),
        version_digest=_digest(value.get("version_digest"), field_name="version_digest"),
        observed_region=_text(value.get("observed_region"), field_name="observed_region"),
        principal_account=_text(
            value.get("principal_account"), field_name="principal_account"
        ),
        principal_arn=_text(value.get("principal_arn"), field_name="principal_arn"),
        object_lock_enabled=_bool(
            value.get("object_lock_enabled"), field_name="object_lock_enabled"
        ),
        retention_mode=mode,
        retain_until_utc=cast(str | None, retain_until),
        legal_hold=hold,
        state=state,
        violations=_string_tuple(value.get("violations"), field_name="violations"),
        provider_request_ids=_string_tuple(
            value.get("provider_request_ids"), field_name="provider_request_ids"
        ),
    )
    if result.schema != AWS_OBJECT_LOCK_EVIDENCE_SCHEMA_V1:
        raise ProviderDurableEvidenceBundleV1Error(
            "unsupported AWS Object Lock evidence schema"
        )
    if (
        _digest(value.get("evidence_digest"), field_name="evidence_digest")
        != result.evidence_digest
    ):
        raise ProviderDurableEvidenceBundleV1Error(
            "AWS Object Lock evidence digest mismatch"
        )
    return result


def parse_location_provider_evidence_v1(
    value: Mapping[str, object],
) -> AwsLocationProviderEvidenceV1:
    """Strictly deserialize whole-location provider evidence."""

    _strict_keys(
        value,
        expected=frozenset(
            {
                "schema",
                "generic_location_digest",
                "storage_profile_digest",
                "aws_profile_digest",
                "escrow_manifest_digest",
                "principal_arn",
                "principal_account",
                "observed_region",
                "object_evidence",
                "credential_scope_digest",
                "state",
                "violations",
                "evidence_digest",
            }
        ),
        field_name="AWS location provider evidence",
    )
    try:
        state = ProviderEvidenceStateV1(_text(value.get("state"), field_name="state"))
    except ValueError as exc:
        raise ProviderDurableEvidenceBundleV1Error(
            "unknown provider evidence state"
        ) from exc
    object_evidence = tuple(
        parse_object_lock_evidence_v1(item)
        for item in _mapping_list(
            value.get("object_evidence"), field_name="object_evidence"
        )
    )
    result = AwsLocationProviderEvidenceV1(
        schema=_text(value.get("schema"), field_name="schema"),
        generic_location_digest=_digest(
            value.get("generic_location_digest"), field_name="generic_location_digest"
        ),
        storage_profile_digest=_digest(
            value.get("storage_profile_digest"), field_name="storage_profile_digest"
        ),
        aws_profile_digest=_digest(
            value.get("aws_profile_digest"), field_name="aws_profile_digest"
        ),
        escrow_manifest_digest=_digest(
            value.get("escrow_manifest_digest"), field_name="escrow_manifest_digest"
        ),
        principal_arn=_text(value.get("principal_arn"), field_name="principal_arn"),
        principal_account=_text(
            value.get("principal_account"), field_name="principal_account"
        ),
        observed_region=_text(value.get("observed_region"), field_name="observed_region"),
        object_evidence=object_evidence,
        credential_scope_digest=_digest(
            value.get("credential_scope_digest"), field_name="credential_scope_digest"
        ),
        state=state,
        violations=_string_tuple(value.get("violations"), field_name="violations"),
    )
    if result.schema != AWS_LOCATION_EVIDENCE_SCHEMA_V1:
        raise ProviderDurableEvidenceBundleV1Error(
            "unsupported AWS location evidence schema"
        )
    if (
        _digest(value.get("evidence_digest"), field_name="evidence_digest")
        != result.evidence_digest
    ):
        raise ProviderDurableEvidenceBundleV1Error(
            "AWS location provider evidence digest mismatch"
        )
    return result


def parse_provider_pair_report_v1(
    value: Mapping[str, object],
) -> ProviderDurablePairReportV1:
    """Strictly deserialize two-location provider separation evidence."""

    _strict_keys(
        value,
        expected=frozenset(
            {
                "schema",
                "source_evidence_digest",
                "target_evidence_digest",
                "source_location_digest",
                "target_location_digest",
                "distinct_regions",
                "distinct_principals",
                "distinct_credential_domains",
                "state",
                "violations",
                "ten_year_durability_claim",
                "report_digest",
            }
        ),
        field_name="provider durable pair report",
    )
    try:
        state = ProviderEvidenceStateV1(_text(value.get("state"), field_name="state"))
    except ValueError as exc:
        raise ProviderDurableEvidenceBundleV1Error(
            "unknown provider pair state"
        ) from exc
    result = ProviderDurablePairReportV1(
        schema=_text(value.get("schema"), field_name="schema"),
        source_evidence_digest=_digest(
            value.get("source_evidence_digest"), field_name="source_evidence_digest"
        ),
        target_evidence_digest=_digest(
            value.get("target_evidence_digest"), field_name="target_evidence_digest"
        ),
        source_location_digest=_digest(
            value.get("source_location_digest"), field_name="source_location_digest"
        ),
        target_location_digest=_digest(
            value.get("target_location_digest"), field_name="target_location_digest"
        ),
        distinct_regions=_bool(
            value.get("distinct_regions"), field_name="distinct_regions"
        ),
        distinct_principals=_bool(
            value.get("distinct_principals"), field_name="distinct_principals"
        ),
        distinct_credential_domains=_bool(
            value.get("distinct_credential_domains"),
            field_name="distinct_credential_domains",
        ),
        state=state,
        violations=_string_tuple(value.get("violations"), field_name="violations"),
        ten_year_durability_claim=_bool(
            value.get("ten_year_durability_claim"),
            field_name="ten_year_durability_claim",
        ),
    )
    if result.schema != PROVIDER_PAIR_REPORT_SCHEMA_V1:
        raise ProviderDurableEvidenceBundleV1Error(
            "unsupported provider pair report schema"
        )
    if (
        _digest(value.get("report_digest"), field_name="report_digest")
        != result.report_digest
    ):
        raise ProviderDurableEvidenceBundleV1Error("provider pair report digest mismatch")
    return result


def _version_map(
    versions: Sequence[AwsS3ObjectVersionIdentityV1],
    *,
    field_name: str,
) -> dict[str, AwsS3ObjectVersionIdentityV1]:
    result: dict[str, AwsS3ObjectVersionIdentityV1] = {}
    for version in versions:
        if version.blob_digest in result:
            raise ProviderDurableEvidenceBundleV1Error(
                f"{field_name} contains duplicate blob digest"
            )
        result[version.blob_digest] = version
    if not result:
        raise ProviderDurableEvidenceBundleV1Error(f"{field_name} cannot be empty")
    return result


def validate_closure_grade_location_evidence_v1(
    *,
    profile: AwsS3ObjectLockProfileV1,
    location: DurableEscrowLocationV1,
    escrow_manifest: ArtifactEscrowManifestV1,
    versions: Sequence[AwsS3ObjectVersionIdentityV1],
    credential_scope: AwsCredentialScopeEvidenceV1,
    evidence: AwsLocationProviderEvidenceV1,
) -> None:
    """Require unambiguous provider provenance for preserved closure evidence."""

    if credential_scope.state is not ProviderEvidenceStateV1.VERIFIED:
        raise ProviderDurableEvidenceBundleV1Error(
            "closure-grade credential scope must be VERIFIED"
        )
    if evidence.state is not ProviderEvidenceStateV1.VERIFIED:
        raise ProviderDurableEvidenceBundleV1Error(
            "closure-grade location provider evidence must be VERIFIED"
        )
    if not _policy_source_matches_sts_principal_v1(
        policy_source_arn=credential_scope.policy_source_arn,
        sts_principal_arn=evidence.principal_arn,
    ):
        raise ProviderDurableEvidenceBundleV1Error(
            "IAM policy evidence principal does not match STS storage principal"
        )
    storage_profile_digest = profile.storage_profile().profile_digest
    if location.storage_profile_digest != storage_profile_digest:
        raise ProviderDurableEvidenceBundleV1Error(
            "durable location/storage profile substitution"
        )
    if location.credential_domain_id != profile.credential_domain_id:
        raise ProviderDurableEvidenceBundleV1Error(
            "durable location/credential-domain substitution"
        )
    if evidence.generic_location_digest != location.location_digest:
        raise ProviderDurableEvidenceBundleV1Error(
            "provider evidence/generic location substitution"
        )
    if evidence.storage_profile_digest != storage_profile_digest:
        raise ProviderDurableEvidenceBundleV1Error(
            "provider evidence/storage profile substitution"
        )
    if evidence.aws_profile_digest != profile.profile_digest:
        raise ProviderDurableEvidenceBundleV1Error(
            "provider evidence/AWS profile substitution"
        )
    if evidence.escrow_manifest_digest != escrow_manifest.escrow_manifest_identity.digest:
        raise ProviderDurableEvidenceBundleV1Error(
            "provider evidence/escrow manifest substitution"
        )
    if evidence.credential_scope_digest != credential_scope.evidence_digest:
        raise ProviderDurableEvidenceBundleV1Error(
            "provider evidence/credential-scope substitution"
        )
    if evidence.observed_region != profile.region:
        raise ProviderDurableEvidenceBundleV1Error(
            "provider evidence/profile region substitution"
        )
    if evidence.principal_account != profile.expected_bucket_owner:
        raise ProviderDurableEvidenceBundleV1Error(
            "provider evidence/profile owner substitution"
        )

    version_by_blob = _version_map(versions, field_name="version inventory")
    expected_blobs = {
        binding.blob.digest: binding.blob for binding in escrow_manifest.bindings
    }
    if set(version_by_blob) != set(expected_blobs):
        raise ProviderDurableEvidenceBundleV1Error(
            "exact S3 version inventory does not cover escrow manifest"
        )
    for blob_digest, version in version_by_blob.items():
        blob = expected_blobs[blob_digest]
        if (
            version.profile_digest != profile.profile_digest
            or version.bucket != profile.bucket
            or version.blob_size != blob.size
            or version.key != profile.object_key(blob)
        ):
            raise ProviderDurableEvidenceBundleV1Error(
                "S3 version inventory/profile/blob substitution"
            )

    object_by_version = {
        item.version_digest: item for item in evidence.object_evidence
    }
    expected_version_digests = {item.version_digest for item in versions}
    if set(object_by_version) != expected_version_digests:
        raise ProviderDurableEvidenceBundleV1Error(
            "Object Lock evidence does not cover exact S3 version inventory"
        )
    for item in object_by_version.values():
        if item.state is not ProviderEvidenceStateV1.VERIFIED:
            raise ProviderDurableEvidenceBundleV1Error(
                "closure-grade Object Lock evidence must be VERIFIED"
            )
        if len(item.provider_request_ids) != 5 or any(
            request_id.lower() == "unavailable"
            for request_id in item.provider_request_ids
        ):
            raise ProviderDurableEvidenceBundleV1Error(
                "closure-grade provider evidence requires five exact provider request identifiers"
            )
        if (
            item.principal_arn != evidence.principal_arn
            or item.principal_account != evidence.principal_account
            or item.observed_region != evidence.observed_region
        ):
            raise ProviderDurableEvidenceBundleV1Error(
                "Object Lock evidence provider identity is inconsistent"
            )


@dataclass(frozen=True, slots=True)
class ProviderDurableEvidenceCaptureV1:
    """Secret-free pre-source-loss provider capture bound to exact code and bytes."""

    code_sha: str
    case_id: str
    escrow_manifest: ArtifactEscrowManifestV1
    source_profile: AwsS3ObjectLockProfileV1
    target_profile: AwsS3ObjectLockProfileV1
    source_location: DurableEscrowLocationV1
    target_location: DurableEscrowLocationV1
    source_versions: tuple[AwsS3ObjectVersionIdentityV1, ...]
    target_versions: tuple[AwsS3ObjectVersionIdentityV1, ...]
    source_credential_scope: AwsCredentialScopeEvidenceV1
    target_credential_scope: AwsCredentialScopeEvidenceV1
    source_evidence: AwsLocationProviderEvidenceV1
    target_evidence: AwsLocationProviderEvidenceV1
    plan: MultiLocationEscrowPlanV1
    replication_receipt: MultiLocationReplicationReceiptV1
    pair_report: ProviderDurablePairReportV1
    evidence_authority: str = PROVIDER_EVIDENCE_AUTHORITY_V1
    schema: str = PROVIDER_EVIDENCE_CAPTURE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != PROVIDER_EVIDENCE_CAPTURE_SCHEMA_V1:
            raise ProviderDurableEvidenceBundleV1Error(
                f"unsupported provider capture schema: {self.schema}"
            )
        object.__setattr__(self, "code_sha", _sha(self.code_sha, field_name="code_sha"))
        if self.case_id != SYNTHETIC_PROVIDER_DRILL_CASE_ID_V1:
            raise ProviderDurableEvidenceBundleV1Error(
                "LRD-01H live provider capture is synthetic-only"
            )
        if self.evidence_authority != PROVIDER_EVIDENCE_AUTHORITY_V1:
            raise ProviderDurableEvidenceBundleV1Error(
                "provider capture cannot grant closure authority"
            )
        if self.escrow_manifest.case_id != self.case_id:
            raise ProviderDurableEvidenceBundleV1Error(
                "provider capture escrow case substitution"
            )

        source_versions = tuple(
            sorted(self.source_versions, key=lambda item: item.blob_digest)
        )
        target_versions = tuple(
            sorted(self.target_versions, key=lambda item: item.blob_digest)
        )
        object.__setattr__(self, "source_versions", source_versions)
        object.__setattr__(self, "target_versions", target_versions)

        validate_closure_grade_location_evidence_v1(
            profile=self.source_profile,
            location=self.source_location,
            escrow_manifest=self.escrow_manifest,
            versions=source_versions,
            credential_scope=self.source_credential_scope,
            evidence=self.source_evidence,
        )
        validate_closure_grade_location_evidence_v1(
            profile=self.target_profile,
            location=self.target_location,
            escrow_manifest=self.escrow_manifest,
            versions=target_versions,
            credential_scope=self.target_credential_scope,
            evidence=self.target_evidence,
        )

        manifest_digest = self.escrow_manifest.escrow_manifest_identity.digest
        if (
            self.plan.case_id != self.case_id
            or self.plan.escrow_manifest_digest != manifest_digest
            or self.plan.source_location_digest != self.source_location.location_digest
            or self.plan.target_location_digest != self.target_location.location_digest
        ):
            raise ProviderDurableEvidenceBundleV1Error(
                "provider capture multi-location plan substitution"
            )
        if (
            self.replication_receipt.plan_digest != self.plan.plan_digest
            or self.replication_receipt.case_id != self.case_id
            or self.replication_receipt.escrow_manifest_digest != manifest_digest
            or self.replication_receipt.source_location_digest
            != self.source_location.location_digest
            or self.replication_receipt.target_location_digest
            != self.target_location.location_digest
            or self.replication_receipt.blob_set_digest != self.plan.blob_set_digest
            or self.replication_receipt.replicated_blob_count != self.plan.blob_count
            or self.replication_receipt.replicated_bytes != self.plan.total_bytes
        ):
            raise ProviderDurableEvidenceBundleV1Error(
                "provider capture replication receipt substitution"
            )
        if self.pair_report.state is not ProviderEvidenceStateV1.VERIFIED:
            raise ProviderDurableEvidenceBundleV1Error(
                "provider capture requires VERIFIED two-location provider evidence"
            )
        if (
            self.pair_report.source_evidence_digest
            != self.source_evidence.evidence_digest
            or self.pair_report.target_evidence_digest
            != self.target_evidence.evidence_digest
            or self.pair_report.source_location_digest
            != self.source_location.location_digest
            or self.pair_report.target_location_digest
            != self.target_location.location_digest
        ):
            raise ProviderDurableEvidenceBundleV1Error(
                "provider capture pair-report substitution"
            )

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "code_sha": self.code_sha,
            "case_id": self.case_id,
            "escrow_manifest": self.escrow_manifest.canonical_dict(),
            "source_profile": self.source_profile.canonical_dict(),
            "target_profile": self.target_profile.canonical_dict(),
            "source_location": self.source_location.canonical_dict(),
            "target_location": self.target_location.canonical_dict(),
            "source_versions": [item.canonical_dict() for item in self.source_versions],
            "target_versions": [item.canonical_dict() for item in self.target_versions],
            "source_credential_scope": self.source_credential_scope.canonical_dict(),
            "target_credential_scope": self.target_credential_scope.canonical_dict(),
            "source_evidence": self.source_evidence.canonical_dict(),
            "target_evidence": self.target_evidence.canonical_dict(),
            "plan": self.plan.canonical_dict(),
            "replication_receipt": self.replication_receipt.canonical_dict(),
            "pair_report": self.pair_report.canonical_dict(),
            "evidence_authority": self.evidence_authority,
        }

    @property
    def capture_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "capture_digest": self.capture_digest}

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
    ) -> ProviderDurableEvidenceCaptureV1:
        _strict_keys(
            value,
            expected=frozenset(
                {
                    "schema",
                    "code_sha",
                    "case_id",
                    "escrow_manifest",
                    "source_profile",
                    "target_profile",
                    "source_location",
                    "target_location",
                    "source_versions",
                    "target_versions",
                    "source_credential_scope",
                    "target_credential_scope",
                    "source_evidence",
                    "target_evidence",
                    "plan",
                    "replication_receipt",
                    "pair_report",
                    "evidence_authority",
                    "capture_digest",
                }
            ),
            field_name="provider durable evidence capture",
        )
        source_versions = tuple(
            AwsS3ObjectVersionIdentityV1.from_dict(item)
            for item in _mapping_list(
                value.get("source_versions"), field_name="source_versions"
            )
        )
        target_versions = tuple(
            AwsS3ObjectVersionIdentityV1.from_dict(item)
            for item in _mapping_list(
                value.get("target_versions"), field_name="target_versions"
            )
        )
        result = cls(
            schema=_text(value.get("schema"), field_name="schema"),
            code_sha=_sha(value.get("code_sha"), field_name="code_sha"),
            case_id=_text(value.get("case_id"), field_name="case_id"),
            escrow_manifest=ArtifactEscrowManifestV1.from_dict(
                _mapping(value.get("escrow_manifest"), field_name="escrow_manifest")
            ),
            source_profile=parse_aws_s3_profile_v1(
                _mapping(value.get("source_profile"), field_name="source_profile")
            ),
            target_profile=parse_aws_s3_profile_v1(
                _mapping(value.get("target_profile"), field_name="target_profile")
            ),
            source_location=DurableEscrowLocationV1.from_dict(
                _mapping(value.get("source_location"), field_name="source_location")
            ),
            target_location=DurableEscrowLocationV1.from_dict(
                _mapping(value.get("target_location"), field_name="target_location")
            ),
            source_versions=source_versions,
            target_versions=target_versions,
            source_credential_scope=parse_credential_scope_evidence_v1(
                _mapping(
                    value.get("source_credential_scope"),
                    field_name="source_credential_scope",
                )
            ),
            target_credential_scope=parse_credential_scope_evidence_v1(
                _mapping(
                    value.get("target_credential_scope"),
                    field_name="target_credential_scope",
                )
            ),
            source_evidence=parse_location_provider_evidence_v1(
                _mapping(value.get("source_evidence"), field_name="source_evidence")
            ),
            target_evidence=parse_location_provider_evidence_v1(
                _mapping(value.get("target_evidence"), field_name="target_evidence")
            ),
            plan=MultiLocationEscrowPlanV1.from_dict(
                _mapping(value.get("plan"), field_name="plan")
            ),
            replication_receipt=MultiLocationReplicationReceiptV1.from_dict(
                _mapping(
                    value.get("replication_receipt"),
                    field_name="replication_receipt",
                )
            ),
            pair_report=parse_provider_pair_report_v1(
                _mapping(value.get("pair_report"), field_name="pair_report")
            ),
            evidence_authority=_text(
                value.get("evidence_authority"), field_name="evidence_authority"
            ),
        )
        if (
            _digest(value.get("capture_digest"), field_name="capture_digest")
            != result.capture_digest
        ):
            raise ProviderDurableEvidenceBundleV1Error(
                "provider durable evidence capture digest mismatch"
            )
        return result


@dataclass(frozen=True, slots=True)
class ProviderSourceLossDrillEvidenceV1:
    """Target-only restore evidence; never a closure/certification authority."""

    capture: ProviderDurableEvidenceCaptureV1
    post_loss_target_credential_scope: AwsCredentialScopeEvidenceV1
    post_loss_target_evidence: AwsLocationProviderEvidenceV1
    target_restore: LocationRestoreReportV1
    source_unavailability_evidence_digest: str
    source_unavailability_evidence_kind: str = SOURCE_UNAVAILABILITY_EVIDENCE_KIND_V1
    status: ProviderDrillEvidenceStatusV1 = (
        ProviderDrillEvidenceStatusV1.CAPTURED_NOT_CLOSURE_AUTHORITY
    )
    schema: str = PROVIDER_SOURCE_LOSS_DRILL_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != PROVIDER_SOURCE_LOSS_DRILL_SCHEMA_V1:
            raise ProviderDurableEvidenceBundleV1Error(
                f"unsupported provider source-loss drill schema: {self.schema}"
            )
        if (
            self.source_unavailability_evidence_kind
            != SOURCE_UNAVAILABILITY_EVIDENCE_KIND_V1
        ):
            raise ProviderDurableEvidenceBundleV1Error(
                "source-unavailability evidence kind cannot be promoted"
            )
        object.__setattr__(
            self,
            "source_unavailability_evidence_digest",
            _digest(
                self.source_unavailability_evidence_digest,
                field_name="source_unavailability_evidence_digest",
            ),
        )
        if (
            self.status
            is not ProviderDrillEvidenceStatusV1.CAPTURED_NOT_CLOSURE_AUTHORITY
        ):
            raise ProviderDurableEvidenceBundleV1Error(
                "provider drill bundle cannot grant closure authority"
            )

        validate_closure_grade_location_evidence_v1(
            profile=self.capture.target_profile,
            location=self.capture.target_location,
            escrow_manifest=self.capture.escrow_manifest,
            versions=self.capture.target_versions,
            credential_scope=self.post_loss_target_credential_scope,
            evidence=self.post_loss_target_evidence,
        )
        if (
            self.post_loss_target_evidence.principal_arn
            != self.capture.target_evidence.principal_arn
        ):
            raise ProviderDurableEvidenceBundleV1Error(
                "post-loss target principal changed from prepared target"
            )
        if self.target_restore.state is not RestoreConformanceStateV1.PASS:
            raise ProviderDurableEvidenceBundleV1Error(
                "source-loss drill requires target-only restore PASS"
            )
        if (
            self.target_restore.case_id != self.capture.case_id
            or self.target_restore.escrow_manifest_digest
            != self.capture.escrow_manifest.escrow_manifest_identity.digest
            or self.target_restore.location_digest
            != self.capture.target_location.location_digest
            or self.target_restore.blob_set_digest != self.capture.plan.blob_set_digest
            or self.target_restore.expected_blob_count != self.capture.plan.blob_count
            or self.target_restore.expected_bytes != self.capture.plan.total_bytes
        ):
            raise ProviderDurableEvidenceBundleV1Error(
                "source-loss target restore identity substitution"
            )

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "capture": self.capture.canonical_dict(),
            "post_loss_target_credential_scope": (
                self.post_loss_target_credential_scope.canonical_dict()
            ),
            "post_loss_target_evidence": self.post_loss_target_evidence.canonical_dict(),
            "target_restore": self.target_restore.canonical_dict(),
            "source_unavailability_evidence_digest": (
                self.source_unavailability_evidence_digest
            ),
            "source_unavailability_evidence_kind": (
                self.source_unavailability_evidence_kind
            ),
            "status": self.status.value,
        }

    @property
    def drill_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "drill_digest": self.drill_digest}

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, object],
    ) -> ProviderSourceLossDrillEvidenceV1:
        _strict_keys(
            value,
            expected=frozenset(
                {
                    "schema",
                    "capture",
                    "post_loss_target_credential_scope",
                    "post_loss_target_evidence",
                    "target_restore",
                    "source_unavailability_evidence_digest",
                    "source_unavailability_evidence_kind",
                    "status",
                    "drill_digest",
                }
            ),
            field_name="provider source-loss drill evidence",
        )
        try:
            status = ProviderDrillEvidenceStatusV1(
                _text(value.get("status"), field_name="status")
            )
        except ValueError as exc:
            raise ProviderDurableEvidenceBundleV1Error(
                "unknown provider drill evidence status"
            ) from exc
        result = cls(
            schema=_text(value.get("schema"), field_name="schema"),
            capture=ProviderDurableEvidenceCaptureV1.from_dict(
                _mapping(value.get("capture"), field_name="capture")
            ),
            post_loss_target_credential_scope=parse_credential_scope_evidence_v1(
                _mapping(
                    value.get("post_loss_target_credential_scope"),
                    field_name="post_loss_target_credential_scope",
                )
            ),
            post_loss_target_evidence=parse_location_provider_evidence_v1(
                _mapping(
                    value.get("post_loss_target_evidence"),
                    field_name="post_loss_target_evidence",
                )
            ),
            target_restore=LocationRestoreReportV1.from_dict(
                _mapping(value.get("target_restore"), field_name="target_restore")
            ),
            source_unavailability_evidence_digest=_digest(
                value.get("source_unavailability_evidence_digest"),
                field_name="source_unavailability_evidence_digest",
            ),
            source_unavailability_evidence_kind=_text(
                value.get("source_unavailability_evidence_kind"),
                field_name="source_unavailability_evidence_kind",
            ),
            status=status,
        )
        if (
            _digest(value.get("drill_digest"), field_name="drill_digest")
            != result.drill_digest
        ):
            raise ProviderDurableEvidenceBundleV1Error(
                "provider source-loss drill evidence digest mismatch"
            )
        return result
