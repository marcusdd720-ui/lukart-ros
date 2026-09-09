"""LRD-01H provider-verified durable storage adapter and WORM evidence v1.

AWS S3 Object Lock is the first provider adapter under the existing
``ArtifactEscrowBackendV1`` byte-store contract.  Provider evidence is an immutable,
content-addressed verification projection only.  It never becomes Product, CCL,
Gold, policy, trust-promotion, release, or ten-year durability authority.

The module intentionally has no boto3 dependency.  Callers inject narrow S3, STS,
and optional IAM policy-simulator clients.  Real AWS SDK clients satisfy these
protocols structurally, while repository tests can exercise fail-closed semantics
without manufacturing external provider evidence.
"""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, cast

from core.artifact_escrow_v1 import (
    ArtifactEscrowBackendV1,
    ArtifactEscrowError,
    ArtifactEscrowManifestV1,
    EscrowBlobIdentityV1,
    EscrowLimitsV1,
)
from core.durable_escrow_v1 import DurableEscrowLocationV1
from core.enterprise.recovery_continuity_v1 import StorageProfileV1
from core.p3.contracts import content_digest, require_hex_digest

AWS_S3_PROFILE_SCHEMA_V1 = "lukart.aws-s3-object-lock-profile.v1"
AWS_S3_VERSION_SCHEMA_V1 = "lukart.aws-s3-object-version.v1"
AWS_CREDENTIAL_SCOPE_SCHEMA_V1 = "lukart.aws-credential-scope-evidence.v1"
AWS_OBJECT_LOCK_EVIDENCE_SCHEMA_V1 = "lukart.aws-object-lock-evidence.v1"
AWS_LOCATION_EVIDENCE_SCHEMA_V1 = "lukart.aws-location-provider-evidence.v1"
PROVIDER_PAIR_REPORT_SCHEMA_V1 = "lukart.provider-durable-pair-report.v1"

_REQUIRED_BUCKET_ACTIONS = (
    "s3:GetBucketLocation",
    "s3:GetBucketObjectLockConfiguration",
)
_REQUIRED_OBJECT_ACTIONS = (
    "s3:GetObjectLegalHold",
    "s3:GetObjectRetention",
    "s3:GetObjectVersion",
    "s3:PutObject",
)
_FORBIDDEN_OBJECT_ACTIONS = (
    "s3:BypassGovernanceRetention",
    "s3:DeleteObject",
    "s3:DeleteObjectVersion",
    "s3:PutObjectLegalHold",
    "s3:PutObjectRetention",
)
_FIXED_REQUIRED_ACTIONS = frozenset((*_REQUIRED_BUCKET_ACTIONS, *_REQUIRED_OBJECT_ACTIONS))
_FIXED_FORBIDDEN_ACTIONS = frozenset(_FORBIDDEN_OBJECT_ACTIONS)


class ProviderDurableStorageV1Error(ValueError):
    """Fail-closed LRD-01H contract violation."""


