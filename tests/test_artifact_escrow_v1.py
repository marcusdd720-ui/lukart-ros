from __future__ import annotations

import io
import os
import stat
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

from core.artifact_escrow_v1 import (
    ArtifactEscrowError,
    ArtifactEscrowManifestV1,
    EscrowArtifactBindingV1,
    EscrowArtifactKind,
    EscrowLimitsV1,
    FileSystemEscrowBackendV1,
    OfflineReplayReceiptV1,
    OfflineReplayRunnerV1,
    extract_verified_zip,
    migrate_verified_blob,
    validate_zip_bytes,
)
from core.case_ledger.contracts import ContentAddress
from core.long_range_replay_v1 import (
    LongRangeReplayManifestV1,
    ReplayArtifactBindingV1,
    ReplayArtifactRole,
    ReplayPreservationStatus,
)

COMMIT_SHA = "a" * 40
TREE_SHA = "b" * 40
CASE_ID = "CASE-LRD-01C-0001"


def _logical_identity(role: ReplayArtifactRole) -> ContentAddress:
    return ContentAddress.for_value({"logical-role": role.value})


def _long_range_manifest(
    *,
    case_id: str = CASE_ID,
    unavailable_role: ReplayArtifactRole | None = None,
) -> LongRangeReplayManifestV1:
    artifacts: list[ReplayArtifactBindingV1] = []
    for role in ReplayArtifactRole:
        preservation = (
            ReplayPreservationStatus.UNAVAILABLE
            if role is unavailable_role
            else ReplayPreservationStatus.PRESERVED
        )
        artifacts.append(
            ReplayArtifactBindingV1(
                role=role,
                identity=_logical_identity(role),
                preservation=preservation,
            )
        )
    return LongRangeReplayManifestV1.build(
        case_id=case_id,
        case_replay_manifest_identity=ContentAddress.for_value({"case-replay": case_id}),
        coverage_matrix_identity=ContentAddress.for_value({"coverage": "LRD-01A"}),
        code_commit_sha=COMMIT_SHA,
        code_tree_sha=TREE_SHA,
        artifacts=artifacts,
        semantic_result_identity=_logical_identity(ReplayArtifactRole.SEMANTIC_RESULT),
        presentation_identity=None,
    )


def _materialize_escrow(
    root: Path,
    *,
    long_range: LongRangeReplayManifestV1 | None = None,
    limits: EscrowLimitsV1 | None = None,
) -> tuple[
    FileSystemEscrowBackendV1,
    LongRangeReplayManifestV1,
    ArtifactEscrowManifestV1,
    EscrowLimitsV1,
]:
    policy = limits or EscrowLimitsV1()
    lrd = long_range or _long_range_manifest()
    backend = FileSystemEscrowBackendV1(root)
    bindings: list[EscrowArtifactBindingV1] = []
    by_role = {item.role: item for item in lrd.artifacts}
    for role in ReplayArtifactRole:
        artifact = by_role[role]
        if artifact.preservation is not ReplayPreservationStatus.PRESERVED:
            continue
        data = f"verified-bytes::{role.value}".encode()
        blob = backend.publish(data, limits=policy)
        bindings.append(
            EscrowArtifactBindingV1.build(
                role=role,
                logical_identity=artifact.identity,
                blob=blob,
            )
        )
    escrow = ArtifactEscrowManifestV1.build(
        long_range_manifest=lrd,
        bindings=bindings,
    )
    return backend, lrd, escrow, policy


def _stored_path(backend: FileSystemEscrowBackendV1, digest: str) -> Path:
    return backend.root / "sha256" / digest[:2] / digest


def _zip_bytes(entries: list[tuple[str, bytes]], *, compression: int = zipfile.ZIP_STORED) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return output.getvalue()


