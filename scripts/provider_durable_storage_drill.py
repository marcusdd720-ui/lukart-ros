"""Run the LRD-01H synthetic-only live provider evidence drill.

The runner deliberately has no boto3 package dependency in the Product runtime.
Operators supply boto3 in their external execution environment and use named AWS
profiles whose credentials remain outside the repository.

The drill is split into two phases. ``prepare`` uses source and target to publish,
replicate and capture provider evidence. After the operator makes the source
unavailable and preserves separate evidence of that fact, ``finalize`` instantiates
only the target client and performs the target-only restore verification.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from core.artifact_escrow_v1 import (
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
from core.p3.contracts import canonical_json, content_digest
from core.provider_durable_evidence_bundle_v1 import (
    PROVIDER_EVIDENCE_CAPTURE_SCHEMA_V1,
    PROVIDER_SOURCE_LOSS_DRILL_SCHEMA_V1,
    SYNTHETIC_PROVIDER_DRILL_CASE_ID_V1,
    ProviderDurableEvidenceBundleV1Error,
    ProviderDurableEvidenceCaptureV1,
    ProviderSourceLossDrillEvidenceV1,
)
from core.provider_durable_storage_v1 import (
    AwsS3ObjectLockEscrowBackendV1,
    AwsS3ObjectLockProfileV1,
    build_provider_pair_report_v1,
    verify_s3_location_v1,
)

ROOT = Path(__file__).resolve().parents[1]
OPERATOR_CONFIG_SCHEMA_V1 = "lukart.provider-durable-operator-config.v1"
_LOCATION_CONFIG_KEYS = frozenset(
    {
        "aws_profile",
        "auditor_aws_profile",
        "region",
        "bucket",
        "key_prefix",
        "expected_bucket_owner",
        "credential_domain_id",
        "policy_source_arn",
    }
)
_MAX_EXTERNAL_EVIDENCE_BYTES = 1024 * 1024


class ProviderDrillOperatorError(ValueError):
    """Fail-closed operator configuration or execution error."""


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProviderDrillOperatorError(
            f"{field_name} must be nonblank and already canonical"
        )
    return value


def _mapping(value: object, *, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ProviderDrillOperatorError(f"{field_name} must be an object")
    return cast(Mapping[str, object], value)


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
    raise ProviderDrillOperatorError(
        f"{field_name} key contract violation: missing={missing}; unknown={unknown}"
    )


def _outside_repo(path: Path, *, field_name: str, must_exist: bool) -> Path:
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise ProviderDrillOperatorError(f"{field_name} must not be a symlink")
    resolved = expanded.resolve(strict=must_exist)
    if resolved == ROOT or ROOT in resolved.parents:
        raise ProviderDrillOperatorError(
            f"{field_name} must remain outside the public repository tree"
        )
    return resolved


def _load_json(path: Path, *, field_name: str) -> Mapping[str, object]:
    resolved = _outside_repo(path, field_name=field_name, must_exist=True)
    if not resolved.is_file():
        raise ProviderDrillOperatorError(f"{field_name} must be a regular file")
    try:
        raw: object = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderDrillOperatorError(f"cannot read {field_name}") from exc
    return _mapping(raw, field_name=field_name)


def _write_new_json(path: Path, value: Mapping[str, object]) -> Path:
    resolved = _outside_repo(path, field_name="evidence output", must_exist=False)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.parent.resolve(strict=True)
    if resolved.exists():
        raise ProviderDrillOperatorError("evidence output already exists")
    try:
        with resolved.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(dict(value)))
            handle.write("\n")
    except OSError as exc:
        raise ProviderDrillOperatorError("cannot write evidence output") from exc
    return resolved


@dataclass(frozen=True, slots=True)
class _OperatorLocation:
    aws_profile: str
    auditor_aws_profile: str
    provider_profile: AwsS3ObjectLockProfileV1

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> _OperatorLocation:
        _strict_keys(
            value,
            expected=_LOCATION_CONFIG_KEYS,
            field_name="provider operator location",
        )
        provider = AwsS3ObjectLockProfileV1(
            region=_text(value.get("region"), field_name="region"),
            bucket=_text(value.get("bucket"), field_name="bucket"),
            key_prefix=_text(value.get("key_prefix"), field_name="key_prefix"),
            expected_bucket_owner=_text(
                value.get("expected_bucket_owner"), field_name="expected_bucket_owner"
            ),
            credential_domain_id=_text(
                value.get("credential_domain_id"), field_name="credential_domain_id"
            ),
            policy_source_arn=_text(
                value.get("policy_source_arn"), field_name="policy_source_arn"
            ),
        )
        return cls(
            aws_profile=_text(value.get("aws_profile"), field_name="aws_profile"),
            auditor_aws_profile=_text(
                value.get("auditor_aws_profile"), field_name="auditor_aws_profile"
            ),
            provider_profile=provider,
        )


@dataclass(frozen=True, slots=True)
class _OperatorConfig:
    source: _OperatorLocation
    target: _OperatorLocation

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> _OperatorConfig:
        _strict_keys(
            value,
            expected=frozenset({"schema", "source", "target"}),
            field_name="provider operator config",
        )
        if _text(value.get("schema"), field_name="schema") != OPERATOR_CONFIG_SCHEMA_V1:
            raise ProviderDrillOperatorError("unsupported provider operator config schema")
        result = cls(
            source=_OperatorLocation.from_dict(
                _mapping(value.get("source"), field_name="source")
            ),
            target=_OperatorLocation.from_dict(
                _mapping(value.get("target"), field_name="target")
            ),
        )
        if result.source.aws_profile == result.target.aws_profile:
            raise ProviderDrillOperatorError(
                "source and target storage AWS profiles must be distinct"
            )
        if (
            result.source.provider_profile.credential_domain_id
            == result.target.provider_profile.credential_domain_id
        ):
            raise ProviderDrillOperatorError(
                "source and target credential-domain IDs must be distinct"
            )
        if result.source.provider_profile.region == result.target.provider_profile.region:
            raise ProviderDrillOperatorError(
                "source and target provider regions must be distinct"
            )
        return result


def load_operator_config(path: Path) -> _OperatorConfig:
    return _OperatorConfig.from_dict(_load_json(path, field_name="operator config"))


def _git_identity(expected_sha: str) -> tuple[str, str]:
    if len(expected_sha) != 40 or any(character not in "0123456789abcdef" for character in expected_sha):
        raise ProviderDrillOperatorError("code SHA must be exact lowercase 40-character Git SHA")
    try:
        actual = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        tree = subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ProviderDrillOperatorError("cannot read exact local Git identity") from exc
    if actual != expected_sha:
        raise ProviderDrillOperatorError(
            "local checkout does not match requested exact code SHA"
        )
    if len(tree) != 40 or any(character not in "0123456789abcdef" for character in tree):
        raise ProviderDrillOperatorError("local Git tree identity is malformed")
    return actual, tree


def _load_boto3() -> Any:
    try:
        module = importlib.import_module("boto3")
    except ModuleNotFoundError as exc:
        raise ProviderDrillOperatorError(
            "boto3 is required only in the external provider-drill environment"
        ) from exc
    if not hasattr(module, "Session"):
        raise ProviderDrillOperatorError("loaded boto3 module has no Session API")
    return module


def _provider_clients(
    boto3_module: Any,
    location: _OperatorLocation,
) -> tuple[Any, Any, Any]:
    storage_session = boto3_module.Session(
        profile_name=location.aws_profile,
        region_name=location.provider_profile.region,
    )
    auditor_session = boto3_module.Session(
        profile_name=location.auditor_aws_profile,
        region_name=location.provider_profile.region,
    )
    return (
        storage_session.client("s3", region_name=location.provider_profile.region),
        storage_session.client("sts", region_name=location.provider_profile.region),
        auditor_session.client("iam", region_name=location.provider_profile.region),
    )


def _engineering_capabilities(
    profile: AwsS3ObjectLockProfileV1,
) -> tuple[DurabilityCapabilityEvidenceV1, ...]:
    verified = {
        DurabilityCapabilityV1.EXACT_BYTE_VERIFICATION,
        DurabilityCapabilityV1.IMMUTABLE_PUBLICATION,
    }
    result: list[DurabilityCapabilityEvidenceV1] = []
    for capability in DurabilityCapabilityV1:
        if capability in verified:
            result.append(
                DurabilityCapabilityEvidenceV1(
                    capability=capability,
                    state=CapabilityEvidenceStateV1.VERIFIED,
                    evidence_digest=content_digest(
                        {
                            "stage": "LRD-01H",
                            "aws_profile_digest": profile.profile_digest,
                            "capability": capability.value,
                        }
                    ),
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


def _location(
    provider: AwsS3ObjectLockProfileV1,
    *,
    slot: str,
) -> DurableEscrowLocationV1:
    return DurableEscrowLocationV1.build(
        storage_profile=provider.storage_profile(),
        location_id=f"aws-s3-{slot}:{provider.profile_digest[:16]}",
        failure_domain_id=f"aws-region:{provider.region}",
        credential_domain_id=provider.credential_domain_id,
        capabilities=_engineering_capabilities(provider),
    )


def _synthetic_manifest(
    *,
    code_sha: str,
    code_tree_sha: str,
) -> tuple[ArtifactEscrowManifestV1, dict[ReplayArtifactRole, bytes]]:
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
        code_commit_sha=code_sha,
        code_tree_sha=code_tree_sha,
        artifacts=artifacts,
        semantic_result_identity=logical[ReplayArtifactRole.SEMANTIC_RESULT],
        presentation_identity=None,
    )
    data_by_role = {
        role: (
            f"LRD-01H synthetic provider drill artifact::{role.value}\n"
        ).encode("utf-8")
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


def _publish_source(
    backend: AwsS3ObjectLockEscrowBackendV1,
    manifest: ArtifactEscrowManifestV1,
    data_by_role: Mapping[ReplayArtifactRole, bytes],
    limits: EscrowLimitsV1,
) -> None:
    for binding in manifest.bindings:
        restored = backend.publish(data_by_role[binding.role], limits=limits)
        if restored != binding.blob:
            raise ProviderDrillOperatorError(
                f"source publication changed identity for {binding.role.value}"
            )


def _prepare(args: argparse.Namespace) -> int:
    code_sha, tree_sha = _git_identity(args.code_sha)
    config = load_operator_config(Path(args.config))
    boto3_module = _load_boto3()
    source_s3, source_sts, source_iam = _provider_clients(
        boto3_module, config.source
    )
    target_s3, target_sts, target_iam = _provider_clients(
        boto3_module, config.target
    )
    source_backend = AwsS3ObjectLockEscrowBackendV1(
        s3_client=source_s3,
        profile=config.source.provider_profile,
    )
    target_backend = AwsS3ObjectLockEscrowBackendV1(
        s3_client=target_s3,
        profile=config.target.provider_profile,
    )
    limits = EscrowLimitsV1()
    manifest, data_by_role = _synthetic_manifest(
        code_sha=code_sha,
        code_tree_sha=tree_sha,
    )
    _publish_source(source_backend, manifest, data_by_role, limits)
    source_location = _location(config.source.provider_profile, slot="source")
    target_location = _location(config.target.provider_profile, slot="target")
    plan = build_multi_location_plan_v1(
        expected_case_id=SYNTHETIC_PROVIDER_DRILL_CASE_ID_V1,
        escrow_manifest=manifest,
        source_location=source_location,
        target_location=target_location,
    )
    replication = replicate_escrow_manifest_v1(
        plan=plan,
        escrow_manifest=manifest,
        source_location=source_location,
        target_location=target_location,
        source_backend=source_backend,
        target_backend=target_backend,
        limits=limits,
    )
    observed_at = datetime.now(UTC)
    source_evidence, source_scope = verify_s3_location_v1(
        expected_case_id=SYNTHETIC_PROVIDER_DRILL_CASE_ID_V1,
        escrow_manifest=manifest,
        generic_location=source_location,
        backend=source_backend,
        s3_client=source_s3,
        sts_client=source_sts,
        iam_client=source_iam,
        observed_at=observed_at,
        limits=limits,
    )
    target_evidence, target_scope = verify_s3_location_v1(
        expected_case_id=SYNTHETIC_PROVIDER_DRILL_CASE_ID_V1,
        escrow_manifest=manifest,
        generic_location=target_location,
        backend=target_backend,
        s3_client=target_s3,
        sts_client=target_sts,
        iam_client=target_iam,
        observed_at=observed_at,
        limits=limits,
    )
    pair = build_provider_pair_report_v1(
        source_location=source_location,
        target_location=target_location,
        source_evidence=source_evidence,
        target_evidence=target_evidence,
    )
    capture = ProviderDurableEvidenceCaptureV1(
        code_sha=code_sha,
        case_id=SYNTHETIC_PROVIDER_DRILL_CASE_ID_V1,
        escrow_manifest=manifest,
        source_profile=config.source.provider_profile,
        target_profile=config.target.provider_profile,
        source_location=source_location,
        target_location=target_location,
        source_versions=source_backend.version_bindings(),
        target_versions=target_backend.version_bindings(),
        source_credential_scope=source_scope,
        target_credential_scope=target_scope,
        source_evidence=source_evidence,
        target_evidence=target_evidence,
        plan=plan,
        replication_receipt=replication,
        pair_report=pair,
    )
    output = _write_new_json(Path(args.output), capture.canonical_dict())
    print("LRD-01H PREPARE CAPTURED")
    print("Capture digest:", capture.capture_digest)
    print("Output:", output)
    print("Next: make source unavailable and preserve independent evidence before finalize.")
    return 0


def _external_evidence_digest(path: Path) -> str:
    resolved = _outside_repo(
        path,
        field_name="source-unavailability evidence",
        must_exist=True,
    )
    if not resolved.is_file():
        raise ProviderDrillOperatorError(
            "source-unavailability evidence must be a regular file"
        )
    data = resolved.read_bytes()
    if not data or len(data) > _MAX_EXTERNAL_EVIDENCE_BYTES:
        raise ProviderDrillOperatorError(
            "source-unavailability evidence must be nonempty and at most 1 MiB"
        )
    return hashlib.sha256(data).hexdigest()


def _finalize(args: argparse.Namespace) -> int:
    capture = ProviderDurableEvidenceCaptureV1.from_dict(
        _load_json(Path(args.capture), field_name="provider capture")
    )
    _git_identity(capture.code_sha)
    config = load_operator_config(Path(args.config))
    if config.source.provider_profile != capture.source_profile:
        raise ProviderDrillOperatorError("source config changed since prepare")
    if config.target.provider_profile != capture.target_profile:
        raise ProviderDrillOperatorError("target config changed since prepare")

    # Source clients are deliberately never instantiated in this phase.
    boto3_module = _load_boto3()
    target_s3, target_sts, target_iam = _provider_clients(
        boto3_module, config.target
    )
    target_backend = AwsS3ObjectLockEscrowBackendV1(
        s3_client=target_s3,
        profile=capture.target_profile,
        version_bindings=capture.target_versions,
    )
    limits = EscrowLimitsV1()
    post_loss_target_evidence, post_loss_target_scope = verify_s3_location_v1(
        expected_case_id=capture.case_id,
        escrow_manifest=capture.escrow_manifest,
        generic_location=capture.target_location,
        backend=target_backend,
        s3_client=target_s3,
        sts_client=target_sts,
        iam_client=target_iam,
        observed_at=datetime.now(UTC),
        limits=limits,
    )
    target_restore = verify_location_restore_v1(
        expected_case_id=capture.case_id,
        escrow_manifest=capture.escrow_manifest,
        location=capture.target_location,
        backend=target_backend,
        limits=limits,
    )
    drill = ProviderSourceLossDrillEvidenceV1(
        capture=capture,
        post_loss_target_credential_scope=post_loss_target_scope,
        post_loss_target_evidence=post_loss_target_evidence,
        target_restore=target_restore,
        source_unavailability_evidence_digest=_external_evidence_digest(
            Path(args.source_unavailability_evidence)
        ),
    )
    output = _write_new_json(Path(args.output), drill.canonical_dict())
    print("LRD-01H TARGET-ONLY DRILL CAPTURED")
    print("Drill digest:", drill.drill_digest)
    print("Status:", drill.status.value)
    print("Output:", output)
    print("This is preserved evidence, not automatic LRD-01H closure authority.")
    return 0


def _verify(args: argparse.Namespace) -> int:
    raw = _load_json(Path(args.input), field_name="provider evidence bundle")
    schema = raw.get("schema")
    if schema == PROVIDER_EVIDENCE_CAPTURE_SCHEMA_V1:
        capture = ProviderDurableEvidenceCaptureV1.from_dict(raw)
        print("LRD-01H OFFLINE CAPTURE VERIFY PASS")
        print("Capture digest:", capture.capture_digest)
        return 0
    if schema == PROVIDER_SOURCE_LOSS_DRILL_SCHEMA_V1:
        drill = ProviderSourceLossDrillEvidenceV1.from_dict(raw)
        print("LRD-01H OFFLINE DRILL VERIFY PASS")
        print("Drill digest:", drill.drill_digest)
        print("Status:", drill.status.value)
        return 0
    raise ProviderDrillOperatorError("unsupported provider evidence bundle schema")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="LRD-01H synthetic-only live AWS Object Lock provider drill"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser(
        "prepare",
        help="Publish synthetic bytes, replicate, verify both providers, write capture",
    )
    prepare.add_argument("--config", required=True)
    prepare.add_argument("--code-sha", required=True)
    prepare.add_argument("--output", required=True)

    finalize = subparsers.add_parser(
        "finalize",
        help="After source loss, use target only and bind external source-loss evidence",
    )
    finalize.add_argument("--config", required=True)
    finalize.add_argument("--capture", required=True)
    finalize.add_argument("--source-unavailability-evidence", required=True)
    finalize.add_argument("--output", required=True)

    verify = subparsers.add_parser(
        "verify",
        help="Offline strict verification of a preserved capture or final drill bundle",
    )
    verify.add_argument("--input", required=True)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        if args.command == "prepare":
            return _prepare(args)
        if args.command == "finalize":
            return _finalize(args)
        return _verify(args)
    except (ProviderDrillOperatorError, ProviderDurableEvidenceBundleV1Error) as exc:
        raise SystemExit(f"LRD-01H provider drill rejected: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