class ProviderEvidenceStateV1(StrEnum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    FAIL = "FAIL"


class AwsRetentionModeV1(StrEnum):
    COMPLIANCE = "COMPLIANCE"
    GOVERNANCE = "GOVERNANCE"


class AwsLegalHoldStateV1(StrEnum):
    ON = "ON"
    OFF = "OFF"
    UNKNOWN = "UNKNOWN"


class S3ClientV1(Protocol):
    def put_object(self, **kwargs: object) -> Mapping[str, object]: ...

    def get_object(self, **kwargs: object) -> Mapping[str, object]: ...

    def get_bucket_location(self, **kwargs: object) -> Mapping[str, object]: ...

    def get_object_lock_configuration(self, **kwargs: object) -> Mapping[str, object]: ...

    def get_object_retention(self, **kwargs: object) -> Mapping[str, object]: ...

    def get_object_legal_hold(self, **kwargs: object) -> Mapping[str, object]: ...


class StsClientV1(Protocol):
    def get_caller_identity(self, **kwargs: object) -> Mapping[str, object]: ...


class IamPolicySimulatorClientV1(Protocol):
    def simulate_principal_policy(self, **kwargs: object) -> Mapping[str, object]: ...


class ReadableBodyV1(Protocol):
    def read(self, amt: int | None = None) -> bytes: ...

    def close(self) -> None: ...


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProviderDurableStorageV1Error(
            f"{field_name} must be nonblank and already canonical"
        )
    return value


def _digest(value: object, *, field_name: str) -> str:
    try:
        return require_hex_digest(_text(value, field_name=field_name), field_name=field_name)
    except ValueError as exc:
        raise ProviderDurableStorageV1Error(str(exc)) from exc


def _nonnegative_int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProviderDurableStorageV1Error(f"{field_name} must be a nonnegative integer")
    return value


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
    raise ProviderDurableStorageV1Error(
        f"{field_name} key contract violation: missing={missing}; unknown={unknown}"
    )


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProviderDurableStorageV1Error("provider timestamp must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _utc_datetime(value: object, *, field_name: str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ProviderDurableStorageV1Error(f"{field_name} must be timezone-aware")
        return value.astimezone(UTC)
    if not isinstance(value, str):
        raise ProviderDurableStorageV1Error(f"{field_name} must be an ISO-8601 timestamp")
    raw = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ProviderDurableStorageV1Error(
            f"{field_name} must be an ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProviderDurableStorageV1Error(f"{field_name} must be timezone-aware")
    return parsed.astimezone(UTC)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _response_request_id(response: Mapping[str, object]) -> str:
    metadata = response.get("ResponseMetadata")
    if not isinstance(metadata, Mapping):
        return "unavailable"
    request_id = metadata.get("RequestId")
    if not isinstance(request_id, str) or not request_id:
        return "unavailable"
    return request_id


def _normalize_bucket_region(raw: object) -> str:
    if raw in (None, ""):
        return "us-east-1"
    if raw == "EU":
        return "eu-west-1"
    return _text(raw, field_name="bucket region")


def _body_bytes(response: Mapping[str, object], *, max_bytes: int) -> bytes:
    body = response.get("Body")
    if body is None or not hasattr(body, "read"):
        raise ProviderDurableStorageV1Error("S3 GetObject response has no readable body")
    readable = cast(ReadableBodyV1, body)
    try:
        data = readable.read(max_bytes + 1)
    finally:
        readable.close()
    if not isinstance(data, bytes):
        raise ProviderDurableStorageV1Error("S3 GetObject body must produce bytes")
    if len(data) > max_bytes:
        raise ProviderDurableStorageV1Error("S3 object exceeds max_blob_bytes")
    return data


def _checksum_sha256_base64(data: bytes) -> str:
    return base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")


@dataclass(frozen=True, slots=True)
class AwsS3ObjectLockProfileV1:
    """Secret-free identity for one S3 Object Lock escrow location."""

    region: str
    bucket: str
    key_prefix: str
    expected_bucket_owner: str
    credential_domain_id: str
    policy_source_arn: str | None = None
    schema: str = AWS_S3_PROFILE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != AWS_S3_PROFILE_SCHEMA_V1:
            raise ProviderDurableStorageV1Error(f"unsupported AWS S3 profile schema: {self.schema}")
        for name in (
            "region",
            "bucket",
            "key_prefix",
            "expected_bucket_owner",
            "credential_domain_id",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), field_name=name))
        if self.key_prefix.startswith("/") or self.key_prefix.endswith("/"):
            raise ProviderDurableStorageV1Error(
                "key_prefix must be canonical without leading/trailing slash"
            )
        if ".." in self.key_prefix.split("/"):
            raise ProviderDurableStorageV1Error("key_prefix cannot contain parent traversal")
        if self.policy_source_arn is not None:
            object.__setattr__(
                self,
                "policy_source_arn",
                _text(self.policy_source_arn, field_name="policy_source_arn"),
            )

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "region": self.region,
            "bucket": self.bucket,
            "key_prefix": self.key_prefix,
            "expected_bucket_owner": self.expected_bucket_owner,
            "credential_domain_id": self.credential_domain_id,
            "policy_source_arn": self.policy_source_arn,
        }

    @property
    def profile_digest(self) -> str:
        return content_digest(self.canonical_body())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "profile_digest": self.profile_digest}

    def storage_profile(self) -> StorageProfileV1:
        return StorageProfileV1.from_configuration(
            backend_kind="aws-s3-object-lock-v1",
            implementation_id="core.provider_durable_storage_v1.AwsS3ObjectLockEscrowBackendV1",
            implementation_version="1",
            storage_schema="sha256-prefix-versioned-object-v1",
            public_configuration=self.canonical_body(),
        )

    def object_key(self, identity: EscrowBlobIdentityV1) -> str:
        return f"{self.key_prefix}/sha256/{identity.digest[:2]}/{identity.digest}"


@dataclass(frozen=True, slots=True)
class AwsS3ObjectVersionIdentityV1:
    """Exact provider object-version identity bound to LRD-01C blob bytes."""

    profile_digest: str
    bucket: str
    key: str
    version_id: str
    blob_digest: str
    blob_size: int
    schema: str = AWS_S3_VERSION_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != AWS_S3_VERSION_SCHEMA_V1:
            raise ProviderDurableStorageV1Error(
                f"unsupported S3 object-version schema: {self.schema}"
            )
        object.__setattr__(
            self,
            "profile_digest",
            _digest(self.profile_digest, field_name="profile_digest"),
        )
        for name in ("bucket", "key", "version_id"):
            object.__setattr__(self, name, _text(getattr(self, name), field_name=name))
        object.__setattr__(
            self,
            "blob_digest",
            _digest(self.blob_digest, field_name="blob_digest"),
        )
        object.__setattr__(
            self,
            "blob_size",
            _nonnegative_int(self.blob_size, field_name="blob_size"),
        )

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "profile_digest": self.profile_digest,
            "bucket": self.bucket,
            "key": self.key,
            "version_id": self.version_id,
            "blob_digest": self.blob_digest,
            "blob_size": self.blob_size,
        }

    @property
    def version_digest(self) -> str:
        return content_digest(self.canonical_body())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "version_digest": self.version_digest}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> AwsS3ObjectVersionIdentityV1:
        _strict_keys(
            value,
            expected=frozenset(
                {
                    "schema",
                    "profile_digest",
                    "bucket",
                    "key",
                    "version_id",
                    "blob_digest",
                    "blob_size",
                    "version_digest",
                }
            ),
            field_name="S3 object-version identity",
        )
        result = cls(
            schema=_text(value.get("schema"), field_name="schema"),
            profile_digest=_digest(value.get("profile_digest"), field_name="profile_digest"),
            bucket=_text(value.get("bucket"), field_name="bucket"),
            key=_text(value.get("key"), field_name="key"),
            version_id=_text(value.get("version_id"), field_name="version_id"),
            blob_digest=_digest(value.get("blob_digest"), field_name="blob_digest"),
            blob_size=_nonnegative_int(value.get("blob_size"), field_name="blob_size"),
        )
        if _digest(value.get("version_digest"), field_name="version_digest") != result.version_digest:
            raise ProviderDurableStorageV1Error("S3 object-version digest mismatch")
        return result


