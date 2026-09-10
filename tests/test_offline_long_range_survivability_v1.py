from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

import core.enterprise.supply_chain_continuity_v2 as continuity
import core.offline_survivability_verifier_v1 as standalone
from core.artifact_escrow_v1 import (
    ArtifactEscrowManifestV1,
    EscrowArtifactBindingV1,
    EscrowBlobIdentityV1,
    FileSystemEscrowBackendV1,
)
from core.case_ledger.contracts import ContentAddress
from core.enterprise.supply_chain_continuity_v2 import canonical_json_bytes, write_manifest
from core.long_range_replay_v1 import (
    LongRangeReplayManifestV1,
    ReplayArtifactBindingV1,
    ReplayArtifactRole,
    ReplayCapsuleV1,
    ReplayPreservationStatus,
)
from core.offline_long_range_survivability_v1 import (
    OfflineLongRangeSurvivabilityError,
    build_offline_survivability_bundle,
    verify_offline_survivability_bundle,
)
from core.offline_survivability_verifier_v1 import (
    OfflineSurvivabilityVerificationError,
    verify_survivability_bundle,
)

SOURCE_SHA = "a" * 40
TREE_SHA = "b" * 40


def _write_wheel(path: Path, *, name: str, version: str) -> None:
    dist = name.replace("-", "_")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(
            f"{dist}-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n\n",
        )
        archive.writestr(f"{dist}-{version}.dist-info/RECORD", "")


def _write_source_archive(path: Path, *, source_sha: str = SOURCE_SHA) -> None:
    data = b"print('historical source')\n"
    with tarfile.open(
        path,
        "w",
        format=tarfile.PAX_FORMAT,
        pax_headers={"comment": source_sha},
    ) as archive:
        info = tarfile.TarInfo("app.py")
        info.size = len(data)
        info.mtime = 0
        archive.addfile(info, BytesIO(data))


