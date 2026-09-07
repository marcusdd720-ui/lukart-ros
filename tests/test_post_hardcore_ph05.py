from __future__ import annotations

import copy
import json
import tomllib
from pathlib import Path

import pytest

from core.p3.contracts import content_digest
from validation.release_contract import ReleaseContractError, resolve_release_intent
from validation.release_manifest import build_release_manifest

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
WORKFLOW = ROOT / ".github" / "workflows" / "mvros-v1-release.yml"
BASELINE_COMMIT = "802013c4d0e53dc12306a97e1877ebba86af64a7"


def _pyproject() -> dict[str, object]:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def test_ph05_current_version_has_one_ssot_and_release_is_disabled() -> None:
    data = _pyproject()
    enterprise = data["tool"]["lukart"]["enterprise"]  # type: ignore[index]
    assert isinstance(enterprise, dict)
    assert data["project"]["version"] == "1.1.0.dev0"  # type: ignore[index]
    assert "development_version" not in enterprise
    assert enterprise["release_enabled"] is False
    assert enterprise["immutable_releases_required"] is True
    assert enterprise["immutable_baseline_version"] == "1.0.1"
    assert enterprise["immutable_baseline_commit"] == BASELINE_COMMIT


def test_ph05_disabled_intent_uses_project_version_without_mutation() -> None:
    intent = resolve_release_intent(_pyproject())
    assert intent.project_version == "1.1.0.dev0"
    assert intent.release_enabled is False
    assert intent.tag == ""
    assert intent.immutable_baseline_commit == BASELINE_COMMIT


def test_ph05_legacy_second_version_ssot_is_rejected() -> None:
    data = copy.deepcopy(_pyproject())
    enterprise = data["tool"]["lukart"]["enterprise"]  # type: ignore[index]
    assert isinstance(enterprise, dict)
    enterprise["development_version"] = "1.1.0.dev0"
    with pytest.raises(ReleaseContractError, match="current-version SSOT"):
        resolve_release_intent(data)


def test_ph05_release_enabled_dev_version_is_rejected() -> None:
    data = copy.deepcopy(_pyproject())
    enterprise = data["tool"]["lukart"]["enterprise"]  # type: ignore[index]
    assert isinstance(enterprise, dict)
    enterprise["release_enabled"] = True
    with pytest.raises(ReleaseContractError, match="stable X.Y.Z"):
        resolve_release_intent(data)


def test_ph05_historical_baseline_cannot_be_released_again() -> None:
    data = copy.deepcopy(_pyproject())
    project = data["project"]
    enterprise = data["tool"]["lukart"]["enterprise"]  # type: ignore[index]
    assert isinstance(project, dict)
    assert isinstance(enterprise, dict)
    project["version"] = "1.0.1"
    enterprise["release_enabled"] = True
    with pytest.raises(ReleaseContractError, match="historical baseline"):
        resolve_release_intent(data)


def test_ph05_release_manifest_is_content_addressed_and_exact_sha_bound(tmp_path: Path) -> None:
    candidate = "a" * 40
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "lukart_ros-1.2.0-py3-none-any.whl").write_bytes(b"wheel")
    (dist / "SHA256SUMS").write_text("placeholder\n", encoding="utf-8")
    closure = tmp_path / "closure.json"
    closure.write_text(json.dumps({"candidate_sha": candidate}), encoding="utf-8")
    sbom = tmp_path / "bom.cdx.json"
    sbom.write_text("{}\n", encoding="utf-8")

    manifest = build_release_manifest(
        candidate_sha=candidate,
        version="1.2.0",
        tag="v1.2.0",
        dist_dir=dist,
        closure_manifest=closure,
        sbom=sbom,
    )
    stored = manifest["manifest_digest"]
    unsigned = dict(manifest)
    unsigned.pop("manifest_digest")
    assert stored == content_digest(unsigned)
    assert manifest["candidate_sha"] == candidate


def test_ph05_release_manifest_rejects_mixed_sha(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "lukart_ros-1.2.0-py3-none-any.whl").write_bytes(b"wheel")
    (dist / "SHA256SUMS").write_text("placeholder\n", encoding="utf-8")
    closure = tmp_path / "closure.json"
    closure.write_text(json.dumps({"candidate_sha": "b" * 40}), encoding="utf-8")
    sbom = tmp_path / "bom.cdx.json"
    sbom.write_text("{}\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="another SHA"):
        build_release_manifest(
            candidate_sha="a" * 40,
            version="1.2.0",
            tag="v1.2.0",
            dist_dir=dist,
            closure_manifest=closure,
            sbom=sbom,
        )


def test_ph05_workflow_separates_read_only_validation_build_and_publish() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "release-validate:" in workflow
    assert "release-build:" in workflow
    assert "release-publish:" in workflow
    assert "permissions:\n  actions: read\n  contents: read" in workflow
    assert "release-publish:\n" in workflow
    assert "contents: write" in workflow
    assert "development_version" not in workflow
    assert "python -m validation.release_contract" in workflow
    assert "repos/${GITHUB_REPOSITORY}/immutable-releases" in workflow
    assert "LUKART_RELEASE_POLICY_TOKEN" in workflow
    assert "--draft" in workflow
    assert 'gh release edit "${TAG}" --draft=false' in workflow
    assert 'payload.get("immutable") is not True' in workflow
    assert "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6" in workflow
    assert "build/post-hardcore/ph03-closure-manifest.json" in workflow


def test_ph05_publish_once_never_reuses_existing_release() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "Tag ${TAG} already exists; refusing release reuse or repair." in workflow
    assert "Release ${TAG} already exists; refusing release reuse or repair." in workflow
    assert "--clobber" not in workflow