class AwsS3ObjectLockEscrowBackendV1(ArtifactEscrowBackendV1):
    """S3 byte-store adapter that always rereads one exact VersionId.

    The adapter exposes no delete, retention mutation, legal-hold mutation, or bucket
    policy/configuration API.  Version bindings are infrastructure provenance, not
    artifact identity; exact artifact identity remains SHA-256 + size from LRD-01C.
    """

    def __init__(
        self,
        *,
        s3_client: S3ClientV1,
        profile: AwsS3ObjectLockProfileV1,
        version_bindings: Sequence[AwsS3ObjectVersionIdentityV1] = (),
    ) -> None:
        self.s3_client = s3_client
        self.profile = profile
        self._versions: dict[str, AwsS3ObjectVersionIdentityV1] = {}
        for version in version_bindings:
            self._bind(version)

    def _bind(self, version: AwsS3ObjectVersionIdentityV1) -> None:
        if version.profile_digest != self.profile.profile_digest:
            raise ProviderDurableStorageV1Error("S3 version belongs to a different profile")
        if version.bucket != self.profile.bucket:
            raise ProviderDurableStorageV1Error("S3 version belongs to a different bucket")
        expected_key = self.profile.object_key(
            EscrowBlobIdentityV1(digest=version.blob_digest, size=version.blob_size)
        )
        if version.key != expected_key:
            raise ProviderDurableStorageV1Error("S3 version key is not content-addressed")
        previous = self._versions.get(version.blob_digest)
        if previous is not None and previous != version:
            raise ProviderDurableStorageV1Error("ambiguous S3 version binding")
        self._versions[version.blob_digest] = version

    def publish(self, data: bytes, *, limits: EscrowLimitsV1) -> EscrowBlobIdentityV1:
        if len(data) > limits.max_blob_bytes:
            raise ArtifactEscrowError("artifact exceeds max_blob_bytes")
        identity = EscrowBlobIdentityV1.for_bytes(data)
        existing = self._versions.get(identity.digest)
        if existing is not None:
            if self.read(identity, limits=limits) != data:
                raise ArtifactEscrowError("existing exact S3 version does not match blob")
            return identity
        key = self.profile.object_key(identity)
        try:
            response = self.s3_client.put_object(
                Bucket=self.profile.bucket,
                Key=key,
                Body=data,
                ChecksumAlgorithm="SHA256",
                ChecksumSHA256=_checksum_sha256_base64(data),
                ExpectedBucketOwner=self.profile.expected_bucket_owner,
            )
        except Exception as exc:
            raise ArtifactEscrowError("S3 content-addressed publication failed") from exc
        version_id = response.get("VersionId")
        if not isinstance(version_id, str) or not version_id:
            raise ArtifactEscrowError("S3 publication did not return an exact VersionId")
        version = AwsS3ObjectVersionIdentityV1(
            profile_digest=self.profile.profile_digest,
            bucket=self.profile.bucket,
            key=key,
            version_id=version_id,
            blob_digest=identity.digest,
            blob_size=identity.size,
        )
        try:
            self._bind(version)
            reread = self.read(identity, limits=limits)
        except ProviderDurableStorageV1Error as exc:
            raise ArtifactEscrowError("S3 version binding verification failed") from exc
        if reread != data:
            raise ArtifactEscrowError("S3 verified reread changed artifact bytes")
        return identity

    def read(
        self,
        identity: EscrowBlobIdentityV1,
        *,
        limits: EscrowLimitsV1,
    ) -> bytes:
        if identity.size > limits.max_blob_bytes:
            raise ArtifactEscrowError("artifact exceeds max_blob_bytes")
        version = self._versions.get(identity.digest)
        if version is None:
            raise ArtifactEscrowError("exact S3 VersionId binding is required before read")
        if version.blob_size != identity.size:
            raise ArtifactEscrowError("S3 version size binding mismatch")
        try:
            response = self.s3_client.get_object(
                Bucket=self.profile.bucket,
                Key=version.key,
                VersionId=version.version_id,
                ExpectedBucketOwner=self.profile.expected_bucket_owner,
            )
            data = _body_bytes(response, max_bytes=limits.max_blob_bytes)
        except ProviderDurableStorageV1Error as exc:
            raise ArtifactEscrowError("S3 exact-version read failed") from exc
        except Exception as exc:
            raise ArtifactEscrowError("S3 exact-version read failed") from exc
        returned_version = response.get("VersionId")
        if returned_version != version.version_id:
            raise ArtifactEscrowError("S3 returned stale/substituted VersionId")
        if len(data) != identity.size or _sha256(data) != identity.digest:
            raise ArtifactEscrowError("S3 exact-version bytes failed SHA-256/size binding")
        return data

    def version_identity(self, identity: EscrowBlobIdentityV1) -> AwsS3ObjectVersionIdentityV1:
        version = self._versions.get(identity.digest)
        if version is None or version.blob_size != identity.size:
            raise ProviderDurableStorageV1Error("exact S3 VersionId binding is unavailable")
        return version

    def version_bindings(self) -> tuple[AwsS3ObjectVersionIdentityV1, ...]:
        return tuple(sorted(self._versions.values(), key=lambda item: item.blob_digest))