def _continuity_bundle(tmp_path: Path, *, source_sha: str = SOURCE_SHA) -> Path:
    root = tmp_path / f"continuity-{source_sha[:4]}"
    identity = root / "identity"
    wheelhouse = root / "wheelhouse"
    source = root / "source"
    identity.mkdir(parents=True)
    wheelhouse.mkdir()
    source.mkdir()
    (identity / "pyproject.toml").write_text(
        """
[build-system]
requires = ["setuptools==80.9.0"]
build-backend = "example"

[project]
name = "demo-project"
version = "1.0.0"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (identity / "pylock.toml").write_text(
        """
lock-version = "1.0"
created-by = "test"
requires-python = ">=3.11"

[[packages]]
name = "demo-project"
directory = { path = ".", editable = true }

[[packages]]
name = "foo"
version = "2.0"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (identity / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (identity / "lukart_build_backend.py").write_text("# backend\n", encoding="utf-8")
    assert continuity.__file__ is not None
    (root / "verifier.py").write_text(
        Path(continuity.__file__).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _write_source_archive(source / "repository.tar", source_sha=source_sha)
    _write_wheel(
        wheelhouse / "demo_project-1.0.0-py3-none-any.whl",
        name="demo-project",
        version="1.0.0",
    )
    _write_wheel(
        wheelhouse / "foo-2.0-py3-none-any.whl",
        name="foo",
        version="2.0",
    )
    _write_wheel(
        wheelhouse / "setuptools-80.9.0-py3-none-any.whl",
        name="setuptools",
        version="80.9.0",
    )
    write_manifest(root, source_sha=source_sha)
    return root


def _lrd_material(
    tmp_path: Path,
) -> tuple[
    LongRangeReplayManifestV1,
    ReplayCapsuleV1,
    ArtifactEscrowManifestV1,
    FileSystemEscrowBackendV1,
]:
    logical = {
        role: ContentAddress.for_value({"stage": "LRD-01I", "role": role.value})
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
    lrd = LongRangeReplayManifestV1.build(
        case_id="SYNTHETIC-LRD-01I",
        case_replay_manifest_identity=ContentAddress.for_value({"case_replay": "synthetic"}),
        coverage_matrix_identity=ContentAddress.for_value({"coverage": "synthetic"}),
        code_commit_sha=SOURCE_SHA,
        code_tree_sha=TREE_SHA,
        artifacts=artifacts,
        semantic_result_identity=logical[ReplayArtifactRole.SEMANTIC_RESULT],
    )
    capsule = ReplayCapsuleV1.build(manifest=lrd)
    backend = FileSystemEscrowBackendV1(tmp_path / "escrow")
    bindings: list[EscrowArtifactBindingV1] = []
    for role in ReplayArtifactRole:
        data = f"LRD-01I::{role.value}\n".encode()
        blob = backend.publish(data, limits=continuity_cast_limits())
        bindings.append(
            EscrowArtifactBindingV1.build(
                role=role,
                logical_identity=logical[role],
                blob=EscrowBlobIdentityV1.for_bytes(data),
            )
        )
    escrow = ArtifactEscrowManifestV1.build(long_range_manifest=lrd, bindings=bindings)
    return lrd, capsule, escrow, backend


def continuity_cast_limits():
    from core.artifact_escrow_v1 import EscrowLimitsV1

    return EscrowLimitsV1()


def _built(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    lrd, capsule, escrow, backend = _lrd_material(tmp_path)
    continuity_root = _continuity_bundle(tmp_path)
    output = tmp_path / "survivability"
    manifest = build_offline_survivability_bundle(
        output_root=output,
        lrd_manifest=lrd,
        replay_capsule=capsule,
        escrow_manifest=escrow,
        escrow_backend=backend,
        continuity_bundle_root=continuity_root,
    )
    return output, manifest


def test_lrd01i_builds_one_verified_offline_survivability_package(tmp_path: Path) -> None:
    root, manifest = _built(tmp_path)
    digest = str(manifest["bundle_digest"])

    assert verify_offline_survivability_bundle(root, expected_digest=digest) == digest
    assert verify_survivability_bundle(root, expected_digest=digest) == digest
    assert manifest["bootstrap_contract"] == {
        "network": "DENY",
        "registry": "NONE",
        "source_host": "NONE",
        "provider_access": "NONE",
        "compatible_python_required": True,
        "physical_interpreter_preserved": False,
    }
    assert (root / "supply-chain" / "source" / "repository.tar").is_file()
    assert (root / "verifier.py").is_file()


def test_lrd01i_embedded_verifier_runs_without_lukart_import_path(tmp_path: Path) -> None:
    root, manifest = _built(tmp_path)
    digest = str(manifest["bundle_digest"])
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)

    result = subprocess.run(
        [
            sys.executable,
            str(root / "verifier.py"),
            str(root),
            "--expected-digest",
            digest,
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert "LRD-01I OFFLINE SURVIVABILITY VERIFY PASS" in result.stdout


def test_lrd01i_rejects_tampered_escrow_bytes(tmp_path: Path) -> None:
    root, manifest = _built(tmp_path)
    digest = str(manifest["bundle_digest"])
    blob = next((root / "escrow").rglob("*"))
    while blob.is_dir():
        blob = next(path for path in blob.rglob("*") if path.is_file())
    blob.write_bytes(blob.read_bytes() + b"tamper")

    with pytest.raises(OfflineSurvivabilityVerificationError, match="inventory mismatch"):
        verify_survivability_bundle(root, expected_digest=digest)


def test_lrd01i_rejects_uninventoried_extra_file(tmp_path: Path) -> None:
    root, manifest = _built(tmp_path)
    digest = str(manifest["bundle_digest"])
    (root / "surprise.txt").write_text("unexpected", encoding="utf-8")

    with pytest.raises(OfflineSurvivabilityVerificationError, match="inventory boundary mismatch"):
        verify_survivability_bundle(root, expected_digest=digest)


def test_lrd01i_rejects_internal_manifest_rewrite_when_external_digest_is_pinned(
    tmp_path: Path,
) -> None:
    root, manifest = _built(tmp_path)
    original_digest = str(manifest["bundle_digest"])
    path = root / "survivability.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["bootstrap_contract"]["physical_interpreter_preserved"] = True
    payload.pop("bundle_digest")
    payload["bundle_digest"] = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    path.write_bytes(canonical_json_bytes(payload) + b"\n")

    with pytest.raises(OfflineSurvivabilityVerificationError):
        verify_survivability_bundle(root, expected_digest=original_digest)


def test_lrd01i_rejects_ssc_source_sha_not_matching_historical_code(tmp_path: Path) -> None:
    lrd, capsule, escrow, backend = _lrd_material(tmp_path)
    continuity_root = _continuity_bundle(tmp_path, source_sha="c" * 40)

    with pytest.raises(OfflineLongRangeSurvivabilityError, match="source SHA"):
        build_offline_survivability_bundle(
            output_root=tmp_path / "survivability",
            lrd_manifest=lrd,
            replay_capsule=capsule,
            escrow_manifest=escrow,
            escrow_backend=backend,
            continuity_bundle_root=continuity_root,
        )


def test_lrd01i_refuses_incomplete_lrd_material_even_when_identity_is_known(tmp_path: Path) -> None:
    lrd, _, escrow, backend = _lrd_material(tmp_path)
    artifacts = tuple(
        ReplayArtifactBindingV1(
            role=item.role,
            identity=item.identity,
            preservation=(
                ReplayPreservationStatus.REFERENCE_ONLY
                if item.role is ReplayArtifactRole.PROVIDER_MODELS
                else item.preservation
            ),
        )
        for item in lrd.artifacts
    )
    incomplete = LongRangeReplayManifestV1.build(
        case_id=lrd.case_id,
        case_replay_manifest_identity=lrd.case_replay_manifest_identity,
        coverage_matrix_identity=lrd.coverage_matrix_identity,
        code_commit_sha=lrd.code_commit_sha,
        code_tree_sha=lrd.code_tree_sha,
        artifacts=artifacts,
        semantic_result_identity=lrd.semantic_result_identity,
    )

    with pytest.raises(OfflineLongRangeSurvivabilityError, match="every LRD artifact"):
        build_offline_survivability_bundle(
            output_root=tmp_path / "survivability",
            lrd_manifest=incomplete,
            replay_capsule=ReplayCapsuleV1.build(manifest=incomplete),
            escrow_manifest=escrow,
            escrow_backend=backend,
            continuity_bundle_root=_continuity_bundle(tmp_path),
        )


def test_lrd01i_rejects_symlink_substitution(tmp_path: Path) -> None:
    root, manifest = _built(tmp_path)
    digest = str(manifest["bundle_digest"])
    target = root / "identity" / "long-range-manifest.json"
    original = target.read_bytes()
    target.unlink()
    external = tmp_path / "external.json"
    external.write_bytes(original)
    try:
        target.symlink_to(external)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")

    with pytest.raises(OfflineSurvivabilityVerificationError, match="symlink"):
        verify_survivability_bundle(root, expected_digest=digest)


def test_lrd01i_standalone_verifier_enforces_total_byte_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, manifest = _built(tmp_path)
    digest = str(manifest["bundle_digest"])
    monkeypatch.setattr(standalone, "_MAX_BUNDLE_BYTES", 1)

    with pytest.raises(OfflineSurvivabilityVerificationError, match="byte limit"):
        verify_survivability_bundle(root, expected_digest=digest)


def test_lrd01i_standalone_verifier_enforces_per_file_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, manifest = _built(tmp_path)
    digest = str(manifest["bundle_digest"])
    monkeypatch.setattr(standalone, "_MAX_FILE_BYTES", 1)

    with pytest.raises(OfflineSurvivabilityVerificationError, match="byte limit"):
        verify_survivability_bundle(root, expected_digest=digest)


def test_lrd01i_builder_rejects_symlinked_supply_chain_root(tmp_path: Path) -> None:
    lrd, capsule, escrow, backend = _lrd_material(tmp_path)
    continuity_root = _continuity_bundle(tmp_path)
    linked_root = tmp_path / "continuity-link"
    try:
        linked_root.symlink_to(continuity_root, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")

    with pytest.raises(OfflineLongRangeSurvivabilityError, match="regular directory"):
        build_offline_survivability_bundle(
            output_root=tmp_path / "survivability",
            lrd_manifest=lrd,
            replay_capsule=capsule,
            escrow_manifest=escrow,
            escrow_backend=backend,
            continuity_bundle_root=linked_root,
        )
