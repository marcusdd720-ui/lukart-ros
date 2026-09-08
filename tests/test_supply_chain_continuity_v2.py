from __future__ import annotations

import hashlib
import json
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

import core.enterprise.supply_chain_continuity_v2 as continuity
from core.enterprise.supply_chain_continuity_v2 import (
    CONTINUITY_SCHEMA,
    MANIFEST_NAME,
    SupplyChainContinuityError,
    canonical_json_bytes,
    export_locked_constraints,
    verify_continuity_bundle,
    write_manifest,
)

SOURCE_SHA = "a" * 40


def _write_wheel(path: Path, *, name: str, version: str) -> None:
    dist = name.replace("-", "_")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(
            f"{dist}-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n\n",
        )
        archive.writestr(f"{dist}-{version}.dist-info/RECORD", "")


def _write_source_archive(path: Path, *, source_sha: str = SOURCE_SHA) -> None:
    data = b"print('source')\n"
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


def _bundle(tmp_path: Path, *, foo_version: str = "2.0") -> Path:
    root = tmp_path / "bundle"
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
    _write_source_archive(source / "repository.tar")

    _write_wheel(
        wheelhouse / "demo_project-1.0.0-py3-none-any.whl",
        name="demo-project",
        version="1.0.0",
    )
    _write_wheel(
        wheelhouse / f"foo-{foo_version}-py3-none-any.whl",
        name="foo",
        version=foo_version,
    )
    _write_wheel(
        wheelhouse / "setuptools-80.9.0-py3-none-any.whl",
        name="setuptools",
        version="80.9.0",
    )
    return root


def _rewrite_manifest(root: Path, payload: dict[str, object]) -> None:
    payload.pop("manifest_digest", None)
    payload["manifest_digest"] = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    (root / MANIFEST_NAME).write_bytes(canonical_json_bytes(payload) + b"\n")


def test_ssc02_bundle_verifies_with_lock_build_source_and_physical_wheels(tmp_path: Path) -> None:
    root = _bundle(tmp_path)
    manifest = write_manifest(root, source_sha=SOURCE_SHA)

    assert manifest["schema"] == CONTINUITY_SCHEMA
    digest = verify_continuity_bundle(root)
    assert digest == manifest["manifest_digest"]
    assert len(digest) == 64


def test_ssc02_manifest_is_deterministic_for_unchanged_bundle(tmp_path: Path) -> None:
    root = _bundle(tmp_path)
    first = write_manifest(root, source_sha=SOURCE_SHA)
    second = write_manifest(root, source_sha=SOURCE_SHA)

    assert first["manifest_digest"] == second["manifest_digest"]
    assert first == second


def test_ssc02_rejects_tampered_wheel(tmp_path: Path) -> None:
    root = _bundle(tmp_path)
    write_manifest(root, source_sha=SOURCE_SHA)
    wheel = root / "wheelhouse" / "foo-2.0-py3-none-any.whl"
    wheel.write_bytes(wheel.read_bytes() + b"tamper")

    with pytest.raises(SupplyChainContinuityError, match="(size|digest) mismatch"):
        verify_continuity_bundle(root)


def test_ssc02_rejects_uninventoried_file(tmp_path: Path) -> None:
    root = _bundle(tmp_path)
    write_manifest(root, source_sha=SOURCE_SHA)
    (root / "wheelhouse" / "surprise.txt").write_text("unexpected", encoding="utf-8")

    with pytest.raises(SupplyChainContinuityError, match="inventory boundary mismatch"):
        verify_continuity_bundle(root)


def test_ssc02_rejects_manifest_path_traversal_even_with_valid_manifest_digest(
    tmp_path: Path,
) -> None:
    root = _bundle(tmp_path)
    write_manifest(root, source_sha=SOURCE_SHA)
    payload = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    payload["inventory"][0]["path"] = "../escape"
    _rewrite_manifest(root, payload)

    with pytest.raises(SupplyChainContinuityError, match="unsafe path"):
        verify_continuity_bundle(root)


def test_ssc02_rejects_unknown_schema(tmp_path: Path) -> None:
    root = _bundle(tmp_path)
    write_manifest(root, source_sha=SOURCE_SHA)
    payload = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    payload["schema"] = "lukart.supply-chain-continuity.v999"
    _rewrite_manifest(root, payload)

    with pytest.raises(SupplyChainContinuityError, match="unsupported continuity schema"):
        verify_continuity_bundle(root)


def test_ssc02_rejects_wheel_version_outside_pylock(tmp_path: Path) -> None:
    root = _bundle(tmp_path, foo_version="9.9")

    with pytest.raises(SupplyChainContinuityError, match="not bound by pylock"):
        write_manifest(root, source_sha=SOURCE_SHA)


def test_ssc02_rejects_source_archive_not_bound_to_exact_commit(tmp_path: Path) -> None:
    root = _bundle(tmp_path)
    _write_source_archive(root / "source" / "repository.tar", source_sha="b" * 40)

    with pytest.raises(SupplyChainContinuityError, match="commit identity"):
        write_manifest(root, source_sha=SOURCE_SHA)


def test_ssc02_exports_exact_constraints_without_uv(tmp_path: Path) -> None:
    pylock = tmp_path / "pylock.toml"
    pylock.write_text(
        """
lock-version = "1.0"
created-by = "test"
requires-python = ">=3.11"

[[packages]]
name = "Zulu_Pkg"
version = "3.4"

[[packages]]
name = "alpha-pkg"
version = "1.2"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "constraints.txt"

    export_locked_constraints(pylock, output)

    assert output.read_text(encoding="utf-8") == "alpha-pkg==1.2\nZulu_Pkg==3.4\n"


def test_ssc02_preserves_pep751_markers_and_skips_local_project_source(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
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
    pylock = tmp_path / "pylock.toml"
    pylock.write_text(
        """
lock-version = "1.0"

[[packages]]
name = "demo-project"
directory = { path = ".", editable = true }

[[packages]]
name = "ast-serialize"
version = "0.9.0"
marker = "python_full_version >= '3.14'"

[[packages]]
name = "ast-serialize"
version = "0.10.0"
marker = "python_full_version < '3.14'"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "constraints.txt"

    export_locked_constraints(pylock, output)

    assert set(output.read_text(encoding="utf-8").splitlines()) == {
        "ast-serialize==0.9.0 ; python_full_version >= '3.14'",
        "ast-serialize==0.10.0 ; python_full_version < '3.14'",
    }


def test_ssc02_rejects_unescrowed_direct_source_dependency(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
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
    pylock = tmp_path / "pylock.toml"
    pylock.write_text(
        """
lock-version = "1.0"

[[packages]]
name = "demo-project"
directory = { path = ".", editable = true }

[[packages]]
name = "unescrowed-dep"
directory = { path = "../dep" }
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SupplyChainContinuityError, match="unsupported direct-source dependency"):
        export_locked_constraints(pylock, tmp_path / "constraints.txt")


def test_ssc02_uses_only_top_level_wheel_metadata_for_identity(tmp_path: Path) -> None:
    root = _bundle(tmp_path)
    setuptools = root / "wheelhouse" / "setuptools-80.9.0-py3-none-any.whl"
    with zipfile.ZipFile(setuptools, "a", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(
            "setuptools/_vendor/example-1.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: example\nVersion: 1.0\n\n",
        )

    manifest = write_manifest(root, source_sha=SOURCE_SHA)

    assert verify_continuity_bundle(root) == manifest["manifest_digest"]