@dataclass(frozen=True, slots=True)
class AwsCredentialScopeEvidenceV1:
    """Read-only IAM simulation evidence for one storage principal."""

    policy_source_arn: str
    required_allowed: tuple[str, ...]
    forbidden_denied: tuple[str, ...]
    state: ProviderEvidenceStateV1
    violations: tuple[str, ...]
    schema: str = AWS_CREDENTIAL_SCOPE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != AWS_CREDENTIAL_SCOPE_SCHEMA_V1:
            raise ProviderDurableStorageV1Error(
                f"unsupported credential-scope schema: {self.schema}"
            )
        object.__setattr__(
            self,
            "policy_source_arn",
            _text(self.policy_source_arn, field_name="policy_source_arn"),
        )
        required = tuple(sorted({_text(item, field_name="required action") for item in self.required_allowed}))
        forbidden = tuple(sorted({_text(item, field_name="forbidden action") for item in self.forbidden_denied}))
        violations = tuple(sorted({_text(item, field_name="violation") for item in self.violations}))
        object.__setattr__(self, "required_allowed", required)
        object.__setattr__(self, "forbidden_denied", forbidden)
        object.__setattr__(self, "violations", violations)
        if not isinstance(self.state, ProviderEvidenceStateV1):
            raise ProviderDurableStorageV1Error("unknown credential-scope evidence state")
        if self.state is ProviderEvidenceStateV1.VERIFIED:
            if set(required) != _FIXED_REQUIRED_ACTIONS:
                raise ProviderDurableStorageV1Error("VERIFIED credential scope lacks required actions")
            if set(forbidden) != _FIXED_FORBIDDEN_ACTIONS:
                raise ProviderDurableStorageV1Error("VERIFIED credential scope lacks deny evidence")
            if violations:
                raise ProviderDurableStorageV1Error("VERIFIED credential scope cannot have violations")
        elif not violations:
            raise ProviderDurableStorageV1Error("non-VERIFIED credential scope requires violations")

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "policy_source_arn": self.policy_source_arn,
            "required_allowed": list(self.required_allowed),
            "forbidden_denied": list(self.forbidden_denied),
            "state": self.state.value,
            "violations": list(self.violations),
        }

    @property
    def evidence_digest(self) -> str:
        return content_digest(self.canonical_body())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "evidence_digest": self.evidence_digest}


def _simulation_decisions(response: Mapping[str, object]) -> dict[str, str]:
    raw = response.get("EvaluationResults")
    if not isinstance(raw, list):
        raise ProviderDurableStorageV1Error("IAM simulation result is missing evaluations")
    result: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, Mapping):
            raise ProviderDurableStorageV1Error("IAM simulation evaluation must be an object")
        action = item.get("EvalActionName")
        decision = item.get("EvalDecision")
        if not isinstance(action, str) or not isinstance(decision, str):
            raise ProviderDurableStorageV1Error("IAM simulation evaluation is malformed")
        if action in result:
            raise ProviderDurableStorageV1Error("duplicate IAM simulation action result")
        result[action] = decision.lower()
    return result


