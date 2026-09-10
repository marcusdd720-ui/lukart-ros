"""Standalone stdlib-only verifier for LRD-01K aggregate evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import cast

REPORT = "lukart.cross-environment-replay-report.v1"
PLAN = "lukart.cross-environment-replay-plan.v1"
PROFILE = "lukart.execution-environment-profile.v1"
OBSERVED = "lukart.observed-environment-receipt.v1"
RECEIPT = "lukart.cross-environment-replay-receipt.v1"
_SHA = re.compile(r"^[0-9a-f]{64}$")
_RESULTS = {
    "EXACT_ENVIRONMENT_REPLAY",
    "CROSS_ENV_SEMANTICALLY_EQUIVALENT",
    "PRESENTATION_ONLY_DRIFT",
    "SEMANTIC_DRIFT",
    "ENVIRONMENT_INCOMPATIBLE",
    "UNVERIFIABLE",
}
_LRD01D = {"NO_DRIFT", "PRESENTATION_ONLY", "SEMANTIC_DRIFT", "UNVERIFIABLE", "ABSTAIN"}
_STATUSES = {"VERIFIED", "FAILED", "UNVERIFIABLE", "INCOMPATIBLE"}
_FIELD_CLASSES = {
    "name": "NON_SEMANTIC",
    "os_family": "REQUIRED_COMPATIBILITY",
    "os_release": "OBSERVED_PROVENANCE",
    "os_build": "OBSERVED_PROVENANCE",
    "cpu_architecture": "REQUIRED_COMPATIBILITY",
    "python_implementation": "REQUIRED_COMPATIBILITY",
    "python_version": "REQUIRED_COMPATIBILITY",
    "python_cache_tag": "REQUIRED_COMPATIBILITY",
    "python_soabi": "REQUIRED_COMPATIBILITY",
    "openssl_identity": "OBSERVED_PROVENANCE",
    "sqlite_identity": "OBSERVED_PROVENANCE",
    "libc_runtime_identity": "OBSERVED_PROVENANCE",
    "locale": "NON_SEMANTIC",
    "timezone": "NON_SEMANTIC",
    "filesystem_semantics": "OBSERVED_PROVENANCE",
    "dependency_lock_digest": "REQUIRED_COMPATIBILITY",
    "physical_dependency_artifact_identities": "REQUIRED_COMPATIBILITY",
    "canonicalization_profile_digest": "REQUIRED_COMPATIBILITY",
    "migration_registry_digest": "REQUIRED_COMPATIBILITY",
    "crypto_profile_digest": "REQUIRED_COMPATIBILITY",
    "lrd01i_bundle_digest": "REQUIRED_COMPATIBILITY",
    "replay_verifier_digest": "REQUIRED_COMPATIBILITY",
    "environment_policy_digest": "REQUIRED_COMPATIBILITY",
}
_PROFILE_KEYS = {
    "schema", "name", "os_family", "os_release", "os_build", "cpu_architecture",
    "python_implementation", "python_version", "python_cache_tag", "python_soabi",
    "openssl_identity", "sqlite_identity", "libc_runtime_identity", "locale", "timezone",
    "filesystem_semantics", "dependency_lock_digest", "physical_dependency_artifact_identities",
    "canonicalization_profile_digest", "migration_registry_digest", "crypto_profile_digest",
    "lrd01i_bundle_digest", "replay_verifier_digest", "environment_policy_digest",
    "field_classes", "profile_digest",
}
_OBS_KEYS = {
    "schema", "os_family", "os_release", "os_build", "cpu_architecture",
    "python_implementation", "python_version", "python_cache_tag", "python_soabi",
    "openssl_identity", "sqlite_identity", "libc_runtime_identity", "locale", "timezone",
    "filesystem_semantics", "installed_artifacts", "installed_artifact_inventory_digest",
    "declared_profile_digest", "verifier_digest", "environment_policy_digest",
    "observed_environment_digest",
}
_PLAN_KEYS = {
    "schema", "lrd01i_bundle_digest", "ssc02_manifest_digest", "environment_profile_digests",
    "reference_profile_digest", "replay_policy_digest", "migration_registry_digest",
    "canonicalization_profile_digest", "crypto_profile_digest", "expected_matrix", "hard_bounds",
    "plan_digest",
}
_RECEIPT_KEYS = {
    "schema", "plan_digest", "lrd01i_bundle_digest", "ssc02_manifest_digest",
    "environment_profile_digest", "observed_environment_digest", "replay_policy_digest",
    "migration_registry_digest", "canonicalization_profile_digest", "crypto_profile_digest",
    "verifier_digest", "execution_status", "semantic_result_identity", "invariant_report_identity",
    "lrd01d_classification", "classification", "network_mode", "ccl_write_authority",
    "product_write_authority", "failure_status", "receipt_digest",
}


class VerificationError(ValueError):
    """Fail-closed standalone verification error."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _digest(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise VerificationError(f"{field} must be lowercase sha256")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise VerificationError(f"{field} must be canonical text")
    return value