def test_publish_and_read_are_content_addressed_not_location_addressed(tmp_path: Path) -> None:
    limits = EscrowLimitsV1()
    first = FileSystemEscrowBackendV1(tmp_path / "first")
    second = FileSystemEscrowBackendV1(tmp_path / "second")
    payload = b"same canonical bytes"

    first_identity = first.publish(payload, limits=limits)
    second_identity = second.publish(payload, limits=limits)

    assert first_identity == second_identity
    assert first.read(first_identity, limits=limits) == payload
    assert second.read(second_identity, limits=limits) == payload
    assert first.root != second.root


def test_one_byte_tampering_is_rejected_on_every_read(tmp_path: Path) -> None:
    limits = EscrowLimitsV1()
    backend = FileSystemEscrowBackendV1(tmp_path / "escrow")
    identity = backend.publish(b"immutable-byte-sequence", limits=limits)
    stored = _stored_path(backend, identity.digest)
    stored.chmod(0o600)
    mutated = bytearray(stored.read_bytes())
    mutated[-1] ^= 0x01
    stored.write_bytes(mutated)

    with pytest.raises(ArtifactEscrowError, match="digest mismatch"):
        backend.read(identity, limits=limits)


def test_declared_size_tampering_is_rejected_before_trust(tmp_path: Path) -> None:
    limits = EscrowLimitsV1()
    backend = FileSystemEscrowBackendV1(tmp_path / "escrow")
    identity = backend.publish(b"bytes", limits=limits)
    raw = identity.canonical_dict()
    raw["size"] = identity.size + 1

    from core.artifact_escrow_v1 import EscrowBlobIdentityV1

    forged = EscrowBlobIdentityV1.from_dict(raw)
    with pytest.raises(ArtifactEscrowError, match="size mismatch"):
        backend.read(forged, limits=limits)


def test_escrow_manifest_exactly_covers_lrd_preserved_roles(tmp_path: Path) -> None:
    lrd = _long_range_manifest(unavailable_role=ReplayArtifactRole.PROVIDER_MODELS)
    _backend, _lrd, escrow, _limits = _materialize_escrow(tmp_path / "escrow", long_range=lrd)

    roles = {binding.role for binding in escrow.bindings}
    assert ReplayArtifactRole.PROVIDER_MODELS not in roles
    assert len(roles) == len(tuple(ReplayArtifactRole)) - 1
    escrow.verify_against(lrd)


def test_missing_preserved_binding_fails_closed(tmp_path: Path) -> None:
    _backend, lrd, escrow, _limits = _materialize_escrow(tmp_path / "escrow")

    with pytest.raises(ArtifactEscrowError, match="exactly cover PRESERVED"):
        ArtifactEscrowManifestV1.build(
            long_range_manifest=lrd,
            bindings=escrow.bindings[1:],
        )


def test_binding_logical_identity_substitution_fails_closed(tmp_path: Path) -> None:
    _backend, lrd, escrow, _limits = _materialize_escrow(tmp_path / "escrow")
    original = escrow.bindings[0]
    substituted = EscrowArtifactBindingV1.build(
        role=original.role,
        logical_identity=ContentAddress.for_value({"substituted": original.role.value}),
        blob=original.blob,
        kind=original.kind,
    )
    bindings = (substituted, *escrow.bindings[1:])

    with pytest.raises(ArtifactEscrowError, match="logical identity mismatch"):
        ArtifactEscrowManifestV1.build(
            long_range_manifest=lrd,
            bindings=bindings,
        )


def test_manifest_unknown_field_and_digest_tampering_fail_closed(tmp_path: Path) -> None:
    _backend, _lrd, escrow, _limits = _materialize_escrow(tmp_path / "escrow")
    unknown = escrow.canonical_dict()
    unknown["fallback_location"] = "somewhere"

    with pytest.raises(ArtifactEscrowError, match="unknown=fallback_location"):
        ArtifactEscrowManifestV1.from_dict(unknown)

    tampered = deepcopy(escrow.canonical_dict())
    bindings = tampered["bindings"]
    assert isinstance(bindings, list)
    first = bindings[0]
    assert isinstance(first, dict)
    blob = first["blob"]
    assert isinstance(blob, dict)
    digest = blob["digest"]
    assert isinstance(digest, str)
    blob["digest"] = ("0" if digest[0] != "0" else "1") + digest[1:]

    with pytest.raises(ArtifactEscrowError, match="binding identity mismatch"):
        ArtifactEscrowManifestV1.from_dict(tampered)