def verify_credential_scope_v1(
    *,
    iam_client: IamPolicySimulatorClientV1 | None,
    profile: AwsS3ObjectLockProfileV1,
) -> AwsCredentialScopeEvidenceV1:
    """Verify required storage access and reject destructive/governance-bypass overreach.

    The IAM simulator is deliberately a separate read-only auditor client; the storage
    credentials themselves do not need policy-inspection authority.
    """

    if iam_client is None or profile.policy_source_arn is None:
        return AwsCredentialScopeEvidenceV1(
            policy_source_arn=profile.policy_source_arn or "UNAVAILABLE",
            required_allowed=(),
            forbidden_denied=(),
            state=ProviderEvidenceStateV1.UNVERIFIED,
            violations=("iam_policy_simulation_unavailable",),
        )
    bucket_arn = f"arn:aws:s3:::{profile.bucket}"
    object_arn = f"{bucket_arn}/{profile.key_prefix}/*"
    try:
        bucket_response = iam_client.simulate_principal_policy(
            PolicySourceArn=profile.policy_source_arn,
            ActionNames=list(_REQUIRED_BUCKET_ACTIONS),
            ResourceArns=[bucket_arn],
        )
        object_response = iam_client.simulate_principal_policy(
            PolicySourceArn=profile.policy_source_arn,
            ActionNames=list((*_REQUIRED_OBJECT_ACTIONS, *_FORBIDDEN_OBJECT_ACTIONS)),
            ResourceArns=[object_arn],
        )
        decisions = {
            **_simulation_decisions(bucket_response),
            **_simulation_decisions(object_response),
        }
    except Exception as exc:
        raise ProviderDurableStorageV1Error("IAM policy simulation failed closed") from exc

    violations: list[str] = []
    required_allowed: list[str] = []
    forbidden_denied: list[str] = []
    for action in sorted(_FIXED_REQUIRED_ACTIONS):
        if decisions.get(action) == "allowed":
            required_allowed.append(action)
        else:
            violations.append(f"required_not_allowed:{action}")
    for action in sorted(_FIXED_FORBIDDEN_ACTIONS):
        if decisions.get(action) in {"explicitdeny", "implicitdeny"}:
            forbidden_denied.append(action)
        else:
            violations.append(f"credential_overreach:{action}")
    return AwsCredentialScopeEvidenceV1(
        policy_source_arn=profile.policy_source_arn,
        required_allowed=tuple(required_allowed),
        forbidden_denied=tuple(forbidden_denied),
        state=(
            ProviderEvidenceStateV1.VERIFIED
            if not violations
            else ProviderEvidenceStateV1.FAIL
        ),
        violations=tuple(violations),
    )


@dataclass(frozen=True, slots=True)
class AwsObjectLockEvidenceV1:
    """Provider-observed evidence for one exact S3 object version."""

    version_digest: str
    observed_region: str
    principal_account: str
    principal_arn: str
    object_lock_enabled: bool
    retention_mode: AwsRetentionModeV1 | None
    retain_until_utc: str | None
    legal_hold: AwsLegalHoldStateV1
    state: ProviderEvidenceStateV1
    violations: tuple[str, ...]
    provider_request_ids: tuple[str, ...]
    schema: str = AWS_OBJECT_LOCK_EVIDENCE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != AWS_OBJECT_LOCK_EVIDENCE_SCHEMA_V1:
            raise ProviderDurableStorageV1Error(
                f"unsupported Object Lock evidence schema: {self.schema}"
            )
        object.__setattr__(
            self,
            "version_digest",
            _digest(self.version_digest, field_name="version_digest"),
        )
        for name in ("observed_region", "principal_account", "principal_arn"):
            object.__setattr__(self, name, _text(getattr(self, name), field_name=name))
        if not isinstance(self.object_lock_enabled, bool):
            raise ProviderDurableStorageV1Error("object_lock_enabled must be boolean")
        if self.retention_mode is not None and not isinstance(
            self.retention_mode, AwsRetentionModeV1
        ):
            raise ProviderDurableStorageV1Error("unknown Object Lock retention mode")
        if self.retain_until_utc is not None:
            _utc_datetime(self.retain_until_utc, field_name="retain_until_utc")
        if not isinstance(self.legal_hold, AwsLegalHoldStateV1):
            raise ProviderDurableStorageV1Error("unknown legal hold state")
        if not isinstance(self.state, ProviderEvidenceStateV1):
            raise ProviderDurableStorageV1Error("unknown provider evidence state")
        violations = tuple(sorted({_text(item, field_name="violation") for item in self.violations}))
        request_ids = tuple(sorted({_text(item, field_name="provider_request_id") for item in self.provider_request_ids}))
        object.__setattr__(self, "violations", violations)
        object.__setattr__(self, "provider_request_ids", request_ids)
        if self.state is ProviderEvidenceStateV1.VERIFIED:
            if violations:
                raise ProviderDurableStorageV1Error("VERIFIED Object Lock evidence has violations")
            if not self.object_lock_enabled:
                raise ProviderDurableStorageV1Error("VERIFIED Object Lock evidence requires enabled lock")
            if self.retention_mode is not AwsRetentionModeV1.COMPLIANCE:
                raise ProviderDurableStorageV1Error("only COMPLIANCE may be provider VERIFIED")
            if self.retain_until_utc is None:
                raise ProviderDurableStorageV1Error("VERIFIED retention requires retain-until date")
        elif not violations:
            raise ProviderDurableStorageV1Error("non-VERIFIED Object Lock evidence requires violations")

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "version_digest": self.version_digest,
            "observed_region": self.observed_region,
            "principal_account": self.principal_account,
            "principal_arn": self.principal_arn,
            "object_lock_enabled": self.object_lock_enabled,
            "retention_mode": self.retention_mode.value if self.retention_mode else None,
            "retain_until_utc": self.retain_until_utc,
            "legal_hold": self.legal_hold.value,
            "state": self.state.value,
            "violations": list(self.violations),
            "provider_request_ids": list(self.provider_request_ids),
        }

    @property
    def evidence_digest(self) -> str:
        return content_digest(self.canonical_body())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "evidence_digest": self.evidence_digest}