def _strict(value: Mapping[str, object], expected: set[str], field: str) -> None:
    if set(value) != expected:
        raise VerificationError(f"{field} contains missing or unknown fields")


def _identity(value: Mapping[str, object], field: str) -> str:
    actual = _digest(value.get(field), field)
    body = dict(value)
    body.pop(field, None)
    if _hash(body) != actual:
        raise VerificationError(f"{field} mismatch")
    return actual


def _compatible(profile: Mapping[str, object], observed: Mapping[str, object]) -> bool:
    required = (
        "os_family", "cpu_architecture", "python_implementation", "python_version",
        "python_cache_tag", "python_soabi",
    )
    if any(profile.get(key) != observed.get(key) for key in required):
        return False
    physical = profile.get("physical_dependency_artifact_identities")
    if (
        not isinstance(physical, list)
        or observed.get("installed_artifact_inventory_digest") not in physical
    ):
        return False
    version = observed.get("python_version")
    if not isinstance(version, str):
        return False
    try:
        major_minor = tuple(int(part) for part in version.split(".")[:2])
    except ValueError:
        return False
    return (3, 11) <= major_minor < (3, 15)


def _classification(
    *, lrd01d: str, compatible: bool, complete: bool, profile: str, reference: str
) -> str:
    if lrd01d not in _LRD01D:
        raise VerificationError("unknown LRD-01D classification")
    if not complete or lrd01d in {"UNVERIFIABLE", "ABSTAIN"}:
        return "UNVERIFIABLE"
    if not compatible:
        return "ENVIRONMENT_INCOMPATIBLE"
    if lrd01d == "SEMANTIC_DRIFT":
        return "SEMANTIC_DRIFT"
    if lrd01d == "PRESENTATION_ONLY":
        return "PRESENTATION_ONLY_DRIFT"
    if profile == reference:
        return "EXACT_ENVIRONMENT_REPLAY"
    return "CROSS_ENV_SEMANTICALLY_EQUIVALENT"