def test_alternate_storage_restore_preserves_exact_byte_identity(tmp_path: Path) -> None:
    limits = EscrowLimitsV1()
    source = FileSystemEscrowBackendV1(tmp_path / "source")
    target = FileSystemEscrowBackendV1(tmp_path / "alternate")
    original = source.publish(b"portable escrow payload", limits=limits)

    restored = migrate_verified_blob(
        original,
        source=source,
        target=target,
        limits=limits,
    )

    assert restored == original
    assert target.read(restored, limits=limits) == b"portable escrow payload"


def test_restore_path_traversal_is_rejected_without_outside_write(tmp_path: Path) -> None:
    limits = EscrowLimitsV1()
    backend = FileSystemEscrowBackendV1(tmp_path / "escrow")
    identity = backend.publish(b"blocked", limits=limits)
    destination = tmp_path / "restore"
    outside = tmp_path / "outside.txt"

    with pytest.raises(ArtifactEscrowError, match="unsafe restore path"):
        backend.restore_blob(
            identity,
            destination_root=destination,
            relative_path="../outside.txt",
            limits=limits,
        )

    assert not outside.exists()


def test_restore_symlink_escape_is_rejected_without_outside_write(tmp_path: Path) -> None:
    limits = EscrowLimitsV1()
    backend = FileSystemEscrowBackendV1(tmp_path / "escrow")
    identity = backend.publish(b"blocked", limits=limits)
    destination = tmp_path / "restore"
    destination.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = destination / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("host cannot create test symlink")

    with pytest.raises(ArtifactEscrowError, match="symlink escape rejected"):
        backend.restore_blob(
            identity,
            destination_root=destination,
            relative_path="link/pwned.txt",
            limits=limits,
        )

    assert not (outside / "pwned.txt").exists()


def test_zip_path_traversal_is_rejected_before_extraction(tmp_path: Path) -> None:
    limits = EscrowLimitsV1()
    backend = FileSystemEscrowBackendV1(tmp_path / "escrow")
    archive = _zip_bytes([("../escape.txt", b"forbidden")])
    identity = backend.publish(archive, limits=limits)
    destination = tmp_path / "expanded"

    with pytest.raises(ArtifactEscrowError, match="unsafe archive member path"):
        extract_verified_zip(
            identity,
            backend=backend,
            destination=destination,
            limits=limits,
        )

    assert not destination.exists()
    assert not (tmp_path / "escape.txt").exists()