def verify_object_lock_version_v1(
    *,
    s3_client: S3ClientV1,
    sts_client: StsClientV1,
    profile: AwsS3ObjectLockProfileV1,
    version: AwsS3ObjectVersionIdentityV1,
    observed_at: datetime,
) -> AwsObjectLockEvidenceV1:
    """Read provider APIs and verify active COMPLIANCE retention for one exact VersionId."""

    now = _utc_datetime(observed_at, field_name="observed_at")
    if version.profile_digest != profile.profile_digest or version.bucket != profile.bucket:
        raise ProviderDurableStorageV1Error("provider evidence profile/version substitution")
    try:
        caller = sts_client.get_caller_identity()
        region_response = s3_client.get_bucket_location(
            Bucket=profile.bucket,
            ExpectedBucketOwner=profile.expected_bucket_owner,
        )
        lock_response = s3_client.get_object_lock_configuration(
            Bucket=profile.bucket,
            ExpectedBucketOwner=profile.expected_bucket_owner,
        )
        retention_response = s3_client.get_object_retention(
            Bucket=profile.bucket,
            Key=version.key,
            VersionId=version.version_id,
            ExpectedBucketOwner=profile.expected_bucket_owner,
        )
        hold_response = s3_client.get_object_legal_hold(
            Bucket=profile.bucket,
            Key=version.key,
            VersionId=version.version_id,
            ExpectedBucketOwner=profile.expected_bucket_owner,
        )
    except Exception as exc:
        raise ProviderDurableStorageV1Error("provider Object Lock API verification failed") from exc

    account = _text(caller.get("Account"), field_name="provider account")
    arn = _text(caller.get("Arn"), field_name="provider principal ARN")
    observed_region = _normalize_bucket_region(region_response.get("LocationConstraint"))
    lock_config = lock_response.get("ObjectLockConfiguration")
    object_lock_enabled = (
        isinstance(lock_config, Mapping) and lock_config.get("ObjectLockEnabled") == "Enabled"
    )
    retention = retention_response.get("Retention")
    raw_mode: object = None
    raw_until: object = None
    if isinstance(retention, Mapping):
        raw_mode = retention.get("Mode")
        raw_until = retention.get("RetainUntilDate")
    mode: AwsRetentionModeV1 | None = None
    if isinstance(raw_mode, str):
        try:
            mode = AwsRetentionModeV1(raw_mode)
        except ValueError:
            mode = None
    retain_until: datetime | None = None
    if raw_until is not None:
        retain_until = _utc_datetime(raw_until, field_name="RetainUntilDate")
    hold = hold_response.get("LegalHold")
    hold_status = hold.get("Status") if isinstance(hold, Mapping) else None
    legal_hold = (
        AwsLegalHoldStateV1.ON
        if hold_status == "ON"
        else AwsLegalHoldStateV1.OFF
        if hold_status == "OFF"
        else AwsLegalHoldStateV1.UNKNOWN
    )

    violations: list[str] = []
    if account != profile.expected_bucket_owner:
        violations.append("wrong_account")
    if observed_region != profile.region:
        violations.append("wrong_region")
    if not object_lock_enabled:
        violations.append("object_lock_disabled")
    if mode is not AwsRetentionModeV1.COMPLIANCE:
        violations.append(
            "governance_retention_not_worm" if mode is AwsRetentionModeV1.GOVERNANCE else "missing_retention"
        )
    if retain_until is None:
        violations.append("missing_retain_until")
    elif retain_until <= now:
        violations.append("expired_retention")

    return AwsObjectLockEvidenceV1(
        version_digest=version.version_digest,
        observed_region=observed_region,
        principal_account=account,
        principal_arn=arn,
        object_lock_enabled=object_lock_enabled,
        retention_mode=mode,
        retain_until_utc=_utc_text(retain_until) if retain_until is not None else None,
        legal_hold=legal_hold,
        state=(ProviderEvidenceStateV1.VERIFIED if not violations else ProviderEvidenceStateV1.FAIL),
        violations=tuple(violations),
        provider_request_ids=tuple(
            _response_request_id(item)
            for item in (caller, region_response, lock_response, retention_response, hold_response)
        ),
    )


