"""LRD-01O immutable replay-revalidation baseline capsule v1.

The capsule preserves the exact evidence required to use a prior verified replay as an
LRD-01M baseline. It is verification-only and reuses ArtifactEscrowBackendV1 for bytes;
backend location is never baseline identity.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from core.artifact_escrow_v1 import (
    ArtifactEscrowBackendV1,
    EscrowBlobIdentityV1,
    EscrowLimitsV1,
)
from core.cross_environment_replay_verifier_v1 import VerificationError, verify_report
from core.p3.contracts import RuntimeIdentity, canonical_json, content_digest, require_hex_digest
from core.replay_revalidation_invalidation_v1 import ReplayRevalidationFingerprintV1

REVALIDATION_BASELINE_SCHEMA_V1 = "lukart.replay-revalidation-baseline.v1"
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ACCEPTABLE_REPLAY_CLASSIFICATIONS = frozenset(
    {
        "EXACT_ENVIRONMENT_REPLAY",
        "CROSS_ENV_SEMANTICALLY_EQUIVALENT",
        "PRESENTATION_ONLY_DRIFT",
    }
)
_RUNTIME_KEYS = frozenset(
    {
        "identity_schema",
        "code_sha",
        "schema_version",
        "config_digest",
        "corpus_digest",
        "provider_identities",
        "plugin_identities",
        "input_digests",
        "evidence_digests",
        "inventories_declared",
        "execution_environment",
    }
)
_DECLARATION_KEYS = frozenset(
    {"providers", "plugins", "inputs", "evidence", "execution_environment"}
)
_EXECUTION_KEYS = frozenset(
    {
        "dependency_lock_digest",
        "python_implementation",
        "python_version",
        "platform_tag",
        "project_version",
        "build_backend",
    }
)
_BASELINE_KEYS = frozenset(
    {
        "schema",
        "repository_sha",
        "replay_repository_sha",
        "runtime_identity",
        "fingerprint",
        "replay_report",
        "replay_report_digest",
        "scheduler_authority",
        "release_authority",
        "product_write_authority",
        "ccl_write_authority",
        "storage_authority",
        "baseline_digest",
    }
)


class ReplayRevalidationBaselineError(ValueError):
    """Fail-closed LRD-01O contract violation."""


def _strict(value: Mapping[str, object], expected: frozenset[str], *, field: str) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = ",".join(sorted(expected - actual)) or "-"
    unknown = ",".join(sorted(actual - expected)) or "-"
    raise ReplayRevalidationBaselineError(
        f"{field} key contract violation: missing={missing}; unknown={unknown}"
    )


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ReplayRevalidationBaselineError(f"{field} must be canonical nonblank text")
    return value


def _digest(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    try:
        normalized = require_hex_digest(text, field_name=field)
    except ValueError as exc:
        raise ReplayRevalidationBaselineError(str(exc)) from exc
    if normalized != text:
        raise ReplayRevalidationBaselineError(f"{field} must be canonical lowercase sha256")
    return normalized


def _git_sha(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _GIT_SHA_RE.fullmatch(text) is None:
        raise ReplayRevalidationBaselineError(f"{field} must be a lowercase full Git SHA")
    return text


def _canonical_mapping(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    if any(not isinstance(key, str) for key in value):
        raise ReplayRevalidationBaselineError(f"{field} keys must be strings")
    try:
        decoded: object = json.loads(canonical_json(dict(value)))
    except (TypeError, ValueError) as exc:
        raise ReplayRevalidationBaselineError(f"{field} is not canonically serializable") from exc
    if not isinstance(decoded, dict):
        raise ReplayRevalidationBaselineError(f"{field} must be an object")
    return cast(dict[str, object], decoded)


def _string_inventory(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ReplayRevalidationBaselineError(f"{field} must be a sequence")
    result = tuple(_text(item, field=field) for item in value)
    if len(result) != len(set(result)):
        raise ReplayRevalidationBaselineError(f"{field} cannot contain duplicates")
    return tuple(sorted(result))


def _bool(mapping: Mapping[str, object], key: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise ReplayRevalidationBaselineError(f"{key} must be boolean")
    return value


def _runtime_from_dict(value: Mapping[str, object]) -> RuntimeIdentity:
    raw = _canonical_mapping(value, field="runtime identity")
    _strict(raw, _RUNTIME_KEYS, field="runtime identity")
    declared_raw = raw.get("inventories_declared")
    execution_raw = raw.get("execution_environment")
    if not isinstance(declared_raw, Mapping) or not isinstance(execution_raw, Mapping):
        raise ReplayRevalidationBaselineError("runtime identity declarations are incomplete")
    declared = cast(Mapping[str, object], declared_raw)
    execution = cast(Mapping[str, object], execution_raw)
    _strict(declared, _DECLARATION_KEYS, field="runtime declarations")
    _strict(execution, _EXECUTION_KEYS, field="runtime execution environment")

    return RuntimeIdentity(
        identity_schema=_text(raw.get("identity_schema"), field="identity_schema"),
        code_sha=_text(raw.get("code_sha"), field="code_sha"),
        schema_version=_text(raw.get("schema_version"), field="schema_version"),
        config_digest=_text(raw.get("config_digest"), field="config_digest"),
        corpus_digest=_text(raw.get("corpus_digest"), field="corpus_digest"),
        provider_identities=_string_inventory(
            raw.get("provider_identities"), field="provider_identities"
        ),
        plugin_identities=_string_inventory(
            raw.get("plugin_identities"), field="plugin_identities"
        ),
        input_digests=_string_inventory(raw.get("input_digests"), field="input_digests"),
        evidence_digests=_string_inventory(
            raw.get("evidence_digests"), field="evidence_digests"
        ),
        provider_inventory_declared=_bool(declared, "providers"),
        plugin_inventory_declared=_bool(declared, "plugins"),
        input_inventory_declared=_bool(declared, "inputs"),
        evidence_inventory_declared=_bool(declared, "evidence"),
        dependency_lock_digest=_text(
            execution.get("dependency_lock_digest"), field="dependency_lock_digest"
        ),
        python_implementation=_text(
            execution.get("python_implementation"), field="python_implementation"
        ),
        python_version=_text(execution.get("python_version"), field="python_version"),
        platform_tag=_text(execution.get("platform_tag"), field="platform_tag"),
        project_version=_text(execution.get("project_version"), field="project_version"),
        build_backend=_text(execution.get("build_backend"), field="build_backend"),
        execution_environment_declared=_bool(declared, "execution_environment"),
    )


def _verify_replay_baseline(
    *,
    report: Mapping[str, object],
    fingerprint: ReplayRevalidationFingerprintV1,
) -> str:
    try:
        report_digest = verify_report(report)
    except VerificationError as exc:
        raise ReplayRevalidationBaselineError(f"invalid LRD-01K replay evidence: {exc}") from exc

    plan = report.get("plan")
    if not isinstance(plan, Mapping):
        raise ReplayRevalidationBaselineError("verified replay report plan is missing")
    expected: tuple[tuple[str, object], ...] = (
        ("lrd01i_bundle_digest", fingerprint.lrd01i_bundle_digest),
        ("ssc02_manifest_digest", fingerprint.ssc02_manifest_digest),
        ("environment_profile_digests", list(fingerprint.environment_profile_digests)),
        ("replay_policy_digest", fingerprint.replay_policy_digest),
        ("migration_registry_digest", fingerprint.migration_registry_digest),
        ("canonicalization_profile_digest", fingerprint.canonicalization_profile_digest),
        ("crypto_profile_digest", fingerprint.crypto_profile_digest),
    )
    for field, identity in expected:
        if plan.get(field) != identity:
            raise ReplayRevalidationBaselineError(
                f"replay report/fingerprint substitution detected: {field}"
            )

    receipts = report.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        raise ReplayRevalidationBaselineError("verified replay report receipts are missing")
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            raise ReplayRevalidationBaselineError("verified replay receipt is malformed")
        if receipt.get("execution_status") != "VERIFIED":
            raise ReplayRevalidationBaselineError("baseline replay execution is not verified")
        classification = receipt.get("classification")
        if classification not in _ACCEPTABLE_REPLAY_CLASSIFICATIONS:
            raise ReplayRevalidationBaselineError(
                f"baseline replay classification is not acceptable: {classification}"
            )
    return report_digest


@dataclass(frozen=True, slots=True)
class ReplayRevalidationBaselineV1:
    """Self-contained verified replay baseline suitable for future LRD-01M comparison."""

    repository_sha: str
    replay_repository_sha: str
    runtime_identity: RuntimeIdentity
    fingerprint: ReplayRevalidationFingerprintV1
    replay_report: dict[str, object]
    replay_report_digest: str
    schema: str = REVALIDATION_BASELINE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != REVALIDATION_BASELINE_SCHEMA_V1:
            raise ReplayRevalidationBaselineError(f"unsupported baseline schema: {self.schema}")
        repository_sha = _git_sha(self.repository_sha, field="repository_sha")
        replay_sha = _git_sha(self.replay_repository_sha, field="replay_repository_sha")
        object.__setattr__(self, "repository_sha", repository_sha)
        object.__setattr__(self, "replay_repository_sha", replay_sha)
        if len(self.runtime_identity.code_sha) != 40:
            raise ReplayRevalidationBaselineError(
                "RuntimeIdentity code_sha must be an exact 40-char repository SHA"
            )
        if self.runtime_identity.code_sha != repository_sha or replay_sha != repository_sha:
            raise ReplayRevalidationBaselineError("baseline repository identity substitution detected")
        if not self.runtime_identity.complete_for_replay:
            missing = ",".join(self.runtime_identity.incomplete_fields()) or "runtime_identity_v3"
            raise ReplayRevalidationBaselineError(
                "baseline RuntimeIdentity must be complete for replay: " + missing
            )
        if self.fingerprint.runtime_identity_digest != self.runtime_identity.digest():
            raise ReplayRevalidationBaselineError("baseline fingerprint RuntimeIdentity mismatch")

        report = _canonical_mapping(self.replay_report, field="replay report")
        object.__setattr__(self, "replay_report", report)
        expected_report_digest = _verify_replay_baseline(
            report=report,
            fingerprint=self.fingerprint,
        )
        supplied_report_digest = _digest(
            self.replay_report_digest,
            field="replay_report_digest",
        )
        if supplied_report_digest != expected_report_digest:
            raise ReplayRevalidationBaselineError("replay_report_digest mismatch")
        object.__setattr__(self, "replay_report_digest", supplied_report_digest)

    @classmethod
    def build(
        cls,
        *,
        repository_sha: str,
        replay_repository_sha: str,
        runtime_identity: RuntimeIdentity,
        fingerprint: ReplayRevalidationFingerprintV1,
        replay_report: Mapping[str, object],
    ) -> ReplayRevalidationBaselineV1:
        report = _canonical_mapping(replay_report, field="replay report")
        try:
            report_digest = verify_report(report)
        except VerificationError as exc:
            raise ReplayRevalidationBaselineError(
                f"invalid LRD-01K replay evidence: {exc}"
            ) from exc
        return cls(
            repository_sha=repository_sha,
            replay_repository_sha=replay_repository_sha,
            runtime_identity=runtime_identity,
            fingerprint=fingerprint,
            replay_report=report,
            replay_report_digest=report_digest,
        )

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "repository_sha": self.repository_sha,
            "replay_repository_sha": self.replay_repository_sha,
            "runtime_identity": self.runtime_identity.canonical_dict(),
            "fingerprint": self.fingerprint.canonical_dict(),
            "replay_report": self.replay_report,
            "replay_report_digest": self.replay_report_digest,
            "scheduler_authority": False,
            "release_authority": False,
            "product_write_authority": False,
            "ccl_write_authority": False,
            "storage_authority": False,
        }

    @property
    def baseline_digest(self) -> str:
        return content_digest(self.body_dict())

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "baseline_digest": self.baseline_digest}

    def canonical_bytes(self) -> bytes:
        return canonical_json(self.canonical_dict()).encode("utf-8")

    def invalidation_inputs(
        self,
    ) -> tuple[ReplayRevalidationFingerprintV1, RuntimeIdentity]:
        return self.fingerprint, self.runtime_identity

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ReplayRevalidationBaselineV1:
        raw = _canonical_mapping(value, field="revalidation baseline")
        _strict(raw, _BASELINE_KEYS, field="revalidation baseline")
        for authority in (
            "scheduler_authority",
            "release_authority",
            "product_write_authority",
            "ccl_write_authority",
            "storage_authority",
        ):
            if raw.get(authority) is not False:
                raise ReplayRevalidationBaselineError(f"{authority} must remain false")
        runtime_raw = raw.get("runtime_identity")
        fingerprint_raw = raw.get("fingerprint")
        report_raw = raw.get("replay_report")
        if not isinstance(runtime_raw, Mapping):
            raise ReplayRevalidationBaselineError("runtime_identity must be an object")
        if not isinstance(fingerprint_raw, Mapping):
            raise ReplayRevalidationBaselineError("fingerprint must be an object")
        if not isinstance(report_raw, Mapping):
            raise ReplayRevalidationBaselineError("replay_report must be an object")
        try:
            fingerprint = ReplayRevalidationFingerprintV1.from_dict(
                cast(Mapping[str, object], fingerprint_raw)
            )
        except ValueError as exc:
            raise ReplayRevalidationBaselineError(
                f"invalid revalidation fingerprint: {exc}"
            ) from exc
        result = cls(
            schema=_text(raw.get("schema"), field="schema"),
            repository_sha=_git_sha(raw.get("repository_sha"), field="repository_sha"),
            replay_repository_sha=_git_sha(
                raw.get("replay_repository_sha"), field="replay_repository_sha"
            ),
            runtime_identity=_runtime_from_dict(cast(Mapping[str, object], runtime_raw)),
            fingerprint=fingerprint,
            replay_report=_canonical_mapping(
                cast(Mapping[str, object], report_raw), field="replay report"
            ),
            replay_report_digest=_digest(
                raw.get("replay_report_digest"), field="replay_report_digest"
            ),
        )
        expected = _digest(raw.get("baseline_digest"), field="baseline_digest")
        if result.baseline_digest != expected:
            raise ReplayRevalidationBaselineError("baseline_digest mismatch")
        if raw != result.canonical_dict():
            raise ReplayRevalidationBaselineError("revalidation baseline is not canonical")
        return result


def publish_revalidation_baseline_v1(
    baseline: ReplayRevalidationBaselineV1,
    *,
    backend: ArtifactEscrowBackendV1,
    limits: EscrowLimitsV1,
) -> EscrowBlobIdentityV1:
    """Publish exact capsule bytes through the existing replaceable escrow byte contract."""
    return backend.publish(baseline.canonical_bytes(), limits=limits)


def restore_revalidation_baseline_v1(
    identity: EscrowBlobIdentityV1,
    *,
    backend: ArtifactEscrowBackendV1,
    limits: EscrowLimitsV1,
) -> ReplayRevalidationBaselineV1:
    """Read, byte-verify and parse one exact baseline capsule from existing escrow storage."""
    data = backend.read(identity, limits=limits)
    try:
        decoded: object = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplayRevalidationBaselineError("baseline capsule bytes are not valid UTF-8 JSON") from exc
    if not isinstance(decoded, Mapping):
        raise ReplayRevalidationBaselineError("baseline capsule root must be an object")
    result = ReplayRevalidationBaselineV1.from_dict(cast(Mapping[str, object], decoded))
    if data != result.canonical_bytes():
        raise ReplayRevalidationBaselineError("baseline capsule bytes are not canonical")
    return result