def verify_report(value: Mapping[str, object], *, expected_digest: str | None = None) -> str:
    report_keys = {
        "schema", "plan", "profiles", "observed_environments", "receipts",
        "matrix_complete", "supersedes", "report_digest",
    }
    _strict(value, report_keys, "report")
    if value.get("schema") != REPORT or value.get("matrix_complete") is not True:
        raise VerificationError("unsupported or incomplete report")
    report_digest = _identity(value, "report_digest")
    if expected_digest is not None and report_digest != _digest(expected_digest, "expected_digest"):
        raise VerificationError("externally pinned report digest mismatch")

    plan = value.get("plan")
    if not isinstance(plan, dict):
        raise VerificationError("plan missing")
    _strict(plan, _PLAN_KEYS, "plan")
    if plan.get("schema") != PLAN:
        raise VerificationError("unknown plan schema")
    plan_digest = _identity(plan, "plan_digest")
    for key in (
        "lrd01i_bundle_digest", "ssc02_manifest_digest", "reference_profile_digest",
        "replay_policy_digest", "migration_registry_digest", "canonicalization_profile_digest",
        "crypto_profile_digest",
    ):
        _digest(plan.get(key), key)
    declared = plan.get("environment_profile_digests")
    expected = plan.get("expected_matrix")
    if (
        not isinstance(declared, list) or len(declared) < 2 or declared != sorted(set(declared))
        or not isinstance(expected, list) or expected != declared
    ):
        raise VerificationError("invalid plan matrix")
    if (
        plan.get("reference_profile_digest") not in declared
        or not isinstance(plan.get("hard_bounds"), dict)
    ):
        raise VerificationError("invalid reference profile or hard bounds")

    profiles_raw = value.get("profiles")
    observed_raw = value.get("observed_environments")
    receipts_raw = value.get("receipts")
    if not all(isinstance(item, list) for item in (profiles_raw, observed_raw, receipts_raw)):
        raise VerificationError("report inventories must be arrays")

    profiles: dict[str, dict[str, object]] = {}
    for profile in cast(list[object], profiles_raw):
        if not isinstance(profile, dict):
            raise VerificationError("invalid profile")
        _strict(profile, _PROFILE_KEYS, "profile")
        if profile.get("schema") != PROFILE or profile.get("field_classes") != _FIELD_CLASSES:
            raise VerificationError("profile schema or field-class mapping mismatch")
        for key in (
            "dependency_lock_digest",
            "canonicalization_profile_digest",
            "migration_registry_digest",
            "crypto_profile_digest", "lrd01i_bundle_digest", "replay_verifier_digest",
            "environment_policy_digest",
        ):
            _digest(profile.get(key), key)
        physical = profile.get("physical_dependency_artifact_identities")
        if not isinstance(physical, list) or not physical or physical != sorted(set(physical)):
            raise VerificationError("invalid physical dependency identities")
        identity = _identity(profile, "profile_digest")
        if identity in profiles:
            raise VerificationError("duplicate profile")
        profiles[identity] = profile

    observed: dict[str, dict[str, object]] = {}
    for item in cast(list[object], observed_raw):
        if not isinstance(item, dict):
            raise VerificationError("invalid observed environment")
        _strict(item, _OBS_KEYS, "observed environment")
        if item.get("schema") != OBSERVED:
            raise VerificationError("unknown observed schema")
        inventory = item.get("installed_artifacts")
        if (
            not isinstance(inventory, list)
            or _hash(inventory) != item.get("installed_artifact_inventory_digest")
        ):
            raise VerificationError("installed artifact inventory substitution")
        for record in inventory:
            if not isinstance(record, dict) or set(record) != {
                "name",
                "version",
                "physical_files_digest",
                "file_count",
            }:
                raise VerificationError("invalid installed artifact record")
            _text(record.get("name"), "installed artifact name")
            _text(record.get("version"), "installed artifact version")
            _digest(record.get("physical_files_digest"), "physical_files_digest")
        for key in ("declared_profile_digest", "verifier_digest", "environment_policy_digest"):
            _digest(item.get(key), key)
        identity = _identity(item, "observed_environment_digest")
        if identity in observed:
            raise VerificationError("duplicate observed environment")
        observed[identity] = item

    seen_profiles: set[str] = set()
    seen_receipts: set[str] = set()
    for receipt in cast(list[object], receipts_raw):
        if not isinstance(receipt, dict):
            raise VerificationError("invalid receipt")
        _strict(receipt, _RECEIPT_KEYS, "receipt")
        if receipt.get("schema") != RECEIPT:
            raise VerificationError("unknown receipt schema")
        receipt_id = _identity(receipt, "receipt_digest")
        if receipt_id in seen_receipts:
            raise VerificationError("duplicate receipt")
        seen_receipts.add(receipt_id)
        profile_id = _digest(
            receipt.get("environment_profile_digest"),
            "environment_profile_digest",
        )
        observed_id = _digest(
            receipt.get("observed_environment_digest"),
            "observed_environment_digest",
        )
        if profile_id not in profiles or observed_id not in observed or profile_id in seen_profiles:
            raise VerificationError("receipt provenance or matrix substitution")
        seen_profiles.add(profile_id)
        profile = profiles[profile_id]
        observation = observed[observed_id]
        if observation.get("declared_profile_digest") != profile_id:
            raise VerificationError("observed/profile substitution")
        if observation.get("environment_policy_digest") != profile.get("environment_policy_digest"):
            raise VerificationError("environment-policy substitution")
        if (
            receipt.get("verifier_digest") != profile.get("replay_verifier_digest")
            or receipt.get("verifier_digest") != observation.get("verifier_digest")
        ):
            raise VerificationError("verifier substitution")
        if receipt.get("plan_digest") != plan_digest:
            raise VerificationError("plan binding mismatch")
        for key in (
            "lrd01i_bundle_digest", "ssc02_manifest_digest", "replay_policy_digest",
            "migration_registry_digest", "canonicalization_profile_digest", "crypto_profile_digest",
        ):
            if receipt.get(key) != plan.get(key):
                raise VerificationError(f"{key} binding mismatch")
        physical_identities = cast(
            list[object],
            profile.get("physical_dependency_artifact_identities"),
        )
        if observation.get("installed_artifact_inventory_digest") not in physical_identities:
            raise VerificationError("physical dependency identity mismatch")
        status = receipt.get("execution_status")
        lrd01d = receipt.get("lrd01d_classification")
        result = receipt.get("classification")
        if status not in _STATUSES or lrd01d not in _LRD01D or result not in _RESULTS:
            raise VerificationError("unknown status/classification")
        semantic = receipt.get("semantic_result_identity")
        invariants = receipt.get("invariant_report_identity")
        if semantic is not None:
            _digest(semantic, "semantic_result_identity")
        if invariants is not None:
            _digest(invariants, "invariant_report_identity")
        compatible = _compatible(profile, observation)
        if status == "VERIFIED" and not compatible:
            raise VerificationError("verified receipt contradicts incompatible environment")
        if status == "INCOMPATIBLE" and compatible:
            raise VerificationError("incompatible receipt contradicts compatible environment")
        expected_result = _classification(
            lrd01d=str(lrd01d),
            compatible=compatible,
            complete=status == "VERIFIED" and semantic is not None and invariants is not None,
            profile=profile_id,
            reference=str(plan.get("reference_profile_digest")),
        )
        if result != expected_result:
            raise VerificationError("receipt classification mismatch")
        failure = receipt.get("failure_status")
        if status == "VERIFIED" and failure is not None:
            raise VerificationError("verified receipt cannot contain failure status")
        if (
            receipt.get("network_mode") != "DENY"
            or receipt.get("ccl_write_authority") is not False
            or receipt.get("product_write_authority") is not False
        ):
            raise VerificationError("least-privilege/offline boundary violated")

    expected_profiles = set(cast(list[str], expected))
    if expected_profiles != seen_profiles or expected_profiles != set(profiles):
        raise VerificationError("partial or substituted matrix")
    if len(seen_receipts) != len(cast(list[object], expected)):
        raise VerificationError("matrix cardinality mismatch")
    return report_digest


def verify_file(path: str | Path, expected_digest: str | None = None) -> str:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise VerificationError("report must be a regular file")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError("cannot read report") from exc
    if not isinstance(value, dict):
        raise VerificationError("report root must be an object")
    return verify_report(cast(Mapping[str, object], value), expected_digest=expected_digest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("--expected-digest")
    args = parser.parse_args()
    print(verify_file(args.report, args.expected_digest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