@dataclass(frozen=True, slots=True)
class AwsLocationProviderEvidenceV1:
    """Whole-location provider evidence bound to one exact escrow manifest."""

    generic_location_digest: str
    storage_profile_digest: str
    aws_profile_digest: str
    escrow_manifest_digest: str
    principal_arn: str
    principal_account: str
    observed_region: str
    object_evidence: tuple[AwsObjectLockEvidenceV1, ...]
    credential_scope_digest: str
    state: ProviderEvidenceStateV1
    violations: tuple[str, ...]
    schema: str = AWS_LOCATION_EVIDENCE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != AWS_LOCATION_EVIDENCE_SCHEMA_V1:
            raise ProviderDurableStorageV1Error(
                f"unsupported AWS location evidence schema: {self.schema}"
            )
        for name in (
            "generic_location_digest",
            "storage_profile_digest",
            "aws_profile_digest",
            "escrow_manifest_digest",
            "credential_scope_digest",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), field_name=name))
        for name in ("principal_arn", "principal_account", "observed_region"):
            object.__setattr__(self, name, _text(getattr(self, name), field_name=name))
        evidence = tuple(sorted(self.object_evidence, key=lambda item: item.version_digest))
        if len({item.version_digest for item in evidence}) != len(evidence):
            raise ProviderDurableStorageV1Error("duplicate provider object evidence")
        object.__setattr__(self, "object_evidence", evidence)
        violations = tuple(sorted({_text(item, field_name="violation") for item in self.violations}))
        object.__setattr__(self, "violations", violations)
        if not isinstance(self.state, ProviderEvidenceStateV1):
            raise ProviderDurableStorageV1Error("unknown location provider evidence state")
        if self.state is ProviderEvidenceStateV1.VERIFIED:
            if violations or not evidence:
                raise ProviderDurableStorageV1Error("VERIFIED location evidence must be complete")
            if any(item.state is not ProviderEvidenceStateV1.VERIFIED for item in evidence):
                raise ProviderDurableStorageV1Error("VERIFIED location contains unverified object")
        elif not violations:
            raise ProviderDurableStorageV1Error("non-VERIFIED location evidence requires violations")

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "generic_location_digest": self.generic_location_digest,
            "storage_profile_digest": self.storage_profile_digest,
            "aws_profile_digest": self.aws_profile_digest,
            "escrow_manifest_digest": self.escrow_manifest_digest,
            "principal_arn": self.principal_arn,
            "principal_account": self.principal_account,
            "observed_region": self.observed_region,
            "object_evidence": [item.canonical_dict() for item in self.object_evidence],
            "credential_scope_digest": self.credential_scope_digest,
            "state": self.state.value,
            "violations": list(self.violations),
        }

    @property
    def evidence_digest(self) -> str:
        return content_digest(self.canonical_body())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "evidence_digest": self.evidence_digest}


def verify_s3_location_v1(
    *,
    expected_case_id: str,
    escrow_manifest: ArtifactEscrowManifestV1,
    generic_location: DurableEscrowLocationV1,
    backend: AwsS3ObjectLockEscrowBackendV1,
    s3_client: S3ClientV1,
    sts_client: StsClientV1,
    iam_client: IamPolicySimulatorClientV1 | None,
    observed_at: datetime,
    limits: EscrowLimitsV1,
) -> tuple[AwsLocationProviderEvidenceV1, AwsCredentialScopeEvidenceV1]:
    """Verify exact bytes, object versions, Object Lock, retention, and credential scope."""

    if escrow_manifest.case_id != _text(expected_case_id, field_name="expected_case_id"):
        raise ProviderDurableStorageV1Error("provider verification case substitution")
    profile = backend.profile
    storage_profile = profile.storage_profile()
    if generic_location.storage_profile_digest != storage_profile.profile_digest:
        raise ProviderDurableStorageV1Error("generic location/storage profile substitution")
    if generic_location.credential_domain_id != profile.credential_domain_id:
        raise ProviderDurableStorageV1Error("credential-domain substitution")

    credential_scope = verify_credential_scope_v1(iam_client=iam_client, profile=profile)
    object_evidence: list[AwsObjectLockEvidenceV1] = []
    violations: list[str] = []
    expected_versions: set[str] = set()
    for binding in escrow_manifest.bindings:
        try:
            backend.read(binding.blob, limits=limits)
            version = backend.version_identity(binding.blob)
        except (ArtifactEscrowError, ProviderDurableStorageV1Error):
            violations.append(f"{binding.role.value}:verified_reread_failed")
            continue
        expected_versions.add(version.version_digest)
        evidence = verify_object_lock_version_v1(
            s3_client=s3_client,
            sts_client=sts_client,
            profile=profile,
            version=version,
            observed_at=observed_at,
        )
        object_evidence.append(evidence)
        if evidence.state is not ProviderEvidenceStateV1.VERIFIED:
            violations.extend(f"{binding.role.value}:{item}" for item in evidence.violations)
    if credential_scope.state is not ProviderEvidenceStateV1.VERIFIED:
        violations.extend(credential_scope.violations)
    if len(expected_versions) != len(escrow_manifest.bindings):
        violations.append("incomplete_exact_version_inventory")

    principal_arns = {item.principal_arn for item in object_evidence}
    principal_accounts = {item.principal_account for item in object_evidence}
    regions = {item.observed_region for item in object_evidence}
    if len(principal_arns) != 1:
        violations.append("inconsistent_principal_identity")
    if len(principal_accounts) != 1:
        violations.append("inconsistent_provider_account")
    if len(regions) != 1:
        violations.append("inconsistent_provider_region")

    return (
        AwsLocationProviderEvidenceV1(
            generic_location_digest=generic_location.location_digest,
            storage_profile_digest=storage_profile.profile_digest,
            aws_profile_digest=profile.profile_digest,
            escrow_manifest_digest=escrow_manifest.escrow_manifest_identity.digest,
            principal_arn=next(iter(principal_arns), "UNAVAILABLE"),
            principal_account=next(iter(principal_accounts), "UNAVAILABLE"),
            observed_region=next(iter(regions), profile.region),
            object_evidence=tuple(object_evidence),
            credential_scope_digest=credential_scope.evidence_digest,
            state=(ProviderEvidenceStateV1.VERIFIED if not violations else ProviderEvidenceStateV1.FAIL),
            violations=tuple(violations),
        ),
        credential_scope,
    )


