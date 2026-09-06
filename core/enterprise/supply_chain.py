"""E4 software supply-chain controls.

The SBOM builder records the declared dependencies resolved in the environment that actually
executes the gate. The provenance model is SLSA-style evidence; this module does not claim an
external SLSA certification.
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

_ACTION_REF = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.MULTILINE)
_FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
_DEP_NAME = re.compile(r"^\s*([A-Za-z0-9_.-]+)")
_DIGEST_LENGTHS = {"sha1": 40, "sha256": 64}


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
    group: str = "runtime"

    def canonical_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "version": self.version,
            "declared_requirement": self.declared_requirement,
            "group": self.group,
        }


def _dependency_name(requirement: str) -> str:
    match = _DEP_NAME.match(requirement)
    if match is None:
        raise EnterpriseContractError(f"cannot parse dependency requirement: {requirement!r}")
    return match.group(1)


def _project_table(pyproject_path: str | Path) -> dict[str, object]:
    data = tomllib.loads(Path(pyproject_path).read_text(encoding="utf-8"))
    project = data.get("project")
    if not isinstance(project, dict):
        raise EnterpriseContractError("pyproject project table missing")
    return project


def read_project_metadata(pyproject_path: str | Path) -> tuple[str, str, tuple[str, ...]]:
    project = _project_table(pyproject_path)
    name = str(project.get("name", "")).strip()
    version = str(project.get("version", "")).strip()
    dependencies = project.get("dependencies", [])
    if not name or not version or not isinstance(dependencies, list):
        raise EnterpriseContractError("invalid project metadata")
    requirements = tuple(str(item).strip() for item in dependencies)
    if any(not item for item in requirements):
        raise EnterpriseContractError("blank project dependency")
    return name, version, requirements


def read_project_dependency_groups(
    pyproject_path: str | Path,
    *,
    extras: Sequence[str] = (),
) -> tuple[tuple[str, str], ...]:
    """Return canonical ``(group, requirement)`` declarations for runtime and selected extras."""

    project = _project_table(pyproject_path)
    runtime = project.get("dependencies", [])
    if not isinstance(runtime, list):
        raise EnterpriseContractError("project dependencies must be a list")

    grouped: list[tuple[str, str]] = []
    for item in runtime:
        requirement = str(item).strip()
        if not requirement:
            raise EnterpriseContractError("blank project dependency")
        grouped.append(("runtime", requirement))

    optional = project.get("optional-dependencies", {})
    if not isinstance(optional, dict):
        raise EnterpriseContractError("project optional-dependencies must be a table")
    normalized_extras = tuple(sorted({str(extra).strip() for extra in extras}))
    if any(not extra for extra in normalized_extras):
        raise EnterpriseContractError("dependency extra cannot be blank")
    for extra in normalized_extras:
        requirements = optional.get(extra)
        if not isinstance(requirements, list):
            raise EnterpriseContractError(f"declared dependency extra is missing: {extra}")
        for item in requirements:
            requirement = str(item).strip()
            if not requirement:
                raise EnterpriseContractError(f"blank dependency in extra: {extra}")
            grouped.append((extra, requirement))

    seen_names: dict[str, str] = {}
    for group, requirement in grouped:
        normalized_name = _dependency_name(requirement).lower()
        previous = seen_names.get(normalized_name)
        if previous is not None:
            raise EnterpriseContractError(
                f"dependency declared in multiple groups: {normalized_name} ({previous}, {group})"
            )
        seen_names[normalized_name] = group
    return tuple(grouped)


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


def resolve_project_dependencies(
    pyproject_path: str | Path,
    *,
    extras: Sequence[str] = (),
) -> tuple[ResolvedDependency, ...]:
    resolved: list[ResolvedDependency] = []
    for group, requirement in read_project_dependency_groups(pyproject_path, extras=extras):
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
                group=group,
            )
        )
    return tuple(sorted(resolved, key=lambda item: (item.name.lower(), item.group)))


def build_cyclonedx_sbom(
    pyproject_path: str | Path,
    *,
    extras: Sequence[str] = (),
) -> dict[str, object]:
    name, version, _ = read_project_metadata(pyproject_path)
    resolved = resolve_project_dependencies(pyproject_path, extras=extras)
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
                },
                {"name": "lukart:dependency-group", "value": item.group},
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
    groups = sorted({item.group for item in resolved})
    bom["properties"] = [
        {"name": "lukart:sbom-scope", "value": "resolved-declared-dependencies"},
        {"name": "lukart:dependency-groups", "value": ",".join(groups)},
        {"name": "lukart:content-digest", "value": content_digest(bom)},
    ]
    return bom


def _property_map(value: object, *, field_name: str) -> dict[str, str]:
    if not isinstance(value, list):
        raise EnterpriseContractError(f"{field_name} properties must be a list")
    result: dict[str, str] = {}
    for raw in value:
        if not isinstance(raw, dict):
            raise EnterpriseContractError(f"{field_name} property must be an object")
        name = str(raw.get("name", "")).strip()
        property_value = str(raw.get("value", "")).strip()
        if not name or not property_value or name in result:
            raise EnterpriseContractError(f"invalid or duplicate {field_name} property")
        result[name] = property_value
    return result


def validate_cyclonedx_sbom(
    bom: Mapping[str, object],
    pyproject_path: str | Path,
    *,
    extras: Sequence[str] = (),
) -> str:
    """Validate SBOM/material consistency and return a canonical dependency identity digest."""

    if bom.get("bomFormat") != "CycloneDX" or bom.get("specVersion") != "1.7":
        raise EnterpriseContractError("unsupported CycloneDX SBOM contract")

    top_properties = _property_map(bom.get("properties"), field_name="SBOM")
    recorded_digest = top_properties.get("lukart:content-digest")
    if recorded_digest is None:
        raise EnterpriseContractError("SBOM content digest is missing")
    recorded_digest = require_hex_digest(recorded_digest, field_name="sbom_content_digest")
    unsigned = dict(bom)
    unsigned.pop("properties", None)
    if content_digest(unsigned) != recorded_digest:
        raise EnterpriseContractError("SBOM content digest mismatch")

    declared = read_project_dependency_groups(pyproject_path, extras=extras)
    expected: dict[str, tuple[str, str]] = {}
    for group, requirement in declared:
        name = _dependency_name(requirement).lower()
        expected[name] = (group, requirement)

    raw_components = bom.get("components")
    if not isinstance(raw_components, list):
        raise EnterpriseContractError("SBOM components must be a list")
    actual: dict[str, dict[str, str]] = {}
    component_refs: list[str] = []
    for raw_component in raw_components:
        if not isinstance(raw_component, dict):
            raise EnterpriseContractError("SBOM component must be an object")
        name = str(raw_component.get("name", "")).strip()
        version = str(raw_component.get("version", "")).strip()
        bom_ref = str(raw_component.get("bom-ref", "")).strip()
        if not name or not version or not bom_ref:
            raise EnterpriseContractError("SBOM component identity is incomplete")
        normalized_name = name.lower()
        if normalized_name in actual:
            raise EnterpriseContractError(f"duplicate SBOM component: {normalized_name}")
        expected_ref = f"python:{normalized_name}@{version}"
        if bom_ref != expected_ref:
            raise EnterpriseContractError(f"SBOM component ref mismatch: {normalized_name}")
        properties = _property_map(
            raw_component.get("properties"),
            field_name=f"component {normalized_name}",
        )
        declared_requirement = properties.get("lukart:declared-requirement")
        dependency_group = properties.get("lukart:dependency-group")
        if declared_requirement is None or dependency_group is None:
            raise EnterpriseContractError(
                f"SBOM dependency declaration metadata missing: {normalized_name}"
            )
        actual[normalized_name] = {
            "name": name,
            "version": version,
            "bom_ref": bom_ref,
            "declared_requirement": declared_requirement,
            "group": dependency_group,
        }
        component_refs.append(bom_ref)

    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        raise EnterpriseContractError(
            f"SBOM dependency boundary mismatch: missing={missing}, unexpected={unexpected}"
        )
    for name, (expected_group, expected_requirement) in expected.items():
        item = actual[name]
        if item["group"] != expected_group or item["declared_requirement"] != expected_requirement:
            raise EnterpriseContractError(f"SBOM dependency declaration mismatch: {name}")

    raw_dependencies = bom.get("dependencies")
    if not isinstance(raw_dependencies, list) or len(raw_dependencies) != 1:
        raise EnterpriseContractError("SBOM root dependency relation must be unique")
    root_dependency = raw_dependencies[0]
    if not isinstance(root_dependency, dict):
        raise EnterpriseContractError("SBOM root dependency relation must be an object")
    depends_on = root_dependency.get("dependsOn")
    if not isinstance(depends_on, list) or sorted(str(item) for item in depends_on) != sorted(
        component_refs
    ):
        raise EnterpriseContractError("SBOM dependency graph does not match components")

    expected_groups = ",".join(sorted({group for group, _ in declared}))
    if top_properties.get("lukart:dependency-groups") != expected_groups:
        raise EnterpriseContractError("SBOM dependency-group boundary mismatch")

    dependency_identity = [actual[name] for name in sorted(actual)]
    return content_digest(
        {
            "schema": "lukart.dependency-identity.v1",
            "sbom_content_digest": recorded_digest,
            "dependencies": dependency_identity,
        }
    )


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
    algorithm: str = "sha256"

    def __post_init__(self) -> None:
        uri = self.uri.strip()
        algorithm = self.algorithm.strip().lower()
        if not uri:
            raise EnterpriseContractError("provenance material URI is required")
        length = _DIGEST_LENGTHS.get(algorithm)
        if length is None:
            raise EnterpriseContractError(f"unsupported provenance digest algorithm: {algorithm}")
        digest = require_hex_digest(
            self.digest,
            field_name="material_digest",
            lengths=(length,),
        )
        object.__setattr__(self, "uri", uri)
        object.__setattr__(self, "algorithm", algorithm)
        object.__setattr__(self, "digest", digest)


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
        identities = [(item.uri, item.algorithm) for item in self.materials]
        if len(set(identities)) != len(identities):
            raise EnterpriseContractError("duplicate provenance material identity")

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
                        {"uri": item.uri, "digest": {item.algorithm: item.digest}}
                        for item in sorted(
                            self.materials,
                            key=lambda value: (value.uri, value.algorithm),
                        )
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
