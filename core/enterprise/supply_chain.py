"""E4 software supply-chain controls.

The SBOM builder records the resolved Python environment that actually executes the gate. The
provenance model is SLSA-style evidence; this module does not claim an external SLSA certification.
"""

from __future__ import annotations

import importlib.metadata
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from core.p3.contracts import content_digest, require_hex_digest

from .contracts import EnterpriseContractError

_ACTION_REF = re.compile(r"^\s*uses:\s*([^\s#]+)", re.MULTILINE)
_FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
_DEP_NAME = re.compile(r"^\s*([A-Za-z0-9_.-]+)")


@dataclass(frozen=True, slots=True)
class WorkflowPinFinding:
    path: str
    reference: str
    reason: str


@dataclass(frozen=True, slots=True)
class WorkflowPinReport:
    scanned_files: int
    external_action_references: int
    findings: tuple[WorkflowPinFinding, ...]

    @property
    def passed(self) -> bool:
        return not self.findings


@dataclass(frozen=True, slots=True)
class ResolvedDependency:
    name: str
    version: str
    declared_requirement: str

    def canonical_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "version": self.version,
            "declared_requirement": self.declared_requirement,
        }


def _dependency_name(requirement: str) -> str:
    match = _DEP_NAME.match(requirement)
    if match is None:
        raise EnterpriseContractError(f"cannot parse dependency requirement: {requirement!r}")
    return match.group(1)


def read_project_metadata(pyproject_path: str | Path) -> tuple[str, str, tuple[str, ...]]:
    data = tomllib.loads(Path(pyproject_path).read_text(encoding="utf-8"))
    project = data.get("project")
    if not isinstance(project, dict):
        raise EnterpriseContractError("pyproject project table missing")
    name = str(project.get("name", "")).strip()
    version = str(project.get("version", "")).strip()
    dependencies = project.get("dependencies", [])
    if not name or not version or not isinstance(dependencies, list):
        raise EnterpriseContractError("invalid project metadata")
    requirements = tuple(str(item).strip() for item in dependencies)
    if any(not item for item in requirements):
        raise EnterpriseContractError("blank project dependency")
    return name, version, requirements


def resolve_dependencies(requirements: Sequence[str]) -> tuple[ResolvedDependency, ...]:
    resolved: list[ResolvedDependency] = []
    for requirement in requirements:
        name = _dependency_name(requirement)
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise EnterpriseContractError(f"declared dependency is not installed: {name}") from exc
        resolved.append(
            ResolvedDependency(
                name=name,
                version=version,
                declared_requirement=requirement,
            )
        )
    return tuple(sorted(resolved, key=lambda item: item.name.lower()))


def build_cyclonedx_sbom(pyproject_path: str | Path) -> dict[str, object]:
    name, version, requirements = read_project_metadata(pyproject_path)
    resolved = resolve_dependencies(requirements)
    components = [
        {
            "type": "library",
            "name": item.name,
            "version": item.version,
            "bom-ref": f"python:{item.name.lower()}@{item.version}",
            "properties": [
                {
                    "name": "lukart:declared-requirement",
                    "value": item.declared_requirement,
                }
            ],
        }
        for item in resolved
    ]
    bom: dict[str, object] = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": name,
                "version": version,
                "bom-ref": f"application:{name}@{version}",
            }
        },
        "components": components,
        "dependencies": [
            {
                "ref": f"application:{name}@{version}",
                "dependsOn": [component["bom-ref"] for component in components],
            }
        ],
    }
    bom["properties"] = [
        {"name": "lukart:sbom-scope", "value": "resolved-python-runtime"},
        {"name": "lukart:content-digest", "value": content_digest(bom)},
    ]
    return bom


def audit_workflow_action_pins(root: str | Path) -> WorkflowPinReport:
    workflows = Path(root) / ".github" / "workflows"
    paths = sorted((*workflows.glob("*.yml"), *workflows.glob("*.yaml")))
    findings: list[WorkflowPinFinding] = []
    external = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for match in _ACTION_REF.finditer(text):
            reference = match.group(1)
            if reference.startswith("./"):
                continue
            external += 1
            if "@" not in reference:
                findings.append(
                    WorkflowPinFinding(str(path), reference, "external action has no immutable ref")
                )
                continue
            _, ref = reference.rsplit("@", 1)
            if _FULL_SHA.fullmatch(ref) is None:
                findings.append(
                    WorkflowPinFinding(
                        str(path),
                        reference,
                        "external action must be pinned to a full 40-character commit SHA",
                    )
                )
    return WorkflowPinReport(
        scanned_files=len(paths),
        external_action_references=external,
        findings=tuple(findings),
    )


@dataclass(frozen=True, slots=True)
class ProvenanceMaterial:
    uri: str
    digest: str

    def __post_init__(self) -> None:
        if not self.uri.strip():
            raise EnterpriseContractError("provenance material URI is required")
        require_hex_digest(self.digest, field_name="material_digest")


@dataclass(frozen=True, slots=True)
class SlsaStyleProvenance:
    subject_name: str
    subject_digest: str
    source_sha: str
    builder_id: str
    build_type: str
    materials: tuple[ProvenanceMaterial, ...]
    parameters: Mapping[str, object]

    def __post_init__(self) -> None:
        if (
            not self.subject_name.strip()
            or not self.builder_id.strip()
            or not self.build_type.strip()
        ):
            raise EnterpriseContractError("provenance subject/builder/build_type are required")
        require_hex_digest(self.subject_digest, field_name="subject_digest")
        require_hex_digest(self.source_sha, field_name="source_sha", lengths=(40, 64))
        if not self.materials:
            raise EnterpriseContractError("provenance requires at least one material")

    def predicate(self) -> dict[str, object]:
        return {
            "_type": "https://in-toto.io/Statement/v1",
            "subject": [
                {
                    "name": self.subject_name,
                    "digest": {"sha256": self.subject_digest},
                }
            ],
            "predicateType": "https://slsa.dev/provenance/v1",
            "predicate": {
                "buildDefinition": {
                    "buildType": self.build_type,
                    "externalParameters": dict(self.parameters),
                    "internalParameters": {},
                    "resolvedDependencies": [
                        {"uri": item.uri, "digest": {"sha256": item.digest}}
                        for item in sorted(self.materials, key=lambda value: value.uri)
                    ],
                },
                "runDetails": {
                    "builder": {"id": self.builder_id},
                    "metadata": {"sourceSha": self.source_sha},
                },
            },
        }

    def digest(self) -> str:
        return content_digest(self.predicate())
