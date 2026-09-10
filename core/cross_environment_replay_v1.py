"""LRD-01K cross-environment replay provenance and verification contracts v1.

Verification-only composition over LRD-01I/SSC-02 identities and LRD-01D semantic
classification. This module creates no Product, CCL, Gold, policy, trust-root,
release, dependency-resolution, migration, crypto, or semantic-comparison authority.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import locale
import os
import platform
import re
import sqlite3
import ssl
import sys
import sysconfig
import tempfile
import time
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import cast

ENVIRONMENT_PROFILE_SCHEMA_V1 = "lukart.execution-environment-profile.v1"
OBSERVED_ENVIRONMENT_SCHEMA_V1 = "lukart.observed-environment-receipt.v1"
REPLAY_PLAN_SCHEMA_V1 = "lukart.cross-environment-replay-plan.v1"
REPLAY_RECEIPT_SCHEMA_V1 = "lukart.cross-environment-replay-receipt.v1"
REPLAY_REPORT_SCHEMA_V1 = "lukart.cross-environment-replay-report.v1"
OCI_CAPSULE_SCHEMA_V1 = "lukart.frozen-oci-execution-capsule.v1"
ENVIRONMENT_POLICY_SCHEMA_V1 = "lukart.lrd01k-environment-policy.v1"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SUPPORTED_PYTHON_MIN = (3, 11)
_SUPPORTED_PYTHON_MAX_EXCLUSIVE = (3, 15)
_LRD01D_CLASSIFICATIONS = frozenset(
    {"NO_DRIFT", "PRESENTATION_ONLY", "SEMANTIC_DRIFT", "UNVERIFIABLE", "ABSTAIN"}
)


class CrossEnvironmentReplayError(ValueError):
    """Fail-closed LRD-01K contract violation."""


class EnvironmentFieldClass(StrEnum):
    REQUIRED_COMPATIBILITY = "REQUIRED_COMPATIBILITY"
    OBSERVED_PROVENANCE = "OBSERVED_PROVENANCE"
    NON_SEMANTIC = "NON_SEMANTIC"


class CrossEnvironmentReplayClassification(StrEnum):
    EXACT_ENVIRONMENT_REPLAY = "EXACT_ENVIRONMENT_REPLAY"
    CROSS_ENV_SEMANTICALLY_EQUIVALENT = "CROSS_ENV_SEMANTICALLY_EQUIVALENT"
    PRESENTATION_ONLY_DRIFT = "PRESENTATION_ONLY_DRIFT"
    SEMANTIC_DRIFT = "SEMANTIC_DRIFT"
    ENVIRONMENT_INCOMPATIBLE = "ENVIRONMENT_INCOMPATIBLE"
    UNVERIFIABLE = "UNVERIFIABLE"


class ReplayExecutionStatus(StrEnum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    UNVERIFIABLE = "UNVERIFIABLE"
    INCOMPATIBLE = "INCOMPATIBLE"


_EXPECTED_FIELD_CLASSES = {
    "name": EnvironmentFieldClass.NON_SEMANTIC.value,
    "os_family": EnvironmentFieldClass.REQUIRED_COMPATIBILITY.value,
    "os_release": EnvironmentFieldClass.OBSERVED_PROVENANCE.value,
    "os_build": EnvironmentFieldClass.OBSERVED_PROVENANCE.value,
    "cpu_architecture": EnvironmentFieldClass.REQUIRED_COMPATIBILITY.value,
    "python_implementation": EnvironmentFieldClass.REQUIRED_COMPATIBILITY.value,
    "python_version": EnvironmentFieldClass.REQUIRED_COMPATIBILITY.value,
    "python_cache_tag": EnvironmentFieldClass.REQUIRED_COMPATIBILITY.value,
    "python_soabi": EnvironmentFieldClass.REQUIRED_COMPATIBILITY.value,
    "openssl_identity": EnvironmentFieldClass.OBSERVED_PROVENANCE.value,
    "sqlite_identity": EnvironmentFieldClass.OBSERVED_PROVENANCE.value,
    "libc_runtime_identity": EnvironmentFieldClass.OBSERVED_PROVENANCE.value,
    "locale": EnvironmentFieldClass.NON_SEMANTIC.value,
    "timezone": EnvironmentFieldClass.NON_SEMANTIC.value,
    "filesystem_semantics": EnvironmentFieldClass.OBSERVED_PROVENANCE.value,
    "dependency_lock_digest": EnvironmentFieldClass.REQUIRED_COMPATIBILITY.value,
    "physical_dependency_artifact_identities": (
        EnvironmentFieldClass.REQUIRED_COMPATIBILITY.value
    ),
    "canonicalization_profile_digest": EnvironmentFieldClass.REQUIRED_COMPATIBILITY.value,
    "migration_registry_digest": EnvironmentFieldClass.REQUIRED_COMPATIBILITY.value,
    "crypto_profile_digest": EnvironmentFieldClass.REQUIRED_COMPATIBILITY.value,
    "lrd01i_bundle_digest": EnvironmentFieldClass.REQUIRED_COMPATIBILITY.value,
    "replay_verifier_digest": EnvironmentFieldClass.REQUIRED_COMPATIBILITY.value,
    "environment_policy_digest": EnvironmentFieldClass.REQUIRED_COMPATIBILITY.value,
}

_SNAPSHOT_KEYS = frozenset(
    {
        "os_family",
        "os_release",
        "os_build",
        "cpu_architecture",
        "python_implementation",
        "python_version",
        "python_cache_tag",
        "python_soabi",
        "openssl_identity",
        "sqlite_identity",
        "libc_runtime_identity",
        "locale",
        "timezone",
        "filesystem_semantics",
        "installed_artifacts",
        "installed_artifact_inventory_digest",
    }
)
_PROFILE_KEYS = frozenset(
    {
        "schema",
        *_SNAPSHOT_KEYS - {"installed_artifacts", "installed_artifact_inventory_digest"},
        "name",
        "dependency_lock_digest",
        "physical_dependency_artifact_identities",
        "canonicalization_profile_digest",
        "migration_registry_digest",
        "crypto_profile_digest",
        "lrd01i_bundle_digest",
        "replay_verifier_digest",
        "environment_policy_digest",
        "field_classes",
        "profile_digest",
    }
)
_OBSERVED_KEYS = frozenset(
    {
        "schema",
        *_SNAPSHOT_KEYS,
        "declared_profile_digest",
        "verifier_digest",
        "environment_policy_digest",
        "observed_environment_digest",
    }
)
_PLAN_KEYS = frozenset(
    {
        "schema",
        "lrd01i_bundle_digest",
        "ssc02_manifest_digest",
        "environment_profile_digests",
        "reference_profile_digest",
        "replay_policy_digest",
        "migration_registry_digest",
        "canonicalization_profile_digest",
        "crypto_profile_digest",
        "expected_matrix",
        "hard_bounds",
        "plan_digest",
    }
)
_RECEIPT_KEYS = frozenset(
    {
        "schema",
        "plan_digest",
        "lrd01i_bundle_digest",
        "ssc02_manifest_digest",
        "environment_profile_digest",
        "observed_environment_digest",
        "replay_policy_digest",
        "migration_registry_digest",
        "canonicalization_profile_digest",
        "crypto_profile_digest",
        "verifier_digest",
        "execution_status",
        "semantic_result_identity",
        "invariant_report_identity",
        "lrd01d_classification",
        "classification",
        "network_mode",
        "ccl_write_authority",
        "product_write_authority",
        "failure_status",
        "receipt_digest",
    }
)


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def digest_value(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise CrossEnvironmentReplayError(f"{field} must be lowercase sha256")
    return value


def _optional_digest(value: object, *, field: str) -> str | None:
    return None if value is None else _digest(value, field=field)


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise CrossEnvironmentReplayError(f"{field} must be a canonical nonblank string")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CrossEnvironmentReplayError(f"{field} contains control characters")
    return value


def _strict(value: Mapping[str, object], expected: frozenset[str], *, field: str) -> None:
    if set(value) != expected:
        missing = ",".join(sorted(expected - set(value))) or "-"
        unknown = ",".join(sorted(set(value) - expected)) or "-"
        raise CrossEnvironmentReplayError(
            f"{field} fields mismatch: missing={missing}; unknown={unknown}"
        )


def _canonical_copy(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    if any(not isinstance(key, str) for key in value):
        raise CrossEnvironmentReplayError(f"{field} keys must be strings")
    try:
        loaded = json.loads(canonical_json_bytes(dict(value)))
    except (TypeError, ValueError) as exc:
        raise CrossEnvironmentReplayError(f"{field} is not canonically serializable") from exc
    if not isinstance(loaded, dict):
        raise CrossEnvironmentReplayError(f"{field} must be an object")
    return cast(dict[str, object], loaded)


def _verify_identity(value: Mapping[str, object], identity_field: str) -> str:
    observed = _digest(value.get(identity_field), field=identity_field)
    body = dict(value)
    body.pop(identity_field, None)
    if digest_value(body) != observed:
        raise CrossEnvironmentReplayError(f"{identity_field} mismatch")
    return observed


def _filesystem_semantics(root: Path) -> dict[str, object]:
    probe = root / "CaseProbe"
    probe.write_text("x", encoding="utf-8")
    return {
        "os_name": os.name,
        "path_separator": os.sep,
        "alt_separator": os.altsep,
        "case_sensitive_probe": not (root / "caseprobe").exists(),
        "supports_symlinks": hasattr(os, "symlink"),
    }


def _installed_artifact_inventory() -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    for distribution in importlib.metadata.distributions():
        metadata = cast(Mapping[str, str], distribution.metadata)
        name = metadata.get("Name") or "UNKNOWN"
        version = distribution.version or "UNKNOWN"
        files = distribution.files or []
        physical_files: list[dict[str, str]] = []
        for relative in sorted(files, key=lambda item: str(item).replace("\\", "/")):
            absolute = Path(str(distribution.locate_file(relative)))
            try:
                if absolute.is_symlink() or not absolute.is_file():
                    continue
                physical_files.append(
                    {
                        "path": str(relative).replace("\\", "/"),
                        "sha256": sha256_file(absolute),
                    }
                )
            except OSError as exc:
                raise CrossEnvironmentReplayError(
                    f"cannot hash installed artifact file for {name}"
                ) from exc
        records.append(
            {
                "name": str(name),
                "version": str(version),
                "physical_files_digest": digest_value(physical_files),
                "file_count": len(physical_files),
            }
        )
    records.sort(key=lambda item: (str(item["name"]).lower(), str(item["version"])))
    return tuple(records)


def capture_environment_snapshot() -> dict[str, object]:
    """Capture actual runtime facts without granting those observations authority."""
    with tempfile.TemporaryDirectory(prefix="lrd01k-fs-") as temporary:
        filesystem = _filesystem_semantics(Path(temporary))
    inventory = list(_installed_artifact_inventory())
    libc_name, libc_version = platform.libc_ver()
    return {
        "os_family": platform.system() or "UNKNOWN",
        "os_release": platform.release() or "UNKNOWN",
        "os_build": platform.version() or "UNKNOWN",
        "cpu_architecture": platform.machine() or "UNKNOWN",
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_cache_tag": sys.implementation.cache_tag or "UNKNOWN",
        "python_soabi": sysconfig.get_config_var("SOABI") or "UNKNOWN",
        "openssl_identity": ssl.OPENSSL_VERSION,
        "sqlite_identity": sqlite3.sqlite_version,
        "libc_runtime_identity": (
            f"{libc_name}:{libc_version}" if libc_name else "NOT_APPLICABLE"
        ),
        "locale": locale.setlocale(locale.LC_CTYPE),
        "timezone": os.environ.get("TZ") or "/".join(time.tzname),
        "filesystem_semantics": filesystem,
        "installed_artifacts": inventory,
        "installed_artifact_inventory_digest": digest_value(inventory),
    }


def _verify_snapshot(value: Mapping[str, object]) -> dict[str, object]:
    raw = _canonical_copy(value, field="environment snapshot")
    _strict(raw, _SNAPSHOT_KEYS, field="environment snapshot")
    for key in (
        "os_family",
        "os_release",
        "os_build",
        "cpu_architecture",
        "python_implementation",
        "python_version",
        "python_cache_tag",
        "python_soabi",
        "openssl_identity",
        "sqlite_identity",
        "libc_runtime_identity",
        "locale",
        "timezone",
    ):
        _text(raw.get(key), field=key)
    if not isinstance(raw.get("filesystem_semantics"), dict):
        raise CrossEnvironmentReplayError("filesystem_semantics must be an object")
    inventory = raw.get("installed_artifacts")
    if not isinstance(inventory, list):
        raise CrossEnvironmentReplayError("installed_artifacts must be an array")
    if digest_value(inventory) != _digest(
        raw.get("installed_artifact_inventory_digest"),
        field="installed_artifact_inventory_digest",
    ):
        raise CrossEnvironmentReplayError("installed artifact inventory substitution detected")
    return raw


def build_observed_environment_receipt(
    snapshot: Mapping[str, object],
    *,
    declared_profile_digest: str,
    verifier_digest: str,
    environment_policy_digest: str,
) -> dict[str, object]:
    raw = _verify_snapshot(snapshot)
    body: dict[str, object] = {
        "schema": OBSERVED_ENVIRONMENT_SCHEMA_V1,
        **raw,
        "declared_profile_digest": _digest(
            declared_profile_digest,
            field="declared_profile_digest",
        ),
        "verifier_digest": _digest(verifier_digest, field="verifier_digest"),
        "environment_policy_digest": _digest(
            environment_policy_digest,
            field="environment_policy_digest",
        ),
    }
    body["observed_environment_digest"] = digest_value(body)
    return body


def observe_environment(
    *,
    declared_profile_digest: str,
    verifier_digest: str,
    environment_policy_digest: str,
) -> dict[str, object]:
    return build_observed_environment_receipt(
        capture_environment_snapshot(),
        declared_profile_digest=declared_profile_digest,
        verifier_digest=verifier_digest,
        environment_policy_digest=environment_policy_digest,
    )


def build_environment_profile(
    *,
    name: str,
    observed: Mapping[str, object],
    dependency_lock_digest: str,
    physical_dependency_artifact_identities: Sequence[str],
    canonicalization_profile_digest: str,
    migration_registry_digest: str,
    crypto_profile_digest: str,
    lrd01i_bundle_digest: str,
    replay_verifier_digest: str,
    environment_policy_digest: str,
) -> dict[str, object]:
    snapshot = _verify_snapshot(observed)
    physical = sorted(
        {
            _digest(value, field="physical_dependency_artifact_identity")
            for value in physical_dependency_artifact_identities
        }
    )
    if not physical:
        raise CrossEnvironmentReplayError("physical dependency artifact identities are required")
    body: dict[str, object] = {
        "schema": ENVIRONMENT_PROFILE_SCHEMA_V1,
        "name": _text(name, field="name"),
        **{
            key: snapshot[key]
            for key in _SNAPSHOT_KEYS
            if key not in {"installed_artifacts", "installed_artifact_inventory_digest"}
        },
        "dependency_lock_digest": _digest(
            dependency_lock_digest,
            field="dependency_lock_digest",
        ),
        "physical_dependency_artifact_identities": physical,
        "canonicalization_profile_digest": _digest(
            canonicalization_profile_digest,
            field="canonicalization_profile_digest",
        ),
        "migration_registry_digest": _digest(
            migration_registry_digest,
            field="migration_registry_digest",
        ),
        "crypto_profile_digest": _digest(crypto_profile_digest, field="crypto_profile_digest"),
        "lrd01i_bundle_digest": _digest(lrd01i_bundle_digest, field="lrd01i_bundle_digest"),
        "replay_verifier_digest": _digest(
            replay_verifier_digest,
            field="replay_verifier_digest",
        ),
        "environment_policy_digest": _digest(
            environment_policy_digest,
            field="environment_policy_digest",
        ),
        "field_classes": dict(_EXPECTED_FIELD_CLASSES),
    }
    body["profile_digest"] = digest_value(body)
    verify_environment_profile(body)
    return body


def verify_environment_profile(value: Mapping[str, object]) -> str:
    raw = _canonical_copy(value, field="environment profile")
    _strict(raw, _PROFILE_KEYS, field="environment profile")
    if raw.get("schema") != ENVIRONMENT_PROFILE_SCHEMA_V1:
        raise CrossEnvironmentReplayError("unsupported environment profile schema")
    for key in (
        "name",
        "os_family",
        "os_release",
        "os_build",
        "cpu_architecture",
        "python_implementation",
        "python_version",
        "python_cache_tag",
        "python_soabi",
        "openssl_identity",
        "sqlite_identity",
        "libc_runtime_identity",
        "locale",
        "timezone",
    ):
        _text(raw.get(key), field=key)
    if not isinstance(raw.get("filesystem_semantics"), dict):
        raise CrossEnvironmentReplayError("filesystem_semantics must be an object")
    for key in (
        "dependency_lock_digest",
        "canonicalization_profile_digest",
        "migration_registry_digest",
        "crypto_profile_digest",
        "lrd01i_bundle_digest",
        "replay_verifier_digest",
        "environment_policy_digest",
    ):
        _digest(raw.get(key), field=key)
    physical = raw.get("physical_dependency_artifact_identities")
    if (
        not isinstance(physical, list)
        or not physical
        or physical != sorted(set(physical))
    ):
        raise CrossEnvironmentReplayError(
            "physical dependency artifact identities must be unique/sorted"
        )
    for identity in physical:
        _digest(identity, field="physical_dependency_artifact_identity")
    classes = raw.get("field_classes")
    if not isinstance(classes, dict):
        raise CrossEnvironmentReplayError("field_classes must be an object")
    if set(classes) != set(_EXPECTED_FIELD_CLASSES):
        raise CrossEnvironmentReplayError("field_classes coverage mismatch")
    for field_class in classes.values():
        try:
            EnvironmentFieldClass(str(field_class))
        except ValueError as exc:
            raise CrossEnvironmentReplayError("unknown environment field class") from exc
    if classes != _EXPECTED_FIELD_CLASSES:
        raise CrossEnvironmentReplayError("environment field class mapping mismatch")
    return _verify_identity(raw, "profile_digest")


def verify_observed_environment(value: Mapping[str, object]) -> str:
    raw = _canonical_copy(value, field="observed environment")
    _strict(raw, _OBSERVED_KEYS, field="observed environment")
    if raw.get("schema") != OBSERVED_ENVIRONMENT_SCHEMA_V1:
        raise CrossEnvironmentReplayError("unsupported observed environment schema")
    snapshot = {key: raw[key] for key in _SNAPSHOT_KEYS}
    _verify_snapshot(snapshot)
    for key in ("declared_profile_digest", "verifier_digest", "environment_policy_digest"):
        _digest(raw.get(key), field=key)
    return _verify_identity(raw, "observed_environment_digest")


def _python_supported(version_text: object) -> bool:
    if not isinstance(version_text, str):
        return False
    try:
        parts = tuple(int(part) for part in version_text.split(".")[:2])
    except ValueError:
        return False
    return _SUPPORTED_PYTHON_MIN <= parts < _SUPPORTED_PYTHON_MAX_EXCLUSIVE


def environment_compatible(
    profile: Mapping[str, object],
    observed: Mapping[str, object],
) -> bool:
    verify_environment_profile(profile)
    verify_observed_environment(observed)
    for key in (
        "os_family",
        "cpu_architecture",
        "python_implementation",
        "python_version",
        "python_cache_tag",
        "python_soabi",
    ):
        if profile.get(key) != observed.get(key):
            return False
    physical = profile.get("physical_dependency_artifact_identities")
    if not isinstance(physical, list):
        return False
    if observed.get("installed_artifact_inventory_digest") not in physical:
        return False
    return _python_supported(observed.get("python_version"))


def classify_from_lrd01d(
    *,
    lrd01d_classification: str,
    compatible: bool,
    evidence_complete: bool,
    profile_digest: str,
    reference_profile_digest: str,
) -> CrossEnvironmentReplayClassification:
    """Map LRD-01D evidence; never recompute semantic truth."""
    if lrd01d_classification not in _LRD01D_CLASSIFICATIONS:
        raise CrossEnvironmentReplayError("unknown LRD-01D classification")
    if not evidence_complete or lrd01d_classification in {"UNVERIFIABLE", "ABSTAIN"}:
        return CrossEnvironmentReplayClassification.UNVERIFIABLE
    if not compatible:
        return CrossEnvironmentReplayClassification.ENVIRONMENT_INCOMPATIBLE
    if lrd01d_classification == "SEMANTIC_DRIFT":
        return CrossEnvironmentReplayClassification.SEMANTIC_DRIFT
    if lrd01d_classification == "PRESENTATION_ONLY":
        return CrossEnvironmentReplayClassification.PRESENTATION_ONLY_DRIFT
    _digest(profile_digest, field="profile_digest")
    _digest(reference_profile_digest, field="reference_profile_digest")
    if profile_digest == reference_profile_digest:
        return CrossEnvironmentReplayClassification.EXACT_ENVIRONMENT_REPLAY
    return CrossEnvironmentReplayClassification.CROSS_ENV_SEMANTICALLY_EQUIVALENT


def verify_replay_plan(value: Mapping[str, object]) -> str:
    raw = _canonical_copy(value, field="replay plan")
    _strict(raw, _PLAN_KEYS, field="replay plan")
    if raw.get("schema") != REPLAY_PLAN_SCHEMA_V1:
        raise CrossEnvironmentReplayError("unsupported replay plan schema")
    for key in (
        "lrd01i_bundle_digest",
        "ssc02_manifest_digest",
        "reference_profile_digest",
        "replay_policy_digest",
        "migration_registry_digest",
        "canonicalization_profile_digest",
        "crypto_profile_digest",
    ):
        _digest(raw.get(key), field=key)
    profiles = raw.get("environment_profile_digests")
    matrix = raw.get("expected_matrix")
    if (
        not isinstance(profiles, list)
        or len(profiles) < 2
        or profiles != sorted(set(profiles))
        or not isinstance(matrix, list)
        or matrix != profiles
    ):
        raise CrossEnvironmentReplayError("replay plan matrix is invalid")
    for identity in profiles:
        _digest(identity, field="environment_profile_digest")
    if raw.get("reference_profile_digest") not in profiles:
        raise CrossEnvironmentReplayError("reference profile is outside replay matrix")
    if not isinstance(raw.get("hard_bounds"), dict):
        raise CrossEnvironmentReplayError("hard_bounds must be an object")
    return _verify_identity(raw, "plan_digest")


def build_replay_plan(
    *,
    lrd01i_bundle_digest: str,
    ssc02_manifest_digest: str,
    environment_profile_digests: Sequence[str],
    reference_profile_digest: str,
    replay_policy_digest: str,
    migration_registry_digest: str,
    canonicalization_profile_digest: str,
    crypto_profile_digest: str,
    expected_matrix: Sequence[str],
    hard_bounds: Mapping[str, object],
) -> dict[str, object]:
    profiles = sorted(set(environment_profile_digests))
    matrix = sorted(set(expected_matrix))
    if len(profiles) < 2 or matrix != profiles:
        raise CrossEnvironmentReplayError(
            "replay plan requires a complete multi-environment matrix"
        )
    if reference_profile_digest not in profiles:
        raise CrossEnvironmentReplayError("reference profile must belong to matrix")
    body: dict[str, object] = {
        "schema": REPLAY_PLAN_SCHEMA_V1,
        "lrd01i_bundle_digest": _digest(lrd01i_bundle_digest, field="lrd01i_bundle_digest"),
        "ssc02_manifest_digest": _digest(ssc02_manifest_digest, field="ssc02_manifest_digest"),
        "environment_profile_digests": profiles,
        "reference_profile_digest": _digest(
            reference_profile_digest,
            field="reference_profile_digest",
        ),
        "replay_policy_digest": _digest(replay_policy_digest, field="replay_policy_digest"),
        "migration_registry_digest": _digest(
            migration_registry_digest,
            field="migration_registry_digest",
        ),
        "canonicalization_profile_digest": _digest(
            canonicalization_profile_digest,
            field="canonicalization_profile_digest",
        ),
        "crypto_profile_digest": _digest(crypto_profile_digest, field="crypto_profile_digest"),
        "expected_matrix": matrix,
        "hard_bounds": _canonical_copy(hard_bounds, field="hard_bounds"),
    }
    body["plan_digest"] = digest_value(body)
    verify_replay_plan(body)
    return body


def verify_replay_receipt(value: Mapping[str, object]) -> str:
    raw = _canonical_copy(value, field="replay receipt")
    _strict(raw, _RECEIPT_KEYS, field="replay receipt")
    if raw.get("schema") != REPLAY_RECEIPT_SCHEMA_V1:
        raise CrossEnvironmentReplayError("unsupported replay receipt schema")
    for key in (
        "plan_digest",
        "lrd01i_bundle_digest",
        "ssc02_manifest_digest",
        "environment_profile_digest",
        "observed_environment_digest",
        "replay_policy_digest",
        "migration_registry_digest",
        "canonicalization_profile_digest",
        "crypto_profile_digest",
        "verifier_digest",
    ):
        _digest(raw.get(key), field=key)
    semantic = _optional_digest(
        raw.get("semantic_result_identity"),
        field="semantic_result_identity",
    )
    invariants = _optional_digest(
        raw.get("invariant_report_identity"),
        field="invariant_report_identity",
    )
    try:
        status = ReplayExecutionStatus(_text(raw.get("execution_status"), field="execution_status"))
        classification = CrossEnvironmentReplayClassification(
            _text(raw.get("classification"), field="classification")
        )
    except ValueError as exc:
        raise CrossEnvironmentReplayError("unknown replay status/classification") from exc
    lrd01d = _text(raw.get("lrd01d_classification"), field="lrd01d_classification")
    if lrd01d not in _LRD01D_CLASSIFICATIONS:
        raise CrossEnvironmentReplayError("unknown LRD-01D classification")
    if raw.get("network_mode") != "DENY":
        raise CrossEnvironmentReplayError("offline replay network mode must be DENY")
    if raw.get("ccl_write_authority") is not False:
        raise CrossEnvironmentReplayError("replay receipt grants forbidden CCL write authority")
    if raw.get("product_write_authority") is not False:
        raise CrossEnvironmentReplayError("replay receipt grants forbidden Product write authority")
    failure = raw.get("failure_status")
    if failure is not None:
        _text(failure, field="failure_status")
    if status is ReplayExecutionStatus.VERIFIED and failure is not None:
        raise CrossEnvironmentReplayError("verified receipt cannot contain failure status")
    if (
        semantic is None or invariants is None
    ) and classification is not CrossEnvironmentReplayClassification.UNVERIFIABLE:
        raise CrossEnvironmentReplayError("missing comparison evidence must be UNVERIFIABLE")
    return _verify_identity(raw, "receipt_digest")


def build_replay_receipt(
    *,
    plan: Mapping[str, object],
    profile: Mapping[str, object],
    observed: Mapping[str, object],
    verifier_digest: str,
    semantic_result_identity: str | None,
    invariant_report_identity: str | None,
    lrd01d_classification: str,
    execution_status: ReplayExecutionStatus,
    failure_status: str | None = None,
) -> dict[str, object]:
    plan_digest = verify_replay_plan(plan)
    profile_digest = verify_environment_profile(profile)
    observed_digest = verify_observed_environment(observed)
    plan_profiles = plan.get("environment_profile_digests")
    if not isinstance(plan_profiles, list) or profile_digest not in plan_profiles:
        raise CrossEnvironmentReplayError("environment-profile substitution detected")
    for key in (
        "lrd01i_bundle_digest",
        "migration_registry_digest",
        "canonicalization_profile_digest",
        "crypto_profile_digest",
    ):
        if profile.get(key) != plan.get(key):
            raise CrossEnvironmentReplayError(f"{key} substitution detected")
    if observed.get("declared_profile_digest") != profile_digest:
        raise CrossEnvironmentReplayError("observed-environment/profile substitution detected")
    if observed.get("verifier_digest") != verifier_digest:
        raise CrossEnvironmentReplayError("observed verifier substitution detected")
    if observed.get("environment_policy_digest") != profile.get("environment_policy_digest"):
        raise CrossEnvironmentReplayError("observed environment-policy substitution detected")
    compatible = environment_compatible(profile, observed)
    evidence_complete = (
        execution_status is ReplayExecutionStatus.VERIFIED
        and semantic_result_identity is not None
        and invariant_report_identity is not None
    )
    classification = classify_from_lrd01d(
        lrd01d_classification=lrd01d_classification,
        compatible=compatible,
        evidence_complete=evidence_complete,
        profile_digest=profile_digest,
        reference_profile_digest=str(plan.get("reference_profile_digest")),
    )
    if execution_status is ReplayExecutionStatus.INCOMPATIBLE and compatible:
        raise CrossEnvironmentReplayError("incompatible execution status contradicts environment")
    if execution_status is ReplayExecutionStatus.VERIFIED and not compatible:
        raise CrossEnvironmentReplayError("verified execution contradicts incompatible environment")
    if execution_status is ReplayExecutionStatus.VERIFIED and failure_status is not None:
        raise CrossEnvironmentReplayError("verified receipt cannot contain failure status")
    body: dict[str, object] = {
        "schema": REPLAY_RECEIPT_SCHEMA_V1,
        "plan_digest": plan_digest,
        "lrd01i_bundle_digest": plan["lrd01i_bundle_digest"],
        "ssc02_manifest_digest": plan["ssc02_manifest_digest"],
        "environment_profile_digest": profile_digest,
        "observed_environment_digest": observed_digest,
        "replay_policy_digest": plan["replay_policy_digest"],
        "migration_registry_digest": plan["migration_registry_digest"],
        "canonicalization_profile_digest": plan["canonicalization_profile_digest"],
        "crypto_profile_digest": plan["crypto_profile_digest"],
        "verifier_digest": _digest(verifier_digest, field="verifier_digest"),
        "execution_status": execution_status.value,
        "semantic_result_identity": _optional_digest(
            semantic_result_identity,
            field="semantic_result_identity",
        ),
        "invariant_report_identity": _optional_digest(
            invariant_report_identity,
            field="invariant_report_identity",
        ),
        "lrd01d_classification": lrd01d_classification,
        "classification": classification.value,
        "network_mode": "DENY",
        "ccl_write_authority": False,
        "product_write_authority": False,
        "failure_status": failure_status,
    }
    body["receipt_digest"] = digest_value(body)
    verify_replay_receipt(body)
    return body


def _validate_report_receipt(
    *,
    receipt: Mapping[str, object],
    plan: Mapping[str, object],
    profile: Mapping[str, object],
    observed: Mapping[str, object],
) -> None:
    for key in (
        "lrd01i_bundle_digest",
        "ssc02_manifest_digest",
        "replay_policy_digest",
        "migration_registry_digest",
        "canonicalization_profile_digest",
        "crypto_profile_digest",
    ):
        if receipt.get(key) != plan.get(key):
            raise CrossEnvironmentReplayError(f"{key} report binding mismatch")
    if receipt.get("verifier_digest") != profile.get("replay_verifier_digest"):
        raise CrossEnvironmentReplayError("receipt verifier/profile binding mismatch")
    if observed.get("verifier_digest") != receipt.get("verifier_digest"):
        raise CrossEnvironmentReplayError("observed verifier/receipt binding mismatch")
    if observed.get("environment_policy_digest") != profile.get("environment_policy_digest"):
        raise CrossEnvironmentReplayError("observed environment-policy/profile mismatch")
    execution_status = ReplayExecutionStatus(str(receipt.get("execution_status")))
    evidence_complete = (
        execution_status is ReplayExecutionStatus.VERIFIED
        and receipt.get("semantic_result_identity") is not None
        and receipt.get("invariant_report_identity") is not None
    )
    expected = classify_from_lrd01d(
        lrd01d_classification=str(receipt.get("lrd01d_classification")),
        compatible=environment_compatible(profile, observed),
        evidence_complete=evidence_complete,
        profile_digest=str(receipt.get("environment_profile_digest")),
        reference_profile_digest=str(plan.get("reference_profile_digest")),
    ).value
    if receipt.get("classification") != expected:
        raise CrossEnvironmentReplayError("replay receipt classification mismatch")


def build_replay_report(
    *,
    plan: Mapping[str, object],
    profiles: Sequence[Mapping[str, object]],
    observed_environments: Sequence[Mapping[str, object]],
    receipts: Sequence[Mapping[str, object]],
    supersedes: str | None = None,
) -> dict[str, object]:
    plan_digest = verify_replay_plan(plan)
    profile_map: dict[str, dict[str, object]] = {}
    observed_map: dict[str, dict[str, object]] = {}
    receipt_map: dict[str, dict[str, object]] = {}
    for profile in profiles:
        identity = verify_environment_profile(profile)
        if identity in profile_map:
            raise CrossEnvironmentReplayError("duplicated environment profile")
        profile_map[identity] = dict(profile)
    for observed in observed_environments:
        identity = verify_observed_environment(observed)
        if identity in observed_map:
            raise CrossEnvironmentReplayError("duplicated observed environment")
        observed_map[identity] = dict(observed)
    for receipt in receipts:
        identity = verify_replay_receipt(receipt)
        if identity in receipt_map:
            raise CrossEnvironmentReplayError("duplicated replay receipt")
        if receipt.get("plan_digest") != plan_digest:
            raise CrossEnvironmentReplayError("cross-plan receipt substitution detected")
        profile_id = str(receipt.get("environment_profile_digest"))
        observed_id = str(receipt.get("observed_environment_digest"))
        if profile_id not in profile_map or observed_id not in observed_map:
            raise CrossEnvironmentReplayError("receipt references unknown provenance object")
        if observed_map[observed_id].get("declared_profile_digest") != profile_id:
            raise CrossEnvironmentReplayError("cross-environment observed receipt swap detected")
        _validate_report_receipt(
            receipt=receipt,
            plan=plan,
            profile=profile_map[profile_id],
            observed=observed_map[observed_id],
        )
        receipt_map[identity] = dict(receipt)
    expected_raw = plan.get("expected_matrix")
    if not isinstance(expected_raw, list):
        raise CrossEnvironmentReplayError("replay plan expected matrix is invalid")
    expected = set(cast(list[str], expected_raw))
    actual = {str(item["environment_profile_digest"]) for item in receipt_map.values()}
    if actual != expected:
        raise CrossEnvironmentReplayError("partial or substituted environment matrix")
    if len(receipt_map) != len(expected) or set(profile_map) != expected:
        raise CrossEnvironmentReplayError("matrix must contain exactly one receipt per profile")
    if supersedes is not None:
        _digest(supersedes, field="supersedes")
    body: dict[str, object] = {
        "schema": REPLAY_REPORT_SCHEMA_V1,
        "plan": dict(plan),
        "profiles": [profile_map[key] for key in sorted(profile_map)],
        "observed_environments": [observed_map[key] for key in sorted(observed_map)],
        "receipts": [receipt_map[key] for key in sorted(receipt_map)],
        "matrix_complete": True,
        "supersedes": supersedes,
    }
    body["report_digest"] = digest_value(body)
    return body


def _load_json_file(path: Path, *, label: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise CrossEnvironmentReplayError(f"{label} is missing or symlinked")
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CrossEnvironmentReplayError(f"invalid {label}") from exc
    if not isinstance(loaded, dict):
        raise CrossEnvironmentReplayError(f"{label} must be an object")
    return cast(dict[str, object], loaded)


def inspect_oci_layout(
    layout_root: str | Path,
    *,
    source_bundle_digest: str,
    dependency_identity_digest: str,
    verifier_digest: str,
) -> dict[str, object]:
    """Verify and content-address one runnable OCI image layout without tag authority."""
    root = Path(layout_root)
    layout_path = root / "oci-layout"
    index_path = root / "index.json"
    layout = _load_json_file(layout_path, label="OCI layout")
    index = _load_json_file(index_path, label="OCI index")
    if layout != {"imageLayoutVersion": "1.0.0"}:
        raise CrossEnvironmentReplayError("unsupported OCI image layout")
    manifests = index.get("manifests")
    if not isinstance(manifests, list) or not manifests:
        raise CrossEnvironmentReplayError("OCI index has no manifest descriptors")
    blob_root = root / "blobs" / "sha256"
    if blob_root.is_symlink() or not blob_root.is_dir():
        raise CrossEnvironmentReplayError("OCI sha256 blob directory is missing")
    blob_by_digest: dict[str, Path] = {}
    inventory: list[dict[str, object]] = []
    for blob in sorted(blob_root.iterdir(), key=lambda item: item.name):
        if blob.is_symlink() or not blob.is_file() or _SHA256_RE.fullmatch(blob.name) is None:
            raise CrossEnvironmentReplayError("invalid OCI blob path")
        observed_digest = sha256_file(blob)
        if observed_digest != blob.name:
            raise CrossEnvironmentReplayError("OCI blob digest mismatch")
        blob_by_digest[observed_digest] = blob
        inventory.append({"digest": observed_digest, "size": blob.stat().st_size})
    if not inventory:
        raise CrossEnvironmentReplayError("OCI layout has no content-addressed blobs")

    def resolve_descriptor(
        descriptor: Mapping[str, object],
        *,
        label: str,
    ) -> tuple[str, Path]:
        raw_digest = _text(descriptor.get("digest"), field=f"{label} digest")
        if not raw_digest.startswith("sha256:"):
            raise CrossEnvironmentReplayError(f"{label} must use sha256")
        digest = _digest(raw_digest.removeprefix("sha256:"), field=f"{label} digest")
        blob = blob_by_digest.get(digest)
        if blob is None:
            raise CrossEnvironmentReplayError(f"{label} blob is missing")
        size = descriptor.get("size")
        if isinstance(size, bool) or not isinstance(size, int) or size != blob.stat().st_size:
            raise CrossEnvironmentReplayError(f"{label} descriptor size mismatch")
        return digest, blob

    runnable: list[tuple[str, dict[str, object], dict[str, object]]] = []
    for descriptor in manifests:
        if not isinstance(descriptor, dict):
            raise CrossEnvironmentReplayError("invalid OCI manifest descriptor")
        if descriptor.get("mediaType") != "application/vnd.oci.image.manifest.v1+json":
            continue
        manifest_digest, manifest_path = resolve_descriptor(
            descriptor,
            label="OCI manifest",
        )
        manifest = _load_json_file(manifest_path, label="OCI image manifest")
        if manifest.get("schemaVersion") != 2:
            raise CrossEnvironmentReplayError("unsupported OCI image manifest")
        runnable.append((manifest_digest, descriptor, manifest))
    if len(runnable) != 1:
        raise CrossEnvironmentReplayError(
            "OCI layout must contain exactly one runnable image manifest"
        )
    manifest_digest, descriptor, manifest = runnable[0]
    config_descriptor = manifest.get("config")
    layers = manifest.get("layers")
    if not isinstance(config_descriptor, dict) or not isinstance(layers, list):
        raise CrossEnvironmentReplayError("OCI manifest config/layers are invalid")
    config_digest, config_path = resolve_descriptor(config_descriptor, label="OCI config")
    config = _load_json_file(config_path, label="OCI image config")
    architecture = _text(config.get("architecture"), field="OCI architecture")
    os_name = _text(config.get("os"), field="OCI os")
    config_section = config.get("config")
    if not isinstance(config_section, dict):
        raise CrossEnvironmentReplayError("OCI runtime config is missing")
    entrypoint = config_section.get("Entrypoint")
    if (
        not isinstance(entrypoint, list)
        or not entrypoint
        or any(not isinstance(item, str) or not item for item in entrypoint)
    ):
        raise CrossEnvironmentReplayError("OCI entrypoint is missing")
    layer_digests: list[str] = []
    for layer in layers:
        if not isinstance(layer, dict):
            raise CrossEnvironmentReplayError("invalid OCI layer descriptor")
        layer_digest, _ = resolve_descriptor(layer, label="OCI layer")
        layer_digests.append(layer_digest)
    if not layer_digests:
        raise CrossEnvironmentReplayError("OCI image must contain at least one layer")
    descriptor_platform = descriptor.get("platform")
    if descriptor_platform is not None:
        if not isinstance(descriptor_platform, dict):
            raise CrossEnvironmentReplayError("OCI descriptor platform must be an object")
        if descriptor_platform.get("architecture") not in (None, architecture):
            raise CrossEnvironmentReplayError("OCI architecture descriptor/config mismatch")
        if descriptor_platform.get("os") not in (None, os_name):
            raise CrossEnvironmentReplayError("OCI OS descriptor/config mismatch")
    body: dict[str, object] = {
        "schema": OCI_CAPSULE_SCHEMA_V1,
        "oci_index_digest": sha256_file(index_path),
        "oci_layout_digest": sha256_file(layout_path),
        "oci_manifest_digest": manifest_digest,
        "runtime_config_digest": config_digest,
        "layer_digests": layer_digests,
        "blob_inventory": inventory,
        "platform": {"os": os_name, "architecture": architecture},
        "source_bundle_digest": _digest(
            source_bundle_digest,
            field="source_bundle_digest",
        ),
        "dependency_identity_digest": _digest(
            dependency_identity_digest,
            field="dependency_identity_digest",
        ),
        "verifier_digest": _digest(verifier_digest, field="verifier_digest"),
        "entrypoint": list(entrypoint),
        "entrypoint_digest": digest_value(entrypoint),
        "mutable_tag_is_identity_authority": False,
        "host_kernel_runtime_cpu_dependency_remains": True,
    }
    body["capsule_digest"] = digest_value(body)
    return body
