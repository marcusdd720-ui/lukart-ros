from __future__ import annotations

import argparse
import hashlib
import json
import platform
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from core.enterprise.contracts import EnterpriseContractError
from core.enterprise.supply_chain import (
    ProvenanceMaterial,
    SlsaStyleProvenance,
    audit_workflow_action_pins,
    validate_cyclonedx_sbom,
)
from core.p3.contracts import content_digest, require_hex_digest

ROOT = Path(__file__).resolve().parents[1]
H3_SCHEMA = "lukart.hardcore.h3-provenance.v1"
H3_BUILD_TYPE = "https://lukart.dev/build/enterprise-evidence/v1"
H3_SUBJECT_NAME = "lukart-enterprise-evidence-manifest"
DEFAULT_WORKFLOW_PATH = ".github/workflows/enterprise-hardening.yml"
DEFAULT_ARTIFACTS = (
    "build/hardcore/h1-baseline-evidence.json",
    "build/hardcore/h2-repository-policy-evidence.json",
    "build/enterprise/bom.cdx.json",
    "build/enterprise/scale-certification.json",
    "build/enterprise/enterprise-engineering-evidence.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_relative_path(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not value.strip():
        raise EnterpriseContractError(f"unsafe H3 artifact path: {value!r}")
    return path.as_posix()


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EnterpriseContractError(f"cannot read H3 JSON material: {path}") from exc
    if not isinstance(value, dict):
        raise EnterpriseContractError(f"H3 JSON material must be an object: {path}")
    return value


@dataclass(frozen=True, slots=True)
class BuilderContext:
    repository: str
    workflow_path: str
    workflow_ref: str
    workflow_sha: str
    run_id: str
    run_attempt: str
    runner_os: str
    runner_arch: str
    python_version: str

    def __post_init__(self) -> None:
        text_fields = {
            "repository": self.repository,
            "workflow_path": self.workflow_path,
            "workflow_ref": self.workflow_ref,
            "run_id": self.run_id,
            "run_attempt": self.run_attempt,
            "runner_os": self.runner_os,
            "runner_arch": self.runner_arch,
            "python_version": self.python_version,
        }
        for name, value in text_fields.items():
            if not value.strip():
                raise EnterpriseContractError(f"H3 builder context missing: {name}")
        workflow_sha = require_hex_digest(
            self.workflow_sha,
            field_name="workflow_sha",
            lengths=(40, 64),
        )
        if not self.run_id.isdigit() or int(self.run_id) <= 0:
            raise EnterpriseContractError("H3 run_id must be a positive integer")
        if not self.run_attempt.isdigit() or int(self.run_attempt) <= 0:
            raise EnterpriseContractError("H3 run_attempt must be a positive integer")
        normalized_path = _safe_relative_path(self.workflow_path)
        object.__setattr__(self, "repository", self.repository.strip())
        object.__setattr__(self, "workflow_path", normalized_path)
        object.__setattr__(self, "workflow_ref", self.workflow_ref.strip())
        object.__setattr__(self, "workflow_sha", workflow_sha)
        object.__setattr__(self, "run_id", self.run_id.strip())
        object.__setattr__(self, "run_attempt", self.run_attempt.strip())
        object.__setattr__(self, "runner_os", self.runner_os.strip())
        object.__setattr__(self, "runner_arch", self.runner_arch.strip())
        object.__setattr__(self, "python_version", self.python_version.strip())

    @property
    def builder_id(self) -> str:
        return f"https://github.com/{self.repository}/actions/workflows/{Path(self.workflow_path).name}"

    def canonical_dict(self) -> dict[str, str]:
        return {
            "repository": self.repository,
            "workflow_path": self.workflow_path,
            "workflow_ref": self.workflow_ref,
            "workflow_sha": self.workflow_sha,
            "run_id": self.run_id,
            "run_attempt": self.run_attempt,
            "runner_os": self.runner_os,
            "runner_arch": self.runner_arch,
            "python_version": self.python_version,
            "builder_id": self.builder_id,
        }


def build_h3_evidence(
    candidate_sha: str,
    builder: BuilderContext,
    *,
    root: Path = ROOT,
    artifact_paths: Sequence[str] = DEFAULT_ARTIFACTS,
) -> dict[str, object]:
    sha = require_hex_digest(candidate_sha, field_name="candidate_sha", lengths=(40, 64))
    if builder.repository != "marcusdd720-ui/lukart-ros":
        raise EnterpriseContractError(f"unexpected H3 repository identity: {builder.repository}")

    workflow_relative = _safe_relative_path(builder.workflow_path)
    workflow_path = root / workflow_relative
    if not workflow_path.is_file():
        raise EnterpriseContractError(f"H3 workflow identity file missing: {workflow_relative}")
    workflow_digest = _sha256(workflow_path)

    pin_report = audit_workflow_action_pins(root)
    if not pin_report.passed:
        findings = [f"{item.path}:{item.reference}" for item in pin_report.findings]
        raise EnterpriseContractError(f"H3 unpinned workflow dependency: {findings}")

    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.is_file():
        raise EnterpriseContractError("H3 pyproject material is missing")
    pyproject_digest = _sha256(pyproject_path)

    sbom_relative = "build/enterprise/bom.cdx.json"
    sbom_path = root / sbom_relative
    if not sbom_path.is_file():
        raise EnterpriseContractError("H3 SBOM material is missing")
    sbom = _load_json_object(sbom_path)
    dependency_identity_digest = validate_cyclonedx_sbom(
        sbom,
        pyproject_path,
        extras=("dev",),
    )
    sbom_file_digest = _sha256(sbom_path)

    normalized_artifacts = tuple(sorted({_safe_relative_path(item) for item in artifact_paths}))
    if len(normalized_artifacts) != len(artifact_paths):
        raise EnterpriseContractError("H3 artifact manifest contains duplicate paths")
    if sbom_relative not in normalized_artifacts:
        raise EnterpriseContractError("H3 artifact manifest must contain the dependency SBOM")

    artifact_manifest: dict[str, str] = {}
    for relative in normalized_artifacts:
        path = root / relative
        if not path.is_file():
            raise EnterpriseContractError(f"H3 artifact missing: {relative}")
        artifact_manifest[relative] = _sha256(path)
    manifest_digest = content_digest(
        {
            "schema": "lukart.hardcore.h3-artifact-manifest.v1",
            "candidate_sha": sha,
            "artifacts": artifact_manifest,
        }
    )

    source_algorithm = "sha1" if len(sha) == 40 else "sha256"
    materials = (
        ProvenanceMaterial(
            uri=f"git+https://github.com/{builder.repository}@{sha}",
            digest=sha,
            algorithm=source_algorithm,
        ),
        ProvenanceMaterial(
            uri="file:pyproject.toml",
            digest=pyproject_digest,
        ),
        ProvenanceMaterial(
            uri=f"file:{workflow_relative}",
            digest=workflow_digest,
        ),
        ProvenanceMaterial(
            uri=f"file:{sbom_relative}",
            digest=sbom_file_digest,
        ),
        ProvenanceMaterial(
            uri="urn:lukart:dependency-identity:v1",
            digest=dependency_identity_digest,
        ),
    )
    provenance = SlsaStyleProvenance(
        subject_name=H3_SUBJECT_NAME,
        subject_digest=manifest_digest,
        source_sha=sha,
        builder_id=builder.builder_id,
        build_type=H3_BUILD_TYPE,
        materials=materials,
        parameters={
            "schema": H3_SCHEMA,
            "repository": builder.repository,
            "workflow_path": workflow_relative,
            "workflow_ref": builder.workflow_ref,
            "workflow_sha": builder.workflow_sha,
            "run_id": builder.run_id,
            "run_attempt": builder.run_attempt,
            "runner_os": builder.runner_os,
            "runner_arch": builder.runner_arch,
            "python_version": builder.python_version,
            "dependency_identity_digest": dependency_identity_digest,
            "artifact_manifest_digest": manifest_digest,
        },
    )

    evidence: dict[str, object] = {
        "schema": H3_SCHEMA,
        "candidate_sha": sha,
        "builder": builder.canonical_dict(),
        "workflow_file_digest": workflow_digest,
        "pyproject_digest": pyproject_digest,
        "sbom_file_digest": sbom_file_digest,
        "dependency_identity_digest": dependency_identity_digest,
        "artifact_manifest": artifact_manifest,
        "artifact_manifest_digest": manifest_digest,
        "action_pin_report": {
            "scanned_files": pin_report.scanned_files,
            "external_action_references": pin_report.external_action_references,
            "findings": [],
        },
        "provenance_statement": provenance.predicate(),
        "provenance_digest": provenance.digest(),
        "claim_boundary": (
            "SLSA-style engineering provenance only; this evidence does not claim external "
            "SLSA certification or independent review."
        ),
    }
    evidence["evidence_digest"] = content_digest(evidence)
    return evidence


def validate_h3_evidence(
    evidence: Mapping[str, object],
    expected_candidate_sha: str,
    builder: BuilderContext,
    *,
    root: Path = ROOT,
    artifact_paths: Sequence[str] = DEFAULT_ARTIFACTS,
) -> str:
    expected = build_h3_evidence(
        expected_candidate_sha,
        builder,
        root=root,
        artifact_paths=artifact_paths,
    )
    if dict(evidence) != expected:
        raise EnterpriseContractError("H3 provenance/material evidence mismatch")
    digest = evidence.get("evidence_digest")
    if not isinstance(digest, str):
        raise EnterpriseContractError("H3 evidence digest is missing")
    return require_hex_digest(digest, field_name="h3_evidence_digest")


def _builder_from_args(args: argparse.Namespace) -> BuilderContext:
    return BuilderContext(
        repository=args.repository,
        workflow_path=args.workflow_path,
        workflow_ref=args.workflow_ref,
        workflow_sha=args.workflow_sha,
        run_id=args.run_id,
        run_attempt=args.run_attempt,
        runner_os=args.runner_os,
        runner_arch=args.runner_arch,
        python_version=platform.python_version(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build exact-SHA H3 supply-chain provenance")
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--workflow-path", default=DEFAULT_WORKFLOW_PATH)
    parser.add_argument("--workflow-ref", required=True)
    parser.add_argument("--workflow-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--runner-os", required=True)
    parser.add_argument("--runner-arch", required=True)
    parser.add_argument(
        "--output",
        default="build/hardcore/h3-supply-chain-provenance.json",
    )
    args = parser.parse_args()

    builder = _builder_from_args(args)
    evidence = build_h3_evidence(args.candidate_sha, builder)
    validate_h3_evidence(evidence, args.candidate_sha, builder)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("H3_SUPPLY_CHAIN_PROVENANCE=PASS")
    print(f"H3_CANDIDATE_SHA={evidence['candidate_sha']}")
    print(f"H3_DEPENDENCY_IDENTITY={evidence['dependency_identity_digest']}")
    print(f"H3_PROVENANCE_DIGEST={evidence['provenance_digest']}")
    print(f"H3_EVIDENCE_DIGEST={evidence['evidence_digest']}")
    print(f"H3_EVIDENCE_PATH={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