@dataclass(frozen=True, slots=True)
class ProviderDurablePairReportV1:
    """Two-location AWS evidence without converting it into a ten-year SLA."""

    source_evidence_digest: str
    target_evidence_digest: str
    source_location_digest: str
    target_location_digest: str
    distinct_regions: bool
    distinct_principals: bool
    distinct_credential_domains: bool
    state: ProviderEvidenceStateV1
    violations: tuple[str, ...]
    ten_year_durability_claim: bool = False
    schema: str = PROVIDER_PAIR_REPORT_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != PROVIDER_PAIR_REPORT_SCHEMA_V1:
            raise ProviderDurableStorageV1Error(
                f"unsupported provider pair report schema: {self.schema}"
            )
        for name in (
            "source_evidence_digest",
            "target_evidence_digest",
            "source_location_digest",
            "target_location_digest",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), field_name=name))
        for name in ("distinct_regions", "distinct_principals", "distinct_credential_domains"):
            if not isinstance(getattr(self, name), bool):
                raise ProviderDurableStorageV1Error(f"{name} must be boolean")
        if self.ten_year_durability_claim:
            raise ProviderDurableStorageV1Error("LRD-01H cannot manufacture a ten-year SLA")
        if not isinstance(self.state, ProviderEvidenceStateV1):
            raise ProviderDurableStorageV1Error("unknown provider pair state")
        violations = tuple(sorted({_text(item, field_name="violation") for item in self.violations}))
        object.__setattr__(self, "violations", violations)
        if self.state is ProviderEvidenceStateV1.VERIFIED:
            if violations:
                raise ProviderDurableStorageV1Error("VERIFIED provider pair has violations")
            if not (
                self.distinct_regions
                and self.distinct_principals
                and self.distinct_credential_domains
            ):
                raise ProviderDurableStorageV1Error("VERIFIED provider pair lacks separation")
        elif not violations:
            raise ProviderDurableStorageV1Error("non-VERIFIED provider pair requires violations")

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source_evidence_digest": self.source_evidence_digest,
            "target_evidence_digest": self.target_evidence_digest,
            "source_location_digest": self.source_location_digest,
            "target_location_digest": self.target_location_digest,
            "distinct_regions": self.distinct_regions,
            "distinct_principals": self.distinct_principals,
            "distinct_credential_domains": self.distinct_credential_domains,
            "state": self.state.value,
            "violations": list(self.violations),
            "ten_year_durability_claim": self.ten_year_durability_claim,
        }

    @property
    def report_digest(self) -> str:
        return content_digest(self.canonical_body())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.canonical_body(), "report_digest": self.report_digest}


def build_provider_pair_report_v1(
    *,
    source_location: DurableEscrowLocationV1,
    target_location: DurableEscrowLocationV1,
    source_evidence: AwsLocationProviderEvidenceV1,
    target_evidence: AwsLocationProviderEvidenceV1,
) -> ProviderDurablePairReportV1:
    """Bind two independently verified provider locations and fail closed on overlap."""

    if source_evidence.generic_location_digest != source_location.location_digest:
        raise ProviderDurableStorageV1Error("source provider evidence location substitution")
    if target_evidence.generic_location_digest != target_location.location_digest:
        raise ProviderDurableStorageV1Error("target provider evidence location substitution")
    if source_evidence.escrow_manifest_digest != target_evidence.escrow_manifest_digest:
        raise ProviderDurableStorageV1Error("provider evidence escrow substitution")

    distinct_regions = source_evidence.observed_region != target_evidence.observed_region
    distinct_principals = source_evidence.principal_arn != target_evidence.principal_arn
    distinct_credentials = (
        source_location.credential_domain_id != target_location.credential_domain_id
    )
    violations: list[str] = []
    if source_evidence.state is not ProviderEvidenceStateV1.VERIFIED:
        violations.append("source_provider_evidence_not_verified")
    if target_evidence.state is not ProviderEvidenceStateV1.VERIFIED:
        violations.append("target_provider_evidence_not_verified")
    if not distinct_regions:
        violations.append("provider_region_collision")
    if not distinct_principals:
        violations.append("provider_principal_collision")
    if not distinct_credentials:
        violations.append("credential_domain_collision")

    return ProviderDurablePairReportV1(
        source_evidence_digest=source_evidence.evidence_digest,
        target_evidence_digest=target_evidence.evidence_digest,
        source_location_digest=source_location.location_digest,
        target_location_digest=target_location.location_digest,
        distinct_regions=distinct_regions,
        distinct_principals=distinct_principals,
        distinct_credential_domains=distinct_credentials,
        state=(ProviderEvidenceStateV1.VERIFIED if not violations else ProviderEvidenceStateV1.FAIL),
        violations=tuple(violations),
    )
