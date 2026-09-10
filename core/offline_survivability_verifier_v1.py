"""Standalone stdlib verifier for LRD-01I offline survivability bundles.

This module intentionally imports only the Python standard library so the exact copy
placed inside a survivability bundle can verify its physical inventory before the
historical LUKART runtime is reconstructed. It is verification-only and has no Product,
CCL, Gold, policy, trust, provider, or release authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import cast

SURVIVABILITY_SCHEMA_V1 = "lukart.offline-long-range-survivability.v1"
SURVIVABILITY_MANIFEST_NAME = "survivability.json"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_ROLES = frozenset({"identity", "escrow_blob", "supply_chain", "verifier"})
_LRD_ROLES = (
    "authorization_policy",
    "canonicalization_profiles",
    "case_replay_bundle",
    "config",
    "crypto_profile",
    "dependency_lock",
    "dependency_set",
    "epistemic_policy",
    "evidence_inputs",
    "migration_registry",
    "plugin_set",
    "provider_models",
    "provider_requests",
    "provider_responses",
    "renderer",
    "runtime",
    "sbom",
    "schemas",
    "semantic_result",
    "source_archive",
    "storage_profile",
    "trust_policy",
    "verification_material",
)
_BOOTSTRAP_CONTRACT = {
    "network": "DENY",
    "registry": "NONE",
    "source_host": "NONE",
    "provider_access": "NONE",
    "compatible_python_required": True,
    "physical_interpreter_preserved": False,
}
_MANIFEST_KEYS = frozenset(
    {
        "schema",
        "case_id",
        "code_commit_sha",
        "code_tree_sha",
        "lrd_manifest_identity",
        "replay_capsule_identity",
        "escrow_manifest_identity",
        "supply_chain_manifest_digest",
        "supply_chain_runtime",
        "bootstrap_contract",
        "inventory",
        "bundle_digest",
    }
)


class OfflineSurvivabilityVerificationError(ValueError):
    """Fail-closed standalone verification error."""


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _strict_keys(value: Mapping[str, object], expected: frozenset[str], context: str) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = ",".join(sorted(expected - actual)) or "-"
    unknown = ",".join(sorted(actual - expected)) or "-"
    raise OfflineSurvivabilityVerificationError(
        f"{context} key contract violation: missing={missing}; unknown={unknown}"
    )


def _mapping(value: object, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise OfflineSurvivabilityVerificationError(f"{context} must be an object")
    return cast(Mapping[str, object], value)


def _text(value: object, context: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise OfflineSurvivabilityVerificationError(
            f"{context} must be nonblank and already canonical"
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise OfflineSurvivabilityVerificationError(f"{context} contains control characters")
    return value


def _sha256(value: object, context: str) -> str:
    text = _text(value, context)
    if _SHA256_RE.fullmatch(text) is None:
        raise OfflineSurvivabilityVerificationError(f"{context} must be lowercase sha256")
    return text


def _git_sha(value: object, context: str) -> str:
    text = _text(value, context)
    if _GIT_SHA_RE.fullmatch(text) is None:
        raise OfflineSurvivabilityVerificationError(f"{context} must be a full lowercase Git SHA")
    return text


def _address(value: object, context: str) -> Mapping[str, object]:
    address = _mapping(value, context)
    _strict_keys(address, frozenset({"algorithm", "digest"}), context)
    if address.get("algorithm") != "sha256":
        raise OfflineSurvivabilityVerificationError(f"{context} uses unsupported digest algorithm")
    _sha256(address.get("digest"), f"{context} digest")
    return address


def _safe_relative(value: object, context: str) -> str:
    text = _text(value, context)
    if "\\" in text or "\x00" in text:
        raise OfflineSurvivabilityVerificationError(f"unsafe {context}")
    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise OfflineSurvivabilityVerificationError(f"unsafe {context}")
    if path.as_posix() != text or ":" in path.parts[0]:
        raise OfflineSurvivabilityVerificationError(f"non-canonical {context}")
    return text


def _regular_file(root: Path, relative: str) -> Path:
    current = root.resolve(strict=True)
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise OfflineSurvivabilityVerificationError(f"symlink is forbidden: {relative}")
    if not current.is_file():
        raise OfflineSurvivabilityVerificationError(f"bundle file is missing: {relative}")
    return current


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, context: str) -> dict[str, object]:
    try:
        decoded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OfflineSurvivabilityVerificationError(f"cannot read {context}") from exc
    if not isinstance(decoded, dict) or any(not isinstance(key, str) for key in decoded):
        raise OfflineSurvivabilityVerificationError(f"{context} must be an object")
    return cast(dict[str, object], decoded)


def _content_address_body(value: Mapping[str, object], identity_key: str, context: str) -> None:
    expected = _address(value.get(identity_key), f"{context} identity")
    body = dict(value)
    body.pop(identity_key, None)
    digest = hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()
    if expected.get("digest") != digest:
        raise OfflineSurvivabilityVerificationError(f"{context} content identity mismatch")


def _verify_lrd(root: Path, manifest: Mapping[str, object]) -> dict[str, object]:
    lrd = _load_json(root / "identity" / "long-range-manifest.json", "LRD manifest")
    expected_keys = frozenset(
        {
            "schema",
            "case_id",
            "case_replay_manifest_identity",
            "coverage_matrix_identity",
            "code_commit_sha",
            "code_tree_sha",
            "artifacts",
            "semantic_result_identity",
            "presentation_identity",
            "manifest_identity",
        }
    )
    _strict_keys(lrd, expected_keys, "LRD manifest")
    if lrd.get("schema") != "lukart.long-range-replay-manifest.v1":
        raise OfflineSurvivabilityVerificationError("unsupported LRD manifest schema")
    if lrd.get("case_id") != manifest.get("case_id"):
        raise OfflineSurvivabilityVerificationError("LRD case identity mismatch")
    if _git_sha(lrd.get("code_commit_sha"), "LRD code SHA") != manifest.get(
        "code_commit_sha"
    ):
        raise OfflineSurvivabilityVerificationError("LRD code SHA mismatch")
    if _git_sha(lrd.get("code_tree_sha"), "LRD tree SHA") != manifest.get("code_tree_sha"):
        raise OfflineSurvivabilityVerificationError("LRD tree SHA mismatch")
    _content_address_body(lrd, "manifest_identity", "LRD manifest")
    if _address(lrd.get("manifest_identity"), "LRD manifest identity") != _address(
        manifest.get("lrd_manifest_identity"), "outer LRD manifest identity"
    ):
        raise OfflineSurvivabilityVerificationError("outer LRD identity mismatch")

    raw_artifacts = lrd.get("artifacts")
    if not isinstance(raw_artifacts, list):
        raise OfflineSurvivabilityVerificationError("LRD artifacts must be a list")
    roles: list[str] = []
    by_role: dict[str, Mapping[str, object]] = {}
    for item in raw_artifacts:
        artifact = _mapping(item, "LRD artifact")
        _strict_keys(artifact, frozenset({"role", "identity", "preservation"}), "LRD artifact")
        role = _text(artifact.get("role"), "LRD artifact role")
        _address(artifact.get("identity"), f"LRD {role} identity")
        if artifact.get("preservation") != "PRESERVED":
            raise OfflineSurvivabilityVerificationError(
                f"offline survivability requires PRESERVED material for {role}"
            )
        roles.append(role)
        by_role[role] = artifact
    if tuple(roles) != _LRD_ROLES:
        raise OfflineSurvivabilityVerificationError("LRD artifact-role inventory mismatch")
    semantic = by_role["semantic_result"]["identity"]
    if semantic != lrd.get("semantic_result_identity"):
        raise OfflineSurvivabilityVerificationError("LRD semantic-result identity mismatch")
    return lrd


def _verify_capsule(root: Path, manifest: Mapping[str, object], lrd: Mapping[str, object]) -> None:
    capsule = _load_json(root / "identity" / "replay-capsule.json", "replay capsule")
    _strict_keys(
        capsule,
        frozenset({"schema", "manifest", "supersedes_digest", "capsule_identity"}),
        "replay capsule",
    )
    if capsule.get("schema") != "lukart.replay-capsule.v1":
        raise OfflineSurvivabilityVerificationError("unsupported replay capsule schema")
    if capsule.get("manifest") != lrd:
        raise OfflineSurvivabilityVerificationError("replay capsule embeds a different LRD manifest")
    _content_address_body(capsule, "capsule_identity", "replay capsule")
    if _address(capsule.get("capsule_identity"), "replay capsule identity") != _address(
        manifest.get("replay_capsule_identity"), "outer replay capsule identity"
    ):
        raise OfflineSurvivabilityVerificationError("outer replay capsule identity mismatch")


def _verify_escrow(
    root: Path,
    manifest: Mapping[str, object],
    lrd: Mapping[str, object],
    inventory_paths: set[str],
) -> None:
    escrow = _load_json(root / "identity" / "artifact-escrow-manifest.json", "escrow manifest")
    _strict_keys(
        escrow,
        frozenset(
            {
                "schema",
                "case_id",
                "long_range_manifest_identity",
                "bindings",
                "escrow_manifest_identity",
            }
        ),
        "escrow manifest",
    )
    if escrow.get("schema") != "lukart.artifact-escrow-manifest.v1":
        raise OfflineSurvivabilityVerificationError("unsupported escrow manifest schema")
    if escrow.get("case_id") != manifest.get("case_id"):
        raise OfflineSurvivabilityVerificationError("escrow case identity mismatch")
    if escrow.get("long_range_manifest_identity") != lrd.get("manifest_identity"):
        raise OfflineSurvivabilityVerificationError("escrow LRD binding mismatch")
    _content_address_body(escrow, "escrow_manifest_identity", "escrow manifest")
    if _address(escrow.get("escrow_manifest_identity"), "escrow manifest identity") != _address(
        manifest.get("escrow_manifest_identity"), "outer escrow identity"
    ):
        raise OfflineSurvivabilityVerificationError("outer escrow identity mismatch")

    raw_lrd_artifacts = cast(list[object], lrd["artifacts"])
    lrd_by_role = {
        cast(str, _mapping(item, "LRD artifact")["role"]): _mapping(item, "LRD artifact")
        for item in raw_lrd_artifacts
    }
    raw_bindings = escrow.get("bindings")
    if not isinstance(raw_bindings, list):
        raise OfflineSurvivabilityVerificationError("escrow bindings must be a list")
    seen_roles: list[str] = []
    expected_blob_paths: set[str] = set()
    for item in raw_bindings:
        binding = _mapping(item, "escrow binding")
        _strict_keys(
            binding,
            frozenset(
                {"schema", "role", "logical_identity", "blob", "kind", "binding_identity"}
            ),
            "escrow binding",
        )
        if binding.get("schema") != "lukart.artifact-escrow-binding.v1":
            raise OfflineSurvivabilityVerificationError("unsupported escrow binding schema")
        role = _text(binding.get("role"), "escrow role")
        if role not in lrd_by_role or binding.get("logical_identity") != lrd_by_role[role].get(
            "identity"
        ):
            raise OfflineSurvivabilityVerificationError(f"escrow logical identity mismatch: {role}")
        _content_address_body(binding, "binding_identity", f"escrow binding {role}")
        blob = _mapping(binding.get("blob"), f"escrow blob {role}")
        _strict_keys(blob, frozenset({"schema", "algorithm", "digest", "size"}), "escrow blob")
        if blob.get("schema") != "lukart.artifact-blob.v1" or blob.get("algorithm") != "sha256":
            raise OfflineSurvivabilityVerificationError("unsupported escrow blob identity")
        digest = _sha256(blob.get("digest"), f"escrow blob {role} digest")
        size = blob.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise OfflineSurvivabilityVerificationError("invalid escrow blob size")
        blob_path = f"escrow/sha256/{digest[:2]}/{digest}"
        if blob_path not in inventory_paths:
            raise OfflineSurvivabilityVerificationError(f"escrow blob not inventoried: {role}")
        expected_blob_paths.add(blob_path)
        seen_roles.append(role)
    if tuple(seen_roles) != _LRD_ROLES:
        raise OfflineSurvivabilityVerificationError("escrow role coverage mismatch")
    actual_blob_paths = {path for path in inventory_paths if path.startswith("escrow/")}
    if actual_blob_paths != expected_blob_paths:
        raise OfflineSurvivabilityVerificationError("escrow physical blob inventory mismatch")


def _verify_supply_chain(root: Path, manifest: Mapping[str, object]) -> None:
    supply = _load_json(root / "supply-chain" / "manifest.json", "SSC-02 manifest")
    _strict_keys(
        supply,
        frozenset(
            {
                "schema",
                "source_sha",
                "python",
                "platform",
                "recovery_contract",
                "inventory",
                "manifest_digest",
            }
        ),
        "SSC-02 manifest",
    )
    if supply.get("schema") != "lukart.supply-chain-continuity.v2":
        raise OfflineSurvivabilityVerificationError("unsupported SSC-02 schema")
    source_sha = _git_sha(supply.get("source_sha"), "SSC-02 source SHA")
    if source_sha != manifest.get("code_commit_sha"):
        raise OfflineSurvivabilityVerificationError("SSC-02 source SHA does not match LRD code SHA")
    unsigned = dict(supply)
    digest = _sha256(unsigned.pop("manifest_digest", None), "SSC-02 manifest digest")
    expected = hashlib.sha256(_canonical_json(unsigned).encode("utf-8")).hexdigest()
    if digest != expected or digest != manifest.get("supply_chain_manifest_digest"):
        raise OfflineSurvivabilityVerificationError("SSC-02 manifest digest mismatch")
    runtime = _mapping(manifest.get("supply_chain_runtime"), "supply-chain runtime")
    _strict_keys(runtime, frozenset({"python", "platform"}), "supply-chain runtime")
    if runtime.get("python") != supply.get("python") or runtime.get("platform") != supply.get(
        "platform"
    ):
        raise OfflineSurvivabilityVerificationError("supply-chain runtime identity mismatch")

    raw_inventory = supply.get("inventory")
    if not isinstance(raw_inventory, list) or not raw_inventory:
        raise OfflineSurvivabilityVerificationError("SSC-02 inventory must be non-empty")
    for item in raw_inventory:
        record = _mapping(item, "SSC-02 inventory record")
        relative = _safe_relative(record.get("path"), "SSC-02 inventory path")
        candidate = _regular_file(root, f"supply-chain/{relative}")
        size = record.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise OfflineSurvivabilityVerificationError("invalid SSC-02 inventory size")
        expected_digest = _sha256(record.get("sha256"), "SSC-02 inventory digest")
        if candidate.stat().st_size != size or _file_sha256(candidate) != expected_digest:
            raise OfflineSurvivabilityVerificationError(
                f"SSC-02 physical inventory mismatch: {relative}"
            )


def verify_survivability_bundle(
    bundle_root: str | Path,
    *,
    expected_digest: str,
) -> str:
    """Verify one complete LRD-01I bundle using standard-library facilities only."""

    root = Path(bundle_root)
    if root.is_symlink() or not root.is_dir():
        raise OfflineSurvivabilityVerificationError("survivability bundle root is invalid")
    manifest_path = root / SURVIVABILITY_MANIFEST_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise OfflineSurvivabilityVerificationError("survivability manifest is missing")
    manifest = _load_json(manifest_path, "survivability manifest")
    _strict_keys(manifest, _MANIFEST_KEYS, "survivability manifest")
    if manifest.get("schema") != SURVIVABILITY_SCHEMA_V1:
        raise OfflineSurvivabilityVerificationError("unsupported survivability schema")
    _text(manifest.get("case_id"), "case_id")
    _git_sha(manifest.get("code_commit_sha"), "code_commit_sha")
    _git_sha(manifest.get("code_tree_sha"), "code_tree_sha")
    _address(manifest.get("lrd_manifest_identity"), "lrd_manifest_identity")
    _address(manifest.get("replay_capsule_identity"), "replay_capsule_identity")
    _address(manifest.get("escrow_manifest_identity"), "escrow_manifest_identity")
    _sha256(manifest.get("supply_chain_manifest_digest"), "supply_chain_manifest_digest")
    bootstrap = _mapping(manifest.get("bootstrap_contract"), "bootstrap contract")
    if dict(bootstrap) != _BOOTSTRAP_CONTRACT:
        raise OfflineSurvivabilityVerificationError("unsupported bootstrap contract")

    declared_digest = _sha256(manifest.get("bundle_digest"), "bundle_digest")
    pinned_digest = _sha256(expected_digest, "expected bundle digest")
    unsigned = dict(manifest)
    unsigned.pop("bundle_digest", None)
    computed = hashlib.sha256(_canonical_json(unsigned).encode("utf-8")).hexdigest()
    if declared_digest != computed or declared_digest != pinned_digest:
        raise OfflineSurvivabilityVerificationError("survivability bundle digest mismatch")

    raw_inventory = manifest.get("inventory")
    if not isinstance(raw_inventory, list) or not raw_inventory:
        raise OfflineSurvivabilityVerificationError("survivability inventory must be non-empty")
    expected_paths: set[str] = set()
    for item in raw_inventory:
        record = _mapping(item, "survivability inventory record")
        _strict_keys(record, frozenset({"path", "role", "size", "sha256"}), "inventory record")
        relative = _safe_relative(record.get("path"), "inventory path")
        if relative == SURVIVABILITY_MANIFEST_NAME or relative in expected_paths:
            raise OfflineSurvivabilityVerificationError("duplicate/reserved inventory path")
        role = _text(record.get("role"), "inventory role")
        if role not in _ALLOWED_ROLES:
            raise OfflineSurvivabilityVerificationError(f"unsupported inventory role: {role}")
        size = record.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise OfflineSurvivabilityVerificationError("invalid inventory size")
        digest = _sha256(record.get("sha256"), "inventory digest")
        candidate = _regular_file(root, relative)
        if candidate.stat().st_size != size or _file_sha256(candidate) != digest:
            raise OfflineSurvivabilityVerificationError(f"inventory mismatch: {relative}")
        expected_paths.add(relative)

    actual_paths: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise OfflineSurvivabilityVerificationError(
                f"bundle contains symlink: {path.relative_to(root).as_posix()}"
            )
        if path.is_dir():
            continue
        relative = path.relative_to(root).as_posix()
        if relative != SURVIVABILITY_MANIFEST_NAME:
            actual_paths.add(relative)
    if actual_paths != expected_paths:
        missing = sorted(expected_paths - actual_paths)
        unexpected = sorted(actual_paths - expected_paths)
        raise OfflineSurvivabilityVerificationError(
            f"bundle inventory boundary mismatch: missing={missing}; unexpected={unexpected}"
        )

    required = {
        "identity/long-range-manifest.json",
        "identity/replay-capsule.json",
        "identity/artifact-escrow-manifest.json",
        "supply-chain/manifest.json",
        "supply-chain/verifier.py",
        "verifier.py",
    }
    if not required.issubset(expected_paths):
        raise OfflineSurvivabilityVerificationError("required survivability material is missing")

    lrd = _verify_lrd(root, manifest)
    _verify_capsule(root, manifest, lrd)
    _verify_escrow(root, manifest, lrd, expected_paths)
    _verify_supply_chain(root, manifest)
    return declared_digest


def _cli() -> int:
    parser = argparse.ArgumentParser(description="LRD-01I standalone survivability verifier")
    parser.add_argument("bundle")
    parser.add_argument("--expected-digest", required=True)
    args = parser.parse_args()
    digest = verify_survivability_bundle(args.bundle, expected_digest=args.expected_digest)
    print("LRD-01I OFFLINE SURVIVABILITY VERIFY PASS")
    print("Bundle digest:", digest)
    print("Physical interpreter preserved: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
