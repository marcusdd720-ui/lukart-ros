from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from core.enterprise.contracts import EnterpriseContractError
from core.enterprise.supply_chain import (
    ProvenanceMaterial,
    SlsaStyleProvenance,
    build_cyclonedx_sbom,
    validate_cyclonedx_sbom,
)
from core.p3.contracts import content_digest
from scripts.hardcore_h3_provenance import (
    DEFAULT_ARTIFACTS,
    BuilderContext,
    build_h3_evidence,
    validate_h3_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_SHA = "a" * 40
WORKFLOW_SHA = "b" * 40


def _builder(**overrides: str) -> BuilderContext:
    values = {
        "repository": "marcusdd720-ui/lukart-ros",
        "workflow_path": ".github/workflows/enterprise-hardening.yml",
        "workflow_ref": (
            "marcusdd720-ui/lukart-ros/.github/workflows/enterprise-hardening.yml@refs/pull/1/merge"
        ),
        "workflow_sha": WORKFLOW_SHA,
        "run_id": "123",
        "run_attempt": "1",
        "runner_os": "Linux",
        "runner_arch": "X64",
        "python_version": "3.11.16",
    }
    values.update(overrides)
    return BuilderContext(**values)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _resign_sbom(bom: dict[str, object]) -> None:
    properties = bom["properties"]
    assert isinstance(properties, list)
    unsigned = dict(bom)
    unsigned.pop("properties")
    digest = content_digest(unsigned)
    for item in properties:
        assert isinstance(item, dict)
        if item.get("name") == "lukart:content-digest":
            item["value"] = digest
            return
    raise AssertionError("content digest property missing")


def _prepared_root(tmp_path: Path) -> Path:
    shutil.copy2(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    workflow = tmp_path / ".github" / "workflows" / "enterprise-hardening.yml"
    workflow.parent.mkdir(parents=True)
    shutil.copy2(ROOT / ".github" / "workflows" / "enterprise-hardening.yml", workflow)

    bom = build_cyclonedx_sbom(tmp_path / "pyproject.toml", extras=("dev",))
    _write_json(tmp_path / "build" / "enterprise" / "bom.cdx.json", bom)
    for relative in DEFAULT_ARTIFACTS:
        if relative == "build/enterprise/bom.cdx.json":
            continue
        _write_json(tmp_path / relative, {"artifact": relative, "candidate_sha": CANDIDATE_SHA})
    return tmp_path


def test_h3_sbom_dependency_boundary_includes_dev_and_validates() -> None:
    bom = build_cyclonedx_sbom(ROOT / "pyproject.toml", extras=("dev",))
    digest = validate_cyclonedx_sbom(bom, ROOT / "pyproject.toml", extras=("dev",))
    assert len(digest) == 64
    properties = bom["properties"]
    assert isinstance(properties, list)
    assert {item["value"] for item in properties if item["name"] == "lukart:dependency-groups"} == {
        "dev,runtime"
    }


def test_h3_sbom_rejects_content_tamper() -> None:
    bom = build_cyclonedx_sbom(ROOT / "pyproject.toml", extras=("dev",))
    components = bom["components"]
    assert isinstance(components, list)
    component = components[0]
    assert isinstance(component, dict)
    component["version"] = "tampered"
    with pytest.raises(EnterpriseContractError, match="content digest mismatch"):
        validate_cyclonedx_sbom(bom, ROOT / "pyproject.toml", extras=("dev",))


def test_h3_sbom_rejects_dependency_boundary_drift() -> None:
    bom = build_cyclonedx_sbom(ROOT / "pyproject.toml", extras=("dev",))
    components = bom["components"]
    assert isinstance(components, list)
    components.pop()
    dependencies = bom["dependencies"]
    assert isinstance(dependencies, list)
    root_dependency = dependencies[0]
    assert isinstance(root_dependency, dict)
    root_dependency["dependsOn"] = [
        item["bom-ref"] for item in components if isinstance(item, dict)
    ]
    _resign_sbom(bom)
    with pytest.raises(EnterpriseContractError, match="dependency boundary mismatch"):
        validate_cyclonedx_sbom(bom, ROOT / "pyproject.toml", extras=("dev",))


def test_h3_provenance_material_supports_exact_git_sha1() -> None:
    material = ProvenanceMaterial(
        uri="git+https://github.com/marcusdd720-ui/lukart-ros",
        digest=CANDIDATE_SHA,
        algorithm="sha1",
    )
    provenance = SlsaStyleProvenance(
        subject_name="manifest",
        subject_digest="c" * 64,
        source_sha=CANDIDATE_SHA,
        builder_id="https://github.com/example/builder",
        build_type="https://lukart.dev/build/v1",
        materials=(material,),
        parameters={},
    )
    resolved = provenance.predicate()["predicate"]
    assert isinstance(resolved, dict)
    build_definition = resolved["buildDefinition"]
    assert isinstance(build_definition, dict)
    dependencies = build_definition["resolvedDependencies"]
    assert isinstance(dependencies, list)
    assert dependencies[0]["digest"] == {"sha1": CANDIDATE_SHA}


def test_h3_provenance_rejects_unknown_digest_algorithm() -> None:
    with pytest.raises(EnterpriseContractError, match="unsupported provenance digest algorithm"):
        ProvenanceMaterial(uri="urn:test", digest="a" * 64, algorithm="sha512")


def test_h3_provenance_rejects_duplicate_material_identity() -> None:
    material = ProvenanceMaterial(uri="urn:test", digest="a" * 64)
    with pytest.raises(EnterpriseContractError, match="duplicate provenance material identity"):
        SlsaStyleProvenance(
            subject_name="manifest",
            subject_digest="c" * 64,
            source_sha=CANDIDATE_SHA,
            builder_id="https://github.com/example/builder",
            build_type="https://lukart.dev/build/v1",
            materials=(material, material),
            parameters={},
        )


def test_h3_build_and_validate_exact_evidence(tmp_path: Path) -> None:
    root = _prepared_root(tmp_path)
    builder = _builder()
    evidence = build_h3_evidence(CANDIDATE_SHA, builder, root=root)
    digest = validate_h3_evidence(evidence, CANDIDATE_SHA, builder, root=root)
    assert digest == evidence["evidence_digest"]
    assert evidence["candidate_sha"] == CANDIDATE_SHA
    statement = evidence["provenance_statement"]
    assert isinstance(statement, dict)
    assert statement["predicateType"] == "https://slsa.dev/provenance/v1"


def test_h3_validation_rejects_artifact_tamper(tmp_path: Path) -> None:
    root = _prepared_root(tmp_path)
    builder = _builder()
    evidence = build_h3_evidence(CANDIDATE_SHA, builder, root=root)
    target = root / "build" / "enterprise" / "scale-certification.json"
    target.write_text('{"tampered":true}\n', encoding="utf-8")
    with pytest.raises(EnterpriseContractError, match="provenance/material evidence mismatch"):
        validate_h3_evidence(evidence, CANDIDATE_SHA, builder, root=root)


def test_h3_validation_rejects_candidate_sha_mismatch(tmp_path: Path) -> None:
    root = _prepared_root(tmp_path)
    builder = _builder()
    evidence = build_h3_evidence(CANDIDATE_SHA, builder, root=root)
    with pytest.raises(EnterpriseContractError, match="provenance/material evidence mismatch"):
        validate_h3_evidence(evidence, "d" * 40, builder, root=root)


def test_h3_validation_rejects_provenance_statement_tamper(tmp_path: Path) -> None:
    root = _prepared_root(tmp_path)
    builder = _builder()
    evidence = build_h3_evidence(CANDIDATE_SHA, builder, root=root)
    tampered = copy.deepcopy(evidence)
    statement = tampered["provenance_statement"]
    assert isinstance(statement, dict)
    statement["predicateType"] = "https://example.invalid/provenance"
    with pytest.raises(EnterpriseContractError, match="provenance/material evidence mismatch"):
        validate_h3_evidence(tampered, CANDIDATE_SHA, builder, root=root)


def test_h3_builder_context_fails_closed_on_missing_or_invalid_identity() -> None:
    with pytest.raises(EnterpriseContractError, match="builder context missing"):
        _builder(workflow_ref="")
    with pytest.raises(EnterpriseContractError, match="run_id must be a positive integer"):
        _builder(run_id="0")
    with pytest.raises(Exception, match="workflow_sha"):
        _builder(workflow_sha="not-a-sha")


def test_h3_rejects_artifact_path_traversal(tmp_path: Path) -> None:
    root = _prepared_root(tmp_path)
    with pytest.raises(EnterpriseContractError, match="unsafe H3 artifact path"):
        build_h3_evidence(
            CANDIDATE_SHA,
            _builder(),
            root=root,
            artifact_paths=("../outside.json",),
        )


def test_h3_rejects_unpinned_workflow_dependency(tmp_path: Path) -> None:
    root = _prepared_root(tmp_path)
    workflow = root / ".github" / "workflows" / "enterprise-hardening.yml"
    text = workflow.read_text(encoding="utf-8")
    text = text.replace(
        "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803",
        "actions/checkout@v6",
        1,
    )
    workflow.write_text(text, encoding="utf-8")
    with pytest.raises(EnterpriseContractError, match="unpinned workflow dependency"):
        build_h3_evidence(CANDIDATE_SHA, _builder(), root=root)


def test_h3_rejects_duplicate_artifact_paths(tmp_path: Path) -> None:
    root = _prepared_root(tmp_path)
    with pytest.raises(EnterpriseContractError, match="duplicate paths"):
        build_h3_evidence(
            CANDIDATE_SHA,
            _builder(),
            root=root,
            artifact_paths=(
                "build/enterprise/bom.cdx.json",
                "build/enterprise/bom.cdx.json",
            ),
        )