def test_zip_symlink_member_is_rejected_before_extraction(tmp_path: Path) -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        info = zipfile.ZipInfo("link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "target")
    archive_bytes = output.getvalue()
    limits = EscrowLimitsV1()
    backend = FileSystemEscrowBackendV1(tmp_path / "escrow")
    identity = backend.publish(archive_bytes, limits=limits)

    with pytest.raises(ArtifactEscrowError, match="archive symlink rejected"):
        extract_verified_zip(
            identity,
            backend=backend,
            destination=tmp_path / "expanded",
            limits=limits,
        )


def test_decompression_bomb_ratio_is_rejected_preflight() -> None:
    archive = _zip_bytes(
        [("bomb.txt", b"A" * 100_000)],
        compression=zipfile.ZIP_DEFLATED,
    )
    limits = EscrowLimitsV1(max_compression_ratio=2)

    with pytest.raises(ArtifactEscrowError, match="compression ratio exceeds limit"):
        validate_zip_bytes(archive, limits=limits)


def test_decompression_bomb_expanded_size_is_rejected_preflight() -> None:
    archive = _zip_bytes([("large.bin", b"A" * 2048)])
    limits = EscrowLimitsV1(
        max_member_bytes=4096,
        max_expanded_bytes=1024,
    )

    with pytest.raises(ArtifactEscrowError, match="expanded size exceeds limit"):
        validate_zip_bytes(archive, limits=limits)


def test_safe_zip_extracts_to_new_destination_only(tmp_path: Path) -> None:
    limits = EscrowLimitsV1()
    backend = FileSystemEscrowBackendV1(tmp_path / "escrow")
    archive = _zip_bytes([("folder/file.txt", b"verified")])
    identity = backend.publish(archive, limits=limits)

    destination = extract_verified_zip(
        identity,
        backend=backend,
        destination=tmp_path / "expanded",
        limits=limits,
    )
    assert (destination / "folder" / "file.txt").read_bytes() == b"verified"

    with pytest.raises(ArtifactEscrowError, match="must not already exist"):
        extract_verified_zip(
            identity,
            backend=backend,
            destination=destination,
            limits=limits,
        )


def test_offline_runner_verifies_bytes_and_proves_network_probe_denial(tmp_path: Path) -> None:
    backend, lrd, escrow, limits = _materialize_escrow(tmp_path / "escrow")

    receipt = OfflineReplayRunnerV1(limits=limits).verify(
        expected_case_id=CASE_ID,
        long_range_manifest=lrd,
        escrow_manifest=escrow,
        escrow_root=backend.root,
    )

    assert receipt.network_mode == "OFF"
    assert receipt.network_enforcement == "python-runtime-guard"
    assert receipt.process_enforcement == "python-audit-hook-deny"
    assert receipt.native_ffi_enforcement == "python-audit-hook-deny"
    assert receipt.kernel_sandbox is False
    assert receipt.verified_blob_count == len(escrow.bindings)
    assert OfflineReplayReceiptV1.from_dict(receipt.canonical_dict()) == receipt


def test_offline_runner_rejects_cross_case_substitution(tmp_path: Path) -> None:
    backend, lrd, escrow, limits = _materialize_escrow(tmp_path / "escrow")

    with pytest.raises(ArtifactEscrowError, match="tenant/case scope mismatch"):
        OfflineReplayRunnerV1(limits=limits).verify(
            expected_case_id="CASE-OTHER",
            long_range_manifest=lrd,
            escrow_manifest=escrow,
            escrow_root=backend.root,
        )


def test_offline_runner_rejects_tampered_escrow_bytes(tmp_path: Path) -> None:
    backend, lrd, escrow, limits = _materialize_escrow(tmp_path / "escrow")
    binding = escrow.bindings[0]
    stored = _stored_path(backend, binding.blob.digest)
    stored.chmod(0o600)
    mutated = bytearray(stored.read_bytes())
    mutated[0] ^= 0x01
    stored.write_bytes(mutated)

    with pytest.raises(ArtifactEscrowError, match="offline runner failed"):
        OfflineReplayRunnerV1(limits=limits).verify(
            expected_case_id=CASE_ID,
            long_range_manifest=lrd,
            escrow_manifest=escrow,
            escrow_root=backend.root,
        )


def test_zip_binding_is_preflight_verified_inside_offline_runner(tmp_path: Path) -> None:
    limits = EscrowLimitsV1(max_compression_ratio=2)
    lrd = _long_range_manifest()
    backend = FileSystemEscrowBackendV1(tmp_path / "escrow")
    by_role = {item.role: item for item in lrd.artifacts}
    bindings: list[EscrowArtifactBindingV1] = []
    for role in ReplayArtifactRole:
        if role is ReplayArtifactRole.RUNTIME:
            data = _zip_bytes(
                [("runtime.bin", b"R" * 100_000)],
                compression=zipfile.ZIP_DEFLATED,
            )
            kind = EscrowArtifactKind.ZIP
        else:
            data = f"verified-bytes::{role.value}".encode()
            kind = EscrowArtifactKind.BLOB
        blob = backend.publish(data, limits=limits)
        bindings.append(
            EscrowArtifactBindingV1.build(
                role=role,
                logical_identity=by_role[role].identity,
                blob=blob,
                kind=kind,
            )
        )
    escrow = ArtifactEscrowManifestV1.build(
        long_range_manifest=lrd,
        bindings=bindings,
    )

    with pytest.raises(ArtifactEscrowError, match="offline runner failed"):
        OfflineReplayRunnerV1(limits=limits).verify(
            expected_case_id=CASE_ID,
            long_range_manifest=lrd,
            escrow_manifest=escrow,
            escrow_root=backend.root,
        )


def test_escrow_root_symlink_is_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    symlink = tmp_path / "escrow-link"
    try:
        symlink.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("host cannot create test symlink")

    with pytest.raises(ArtifactEscrowError, match="must not traverse a symlink"):
        FileSystemEscrowBackendV1(symlink)


def test_restore_rejects_existing_destination_without_overwrite(tmp_path: Path) -> None:
    limits = EscrowLimitsV1()
    backend = FileSystemEscrowBackendV1(tmp_path / "escrow")
    identity = backend.publish(b"new", limits=limits)
    destination = tmp_path / "restore"
    destination.mkdir()
    existing = destination / "artifact.bin"
    existing.write_bytes(b"old")

    with pytest.raises(ArtifactEscrowError, match="already exists"):
        backend.restore_blob(
            identity,
            destination_root=destination,
            relative_path="artifact.bin",
            limits=limits,
        )

    assert existing.read_bytes() == b"old"


def test_blob_size_bound_fails_before_publication(tmp_path: Path) -> None:
    limits = EscrowLimitsV1(max_blob_bytes=4, max_archive_bytes=4)
    backend = FileSystemEscrowBackendV1(tmp_path / "escrow")

    with pytest.raises(ArtifactEscrowError, match="max_blob_bytes"):
        backend.publish(b"12345", limits=limits)

    assert not any(path.is_file() for path in backend.root.rglob("*"))


def test_archive_member_count_bound_fails_closed() -> None:
    archive = _zip_bytes([("a", b"1"), ("b", b"2")])
    limits = EscrowLimitsV1(max_archive_members=1)

    with pytest.raises(ArtifactEscrowError, match="member count exceeds limit"):
        validate_zip_bytes(archive, limits=limits)


def test_offline_receipt_cannot_be_promoted_to_kernel_sandbox(tmp_path: Path) -> None:
    backend, lrd, escrow, limits = _materialize_escrow(tmp_path / "escrow")
    receipt = OfflineReplayRunnerV1(limits=limits).verify(
        expected_case_id=CASE_ID,
        long_range_manifest=lrd,
        escrow_manifest=escrow,
        escrow_root=backend.root,
    )
    raw = receipt.canonical_dict()
    raw["kernel_sandbox"] = True
    body = {key: value for key, value in raw.items() if key != "receipt_identity"}
    raw["receipt_identity"] = ContentAddress.for_value(body).canonical_dict()

    with pytest.raises(ArtifactEscrowError, match="cannot claim a kernel sandbox"):
        OfflineReplayReceiptV1.from_dict(raw)


def test_no_mutating_or_delete_method_is_exposed_by_filesystem_backend() -> None:
    public = {
        name
        for name in dir(FileSystemEscrowBackendV1)
        if not name.startswith("_")
    }

    assert "update" not in public
    assert "delete" not in public
    assert "overwrite" not in public
    assert {"publish", "read", "restore_blob"} <= public


def test_offline_runner_uses_fixed_entrypoint_not_caller_supplied_execution() -> None:
    public = {
        name
        for name in dir(OfflineReplayRunnerV1)
        if not name.startswith("_")
    }

    assert public == {"verify"}
    assert "run" not in public
    assert "execute" not in public


def test_os_symlink_creation_probe_does_not_leave_test_artifact(tmp_path: Path) -> None:
    """Keep adversarial symlink fixture cleanup explicit on hosts supporting symlinks."""

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("host cannot create test symlink")
    assert link.is_symlink()
    link.unlink()
    assert not link.exists()
