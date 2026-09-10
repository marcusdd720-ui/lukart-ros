from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from core.independent_review_readiness_v1 import (
    IRR_READINESS_STATUS,
    IRR_REVIEW_STATUS,
    IndependentReviewReadinessError,
    ReviewPackageResultV1,
    build_review_package_v1,
    verify_review_package_v1,
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "irr@example.invalid")
    _git(root, "config", "user.name", "IRR Test")
    files = {
        "README.md": "public readme\n",
        "MASTER_PLAN.md": "master plan\n",
        "SECURITY.md": "security\n",
        "pyproject.toml": "[project]\nname='fixture'\nversion='0.0.0'\n",
        "docs/WORKING_PRINCIPLES.md": "working principles\n",
        "docs/POST_HARDCORE_ROADMAP.md": "roadmap\n",
        "core/example.py": "VALUE = 1\n",
        "validation/example.py": "CHECK = True\n",
        "tests/test_example.py": "def test_ok():\n    assert True\n",
        ".github/workflows/ci.yml": "name: CI\n",
        "cases/private.txt": "not part of reviewer package\n",
        "data/runtime.txt": "not part of reviewer package\n",
        "evidence/runtime.txt": "not part of reviewer package\n",
        "reports/runtime.txt": "not part of reviewer package\n",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture")
    return root, _git(root, "rev-parse", "HEAD")


def _build(tmp_path: Path) -> tuple[Path, str, ReviewPackageResultV1]:
    root, commit = _repo(tmp_path)
    result = build_review_package_v1(
        repo_root=root,
        commit_sha=commit,
        output_dir=tmp_path / "out",
    )
    return root, commit, result


def _rewrite_package(
    source: Path,
    target_dir: Path,
    mutate: Callable[[dict[str, bytes]], None],
) -> Path:
    with zipfile.ZipFile(source, "r") as archive:
        members = {info.filename: archive.read(info.filename) for info in archive.infolist()}
    mutate(members)
    provisional = target_dir / "rewrite.zip"
    with zipfile.ZipFile(provisional, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, members[name])
    digest = hashlib.sha256(provisional.read_bytes()).hexdigest()
    original = source.name.split("-")
    commit = original[3]
    target = target_dir / f"IRR-01-v1-{commit}-{digest}.zip"
    provisional.replace(target)
    Path(f"{target}.sha256").write_text(f"{digest}  {target.name}\n", encoding="ascii")
    return target


def test_build_and_verify_content_addressed_public_package(tmp_path: Path) -> None:
    _, commit, result = _build(tmp_path)
    verified = verify_review_package_v1(result.package_path)

    assert verified.source_commit_sha == commit
    assert verified.package_sha256 == result.package_sha256
    assert verified.readiness_status == IRR_READINESS_STATUS
    assert verified.independent_review_status == IRR_REVIEW_STATUS
    assert result.package_sha256 in result.package_path.name


def test_manifest_never_claims_independent_review_or_certification(tmp_path: Path) -> None:
    _, _, result = _build(tmp_path)
    with zipfile.ZipFile(result.package_path, "r") as archive:
        manifest = json.loads(archive.read("IRR-01/manifest.json"))
        readme = archive.read("IRR-01/REVIEW_README.md").decode("utf-8")

    assert manifest["readiness_status"] == "READY_FOR_INDEPENDENT_REVIEW"
    assert manifest["independent_review_status"] == "NOT_INDEPENDENTLY_REVIEWED"
    assert manifest["authority"] == "readiness-only-no-review-no-certification"
    assert "did **not** perform an independent" in readme
    assert "did **not** certify" in readme


def test_runtime_case_and_generated_roots_are_excluded(tmp_path: Path) -> None:
    _, _, result = _build(tmp_path)
    with zipfile.ZipFile(result.package_path, "r") as archive:
        names = set(archive.namelist())

    assert "IRR-01/repository/core/example.py" in names
    forbidden_paths = (
        "cases/private.txt",
        "data/runtime.txt",
        "evidence/runtime.txt",
        "reports/runtime.txt",
    )
    for forbidden in forbidden_paths:
        assert f"IRR-01/repository/{forbidden}" not in names


def test_dirty_workspace_cannot_change_exact_commit_package(tmp_path: Path) -> None:
    root, commit, first = _build(tmp_path)
    (root / "README.md").write_text("dirty uncommitted replacement\n", encoding="utf-8")
    (root / "untracked-secret.txt").write_text("workspace only\n", encoding="utf-8")
    second = build_review_package_v1(
        repo_root=root,
        commit_sha=commit,
        output_dir=tmp_path / "out2",
    )

    assert second.package_sha256 == first.package_sha256
    assert second.package_path.read_bytes() == first.package_path.read_bytes()


def test_same_commit_build_is_deterministic(tmp_path: Path) -> None:
    root, commit, first = _build(tmp_path)
    second = build_review_package_v1(
        repo_root=root,
        commit_sha=commit,
        output_dir=tmp_path / "other",
    )
    assert second.package_sha256 == first.package_sha256
    assert second.package_path.read_bytes() == first.package_path.read_bytes()


def test_abbreviated_commit_sha_is_rejected(tmp_path: Path) -> None:
    root, commit = _repo(tmp_path)
    with pytest.raises(IndependentReviewReadinessError, match="full 40-character"):
        build_review_package_v1(
            repo_root=root,
            commit_sha=commit[:12],
            output_dir=tmp_path / "out",
        )


def test_selected_symlink_is_rejected_fail_closed(tmp_path: Path) -> None:
    root, _ = _repo(tmp_path)
    (root / "core" / "target.txt").write_text("target\n", encoding="utf-8")
    (root / "core" / "link.txt").symlink_to("target.txt")
    _git(root, "add", "core/target.txt", "core/link.txt")
    _git(root, "commit", "-m", "add symlink")
    commit = _git(root, "rev-parse", "HEAD")

    with pytest.raises(IndependentReviewReadinessError, match="symlink/submodule"):
        build_review_package_v1(
            repo_root=root,
            commit_sha=commit,
            output_dir=tmp_path / "out",
        )


def test_missing_mandatory_canon_is_rejected(tmp_path: Path) -> None:
    root, _ = _repo(tmp_path)
    _git(root, "rm", "docs/WORKING_PRINCIPLES.md")
    _git(root, "commit", "-m", "remove canon")
    commit = _git(root, "rev-parse", "HEAD")

    with pytest.raises(IndependentReviewReadinessError, match="mandatory public review paths"):
        build_review_package_v1(
            repo_root=root,
            commit_sha=commit,
            output_dir=tmp_path / "out",
        )


def test_archive_byte_tamper_is_rejected_before_trust(tmp_path: Path) -> None:
    _, _, result = _build(tmp_path)
    tampered = tmp_path / result.package_path.name
    tampered.write_bytes(result.package_path.read_bytes() + b"tamper")
    Path(f"{tampered}.sha256").write_text(
        result.sha256_path.read_text(encoding="ascii"),
        encoding="ascii",
    )

    with pytest.raises(IndependentReviewReadinessError, match="does not match filename"):
        verify_review_package_v1(tampered)


def test_status_tamper_is_rejected_even_with_new_outer_digest(tmp_path: Path) -> None:
    _, _, result = _build(tmp_path)

    def mutate(members: dict[str, bytes]) -> None:
        manifest = json.loads(members["IRR-01/manifest.json"])
        manifest["independent_review_status"] = "INDEPENDENTLY_REVIEWED"
        members["IRR-01/manifest.json"] = (
            json.dumps(manifest, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"
        ).encode("utf-8")

    tampered = _rewrite_package(result.package_path, tmp_path, mutate)
    with pytest.raises(IndependentReviewReadinessError, match="independent_review_status mismatch"):
        verify_review_package_v1(tampered)


def test_path_traversal_member_is_rejected_even_with_valid_outer_digest(tmp_path: Path) -> None:
    _, _, result = _build(tmp_path)

    def mutate(members: dict[str, bytes]) -> None:
        members["IRR-01/repository/../escape.txt"] = b"escape"

    tampered = _rewrite_package(result.package_path, tmp_path, mutate)
    with pytest.raises(IndependentReviewReadinessError, match="unsafe ZIP member"):
        verify_review_package_v1(tampered)


def test_missing_or_rewritten_sidecar_is_rejected(tmp_path: Path) -> None:
    _, _, result = _build(tmp_path)
    result.sha256_path.write_text("0" * 64 + f"  {result.package_path.name}\n", encoding="ascii")

    with pytest.raises(IndependentReviewReadinessError, match="sidecar mismatch"):
        verify_review_package_v1(result.package_path)
