"""LRD-01I provider-neutral offline long-range survivability package v1.

The package composes existing LRD-01B, LRD-01C and SSC-02 artifacts. It does not
replace their identities or create Product, CCL, Gold, policy, trust, provider or
release authority. A compatible Python interpreter remains an explicit external
bootstrap requirement in v1; repository CI does not claim physical interpreter
preservation or universal future-platform executability.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import cast

from core.artifact_escrow_v1 import (
    ArtifactEscrowManifestV1,
    EscrowLimitsV1,
    FileSystemEscrowBackendV1,
)
from core.enterprise.supply_chain_continuity_v2 import (
    MANIFEST_NAME as SSC_MANIFEST_NAME,
)
from core.enterprise.supply_chain_continuity_v2 import (
    SupplyChainContinuityError,
    verify_continuity_bundle,
)
from core.long_range_replay_v1 import LongRangeReplayManifestV1, ReplayCapsuleV1
from core.offline_survivability_verifier_v1 import (
    SURVIVABILITY_MANIFEST_NAME,
    SURVIVABILITY_SCHEMA_V1,
    OfflineSurvivabilityVerificationError,
    verify_survivability_bundle,
)
from core.p3.contracts import canonical_json

_BOOTSTRAP_CONTRACT = {
    "network": "DENY",
    "registry": "NONE",
    "source_host": "NONE",
    "provider_access": "NONE",
    "compatible_python_required": True,
    "physical_interpreter_preserved": False,
}
_IDENTITY_PATHS = {
    "identity/long-range-manifest.json",
    "identity/replay-capsule.json",
    "identity/artifact-escrow-manifest.json",
}
_MAX_BUNDLE_FILES = 20_000
_MAX_BUNDLE_BYTES = 2 * 1024 * 1024 * 1024
_IO_CHUNK = 1024 * 1024


class OfflineLongRangeSurvivabilityError(ValueError):
    """Fail-closed LRD-01I package construction or verification error."""


def _canonical_bytes(value: object) -> bytes:
    return canonical_json(value).encode("utf-8") + b"\n"


def _json_object(path: Path, *, field_name: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise OfflineLongRangeSurvivabilityError(f"{field_name} must be a regular file")
    try:
        decoded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OfflineLongRangeSurvivabilityError(f"cannot read {field_name}") from exc
    if not isinstance(decoded, dict) or any(not isinstance(key, str) for key in decoded):
        raise OfflineLongRangeSurvivabilityError(f"{field_name} must be an object")
    return cast(dict[str, object], decoded)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_IO_CHUNK), b""):
                digest.update(chunk)
    except OSError as exc:
        raise OfflineLongRangeSurvivabilityError(f"cannot hash bundle file: {path}") from exc
    return digest.hexdigest()


def _safe_relative(path: Path, *, root: Path) -> str:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise OfflineLongRangeSurvivabilityError("bundle path escaped staging root") from exc
    pure = PurePosixPath(relative)
    if (
        not relative
        or "\\" in relative
        or pure.is_absolute()
        or any(part in {"", ".", ".."} for part in pure.parts)
        or pure.as_posix() != relative
    ):
        raise OfflineLongRangeSurvivabilityError(f"unsafe bundle path: {relative!r}")
    return relative


def _copy_tree_strict(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_dir():
        raise OfflineLongRangeSurvivabilityError("supply-chain bundle root must be a directory")
    target.mkdir(parents=True, exist_ok=False)
    file_count = 0
    total_bytes = 0
    for candidate in sorted(source.rglob("*"), key=lambda item: item.as_posix()):
        if candidate.is_symlink():
            raise OfflineLongRangeSurvivabilityError("supply-chain bundle contains a symlink")
        relative = candidate.relative_to(source)
        destination = target / relative
        if candidate.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        if not candidate.is_file():
            raise OfflineLongRangeSurvivabilityError(
                "supply-chain bundle contains a non-regular entry"
            )
        file_count += 1
        total_bytes += candidate.stat().st_size
        if file_count > _MAX_BUNDLE_FILES or total_bytes > _MAX_BUNDLE_BYTES:
            raise OfflineLongRangeSurvivabilityError("supply-chain material exceeds bundle limits")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(candidate, destination)


def _write_identity_files(
    stage: Path,
    *,
    lrd_manifest: LongRangeReplayManifestV1,
    replay_capsule: ReplayCapsuleV1,
    escrow_manifest: ArtifactEscrowManifestV1,
) -> None:
    identity = stage / "identity"
    identity.mkdir()
    (identity / "long-range-manifest.json").write_bytes(
        _canonical_bytes(lrd_manifest.canonical_dict())
    )
    (identity / "replay-capsule.json").write_bytes(
        _canonical_bytes(replay_capsule.canonical_dict())
    )
    (identity / "artifact-escrow-manifest.json").write_bytes(
        _canonical_bytes(escrow_manifest.canonical_dict())
    )


def _copy_escrow_blobs(
    stage: Path,
    *,
    escrow_manifest: ArtifactEscrowManifestV1,
    escrow_backend: FileSystemEscrowBackendV1,
    limits: EscrowLimitsV1,
) -> None:
    for binding in escrow_manifest.bindings:
        data = escrow_backend.read(binding.blob, limits=limits)
        destination = (
            stage
            / "escrow"
            / "sha256"
            / binding.blob.digest[:2]
            / binding.blob.digest
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.read_bytes() != data:
                raise OfflineLongRangeSurvivabilityError("escrow blob identity collision")
            continue
        destination.write_bytes(data)


def _classify(relative: str) -> str:
    if relative in _IDENTITY_PATHS:
        return "identity"
    if relative == "verifier.py":
        return "verifier"
    if relative.startswith("escrow/"):
        return "escrow_blob"
    if relative.startswith("supply-chain/"):
        return "supply_chain"
    raise OfflineLongRangeSurvivabilityError(f"unclassified survivability file: {relative}")


def _inventory(stage: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    total_bytes = 0
    for candidate in sorted(stage.rglob("*"), key=lambda item: item.as_posix()):
        if candidate.is_symlink():
            raise OfflineLongRangeSurvivabilityError("survivability staging contains a symlink")
        if candidate.is_dir():
            continue
        relative = _safe_relative(candidate, root=stage)
        if relative == SURVIVABILITY_MANIFEST_NAME:
            continue
        total_bytes += candidate.stat().st_size
        if len(records) + 1 > _MAX_BUNDLE_FILES or total_bytes > _MAX_BUNDLE_BYTES:
            raise OfflineLongRangeSurvivabilityError("survivability bundle exceeds limits")
        records.append(
            {
                "path": relative,
                "role": _classify(relative),
                "size": candidate.stat().st_size,
                "sha256": _sha256_file(candidate),
            }
        )
    return records


def _bundle_digest(payload: Mapping[str, object]) -> str:
    unsigned = dict(payload)
    unsigned.pop("bundle_digest", None)
    return hashlib.sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()


def _load_ssc_manifest(continuity_root: Path) -> tuple[dict[str, object], str]:
    try:
        digest = verify_continuity_bundle(continuity_root)
    except SupplyChainContinuityError as exc:
        raise OfflineLongRangeSurvivabilityError("SSC-02 continuity bundle rejected") from exc
    payload = _json_object(
        continuity_root / SSC_MANIFEST_NAME,
        field_name="SSC-02 manifest",
    )
    if payload.get("manifest_digest") != digest:
        raise OfflineLongRangeSurvivabilityError("SSC-02 manifest digest binding mismatch")
    return payload, digest


def build_offline_survivability_bundle(
    *,
    output_root: str | Path,
    lrd_manifest: LongRangeReplayManifestV1,
    replay_capsule: ReplayCapsuleV1,
    escrow_manifest: ArtifactEscrowManifestV1,
    escrow_backend: FileSystemEscrowBackendV1,
    continuity_bundle_root: str | Path,
    limits: EscrowLimitsV1 | None = None,
) -> dict[str, object]:
    """Build and atomically publish one complete provider-neutral survivability bundle."""

    lrd_manifest.verify()
    replay_capsule.verify()
    if replay_capsule.manifest != lrd_manifest:
        raise OfflineLongRangeSurvivabilityError(
            "replay capsule does not embed the supplied LRD manifest"
        )
    if not lrd_manifest.all_material_preserved:
        raise OfflineLongRangeSurvivabilityError(
            "offline survivability requires every LRD artifact to be PRESERVED"
        )
    escrow_manifest.verify_against(lrd_manifest)

    continuity_root = Path(continuity_bundle_root).resolve(strict=True)
    ssc_manifest, ssc_digest = _load_ssc_manifest(continuity_root)
    if ssc_manifest.get("source_sha") != lrd_manifest.code_commit_sha:
        raise OfflineLongRangeSurvivabilityError(
            "SSC-02 source SHA must equal the LRD historical code SHA"
        )
    python_identity = ssc_manifest.get("python")
    platform_identity = ssc_manifest.get("platform")
    if not isinstance(python_identity, dict) or not isinstance(platform_identity, dict):
        raise OfflineLongRangeSurvivabilityError("SSC-02 runtime identity is malformed")

    output = Path(output_root).expanduser().resolve(strict=False)
    if output.exists():
        raise OfflineLongRangeSurvivabilityError("survivability output must not already exist")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.stage-", dir=output.parent)
    )
    active_limits = limits or EscrowLimitsV1()
    try:
        _write_identity_files(
            stage,
            lrd_manifest=lrd_manifest,
            replay_capsule=replay_capsule,
            escrow_manifest=escrow_manifest,
        )
        _copy_escrow_blobs(
            stage,
            escrow_manifest=escrow_manifest,
            escrow_backend=escrow_backend,
            limits=active_limits,
        )
        _copy_tree_strict(continuity_root, stage / "supply-chain")

        verifier_source = Path(__file__).with_name("offline_survivability_verifier_v1.py")
        if verifier_source.is_symlink() or not verifier_source.is_file():
            raise OfflineLongRangeSurvivabilityError("standalone verifier source is unavailable")
        shutil.copyfile(verifier_source, stage / "verifier.py")

        payload: dict[str, object] = {
            "schema": SURVIVABILITY_SCHEMA_V1,
            "case_id": lrd_manifest.case_id,
            "code_commit_sha": lrd_manifest.code_commit_sha,
            "code_tree_sha": lrd_manifest.code_tree_sha,
            "lrd_manifest_identity": lrd_manifest.manifest_identity.canonical_dict(),
            "replay_capsule_identity": replay_capsule.capsule_identity.canonical_dict(),
            "escrow_manifest_identity": escrow_manifest.escrow_manifest_identity.canonical_dict(),
            "supply_chain_manifest_digest": ssc_digest,
            "supply_chain_runtime": {
                "python": python_identity,
                "platform": platform_identity,
            },
            "bootstrap_contract": dict(_BOOTSTRAP_CONTRACT),
            "inventory": _inventory(stage),
        }
        payload["bundle_digest"] = _bundle_digest(payload)
        (stage / SURVIVABILITY_MANIFEST_NAME).write_bytes(_canonical_bytes(payload))
        verify_survivability_bundle(
            stage,
            expected_digest=cast(str, payload["bundle_digest"]),
        )
        stage.rename(output)
        return payload
    except (OSError, OfflineSurvivabilityVerificationError) as exc:
        raise OfflineLongRangeSurvivabilityError("survivability bundle publication failed") from exc
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def verify_offline_survivability_bundle(
    bundle_root: str | Path,
    *,
    expected_digest: str,
) -> str:
    """Verify outer bytes with stdlib verifier, then re-check production nested contracts."""

    root = Path(bundle_root)
    try:
        verified = verify_survivability_bundle(root, expected_digest=expected_digest)
    except OfflineSurvivabilityVerificationError as exc:
        raise OfflineLongRangeSurvivabilityError("standalone survivability verification failed") from exc

    lrd = LongRangeReplayManifestV1.from_dict(
        _json_object(root / "identity" / "long-range-manifest.json", field_name="LRD manifest")
    )
    capsule = ReplayCapsuleV1.from_dict(
        _json_object(root / "identity" / "replay-capsule.json", field_name="replay capsule")
    )
    escrow = ArtifactEscrowManifestV1.from_dict(
        _json_object(
            root / "identity" / "artifact-escrow-manifest.json",
            field_name="escrow manifest",
        )
    )
    if capsule.manifest != lrd:
        raise OfflineLongRangeSurvivabilityError("nested replay capsule mismatch")
    escrow.verify_against(lrd)
    if not lrd.all_material_preserved:
        raise OfflineLongRangeSurvivabilityError("nested LRD material is incomplete")
    ssc_manifest, ssc_digest = _load_ssc_manifest(root / "supply-chain")
    if ssc_manifest.get("source_sha") != lrd.code_commit_sha:
        raise OfflineLongRangeSurvivabilityError("nested SSC-02 source SHA mismatch")
    outer = _json_object(root / SURVIVABILITY_MANIFEST_NAME, field_name="survivability manifest")
    if outer.get("supply_chain_manifest_digest") != ssc_digest:
        raise OfflineLongRangeSurvivabilityError("outer SSC-02 digest binding mismatch")
    return verified
