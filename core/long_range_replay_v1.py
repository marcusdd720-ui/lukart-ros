"""LRD-01B immutable long-range replay manifest and capsule contracts.

The contracts bind historical replay identity and execution-closure material without
creating a second Product/CCL authority. They are verification artifacts only.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from core.case_ledger.contracts import ContentAddress
from core.p3.contracts import canonical_json

LONG_RANGE_REPLAY_MANIFEST_SCHEMA_V1 = "lukart.long-range-replay-manifest.v1"
REPLAY_CAPSULE_SCHEMA_V1 = "lukart.replay-capsule.v1"

_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

_MANIFEST_KEYS = frozenset(
    {
        "schema",
        "case_id",
        "case_replay_manifest_identity",
        "coverage_matrix_identity",
        "code_commit_sha",
        "code_tree_sha",
        "artifacts",
        "semantic_result_identity",
        "presentation_identity",
        "manifest_identity",
    }
)
_ARTIFACT_KEYS = frozenset({"role", "identity", "preservation"})
_CAPSULE_KEYS = frozenset({"schema", "manifest", "supersedes_digest", "capsule_identity"})


class LongRangeReplayError(ValueError):
    """Fail-closed LRD manifest/capsule contract violation."""


class ReplayArtifactRole(StrEnum):
    """Fixed v1 execution-closure artifact roles.

    Aggregate roles bind canonical inventories. Physical byte preservation is handled by
    the later content-addressed escrow stage rather than by this manifest contract.
    """

    AUTHORIZATION_POLICY = "authorization_policy"
    CANONICALIZATION_PROFILES = "canonicalization_profiles"
    CASE_REPLAY_BUNDLE = "case_replay_bundle"
    CONFIG = "config"
    CRYPTO_PROFILE = "crypto_profile"
    DEPENDENCY_LOCK = "dependency_lock"
    DEPENDENCY_SET = "dependency_set"
    EPISTEMIC_POLICY = "epistemic_policy"
    EVIDENCE_INPUTS = "evidence_inputs"
    MIGRATION_REGISTRY = "migration_registry"
    PLUGIN_SET = "plugin_set"
    PROVIDER_MODELS = "provider_models"
    PROVIDER_REQUESTS = "provider_requests"
    PROVIDER_RESPONSES = "provider_responses"
    RENDERER = "renderer"
    RUNTIME = "runtime"
    SBOM = "sbom"
    SCHEMAS = "schemas"
    SEMANTIC_RESULT = "semantic_result"
    SOURCE_ARCHIVE = "source_archive"
    STORAGE_PROFILE = "storage_profile"
    TRUST_POLICY = "trust_policy"
    VERIFICATION_MATERIAL = "verification_material"


REQUIRED_MANIFEST_ARTIFACT_ROLES = tuple(sorted(role.value for role in ReplayArtifactRole))


class ReplayPreservationStatus(StrEnum):
    """Whether exact material is physically available to the replay boundary."""

    PRESERVED = "PRESERVED"
    REFERENCE_ONLY = "REFERENCE_ONLY"
    UNAVAILABLE = "UNAVAILABLE"


class ReplayAssuranceLevel(StrEnum):
    EXACT = "EXACT"
    SEMANTIC = "SEMANTIC"
    VERIFIED_EXTERNAL = "VERIFIED_EXTERNAL"
    UNVERIFIABLE = "UNVERIFIABLE"
    ABSTAIN = "ABSTAIN"


def _copy_mapping(value: Mapping[str, object], *, field_name: str) -> dict[str, object]:
    if any(not isinstance(key, str) for key in value):
        raise LongRangeReplayError(f"{field_name} keys must be strings")
    try:
        decoded: object = json.loads(canonical_json(dict(value)))
    except (TypeError, ValueError) as exc:
        raise LongRangeReplayError(f"{field_name} is not canonically serializable") from exc
    if not isinstance(decoded, dict):
        raise LongRangeReplayError(f"{field_name} must be an object")
    return cast(dict[str, object], decoded)


def _require_exact_keys(
    value: Mapping[str, object],
    *,
    expected: frozenset[str],
    field_name: str,
) -> None:
    actual = set(value)
    missing = tuple(sorted(expected - actual))
    unknown = tuple(sorted(actual - expected))
    if not missing and not unknown:
        return
    details: list[str] = []
    if missing:
        details.append("missing=" + ",".join(missing))
    if unknown:
        details.append("unknown=" + ",".join(unknown))
    raise LongRangeReplayError(f"{field_name} key contract violation: " + "; ".join(details))


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LongRangeReplayError(f"{field_name} must be a nonblank string")
    if value != value.strip():
        raise LongRangeReplayError(f"{field_name} must be canonical without whitespace")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise LongRangeReplayError(f"{field_name} cannot contain control characters")
    return value


def _git_sha(value: object, *, field_name: str) -> str:
    text = _text(value, field_name=field_name)
    if _GIT_SHA_RE.fullmatch(text) is None:
        raise LongRangeReplayError(f"{field_name} must be a lowercase full Git SHA")
    return text


def _address(value: object, *, field_name: str) -> ContentAddress:
    if not isinstance(value, Mapping):
        raise LongRangeReplayError(f"{field_name} must be a content-address object")
    try:
        return ContentAddress.from_dict(cast(Mapping[str, object], value))
    except ValueError as exc:
        raise LongRangeReplayError(str(exc)) from exc


def _optional_address(value: object, *, field_name: str) -> ContentAddress | None:
    if value is None:
        return None
    return _address(value, field_name=field_name)


@dataclass(frozen=True, slots=True)
class ReplayArtifactBindingV1:
    """One exact execution-closure identity and its current preservation status."""

    role: ReplayArtifactRole
    identity: ContentAddress
    preservation: ReplayPreservationStatus

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ReplayArtifactBindingV1:
        raw = _copy_mapping(value, field_name="replay artifact")
        _require_exact_keys(raw, expected=_ARTIFACT_KEYS, field_name="replay artifact")
        raw_role = _text(raw.get("role"), field_name="artifact role")
        raw_status = _text(raw.get("preservation"), field_name="artifact preservation")
        try:
            role = ReplayArtifactRole(raw_role)
            preservation = ReplayPreservationStatus(raw_status)
        except ValueError as exc:
            raise LongRangeReplayError("unknown replay artifact enum value") from exc
        return cls(
            role=role,
            identity=_address(raw.get("identity"), field_name="artifact identity"),
            preservation=preservation,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "role": self.role.value,
            "identity": self.identity.canonical_dict(),
            "preservation": self.preservation.value,
        }


@dataclass(frozen=True, slots=True)
class LongRangeReplayManifestV1:
    """Immutable execution-closure envelope over exact Case Replay v2 identity."""

    case_id: str
    case_replay_manifest_identity: ContentAddress
    coverage_matrix_identity: ContentAddress
    code_commit_sha: str
    code_tree_sha: str
    artifacts: tuple[ReplayArtifactBindingV1, ...]
    semantic_result_identity: ContentAddress
    presentation_identity: ContentAddress | None
    manifest_identity: ContentAddress
    schema: str = LONG_RANGE_REPLAY_MANIFEST_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != LONG_RANGE_REPLAY_MANIFEST_SCHEMA_V1:
            raise LongRangeReplayError(f"unsupported LRD manifest schema: {self.schema}")
        _text(self.case_id, field_name="case_id")
        _git_sha(self.code_commit_sha, field_name="code_commit_sha")
        _git_sha(self.code_tree_sha, field_name="code_tree_sha")
        roles = tuple(binding.role.value for binding in self.artifacts)
        if tuple(sorted(set(roles))) != roles:
            raise LongRangeReplayError("artifact roles must be unique and sorted")
        if roles != REQUIRED_MANIFEST_ARTIFACT_ROLES:
            required = set(REQUIRED_MANIFEST_ARTIFACT_ROLES)
            actual = set(roles)
            missing = tuple(sorted(required - actual))
            unknown = tuple(sorted(actual - required))
            details: list[str] = []
            if missing:
                details.append("missing=" + ",".join(missing))
            if unknown:
                details.append("unknown=" + ",".join(unknown))
            raise LongRangeReplayError(
                "LRD manifest artifact inventory is incomplete: " + "; ".join(details)
            )
        semantic_binding = next(
            binding
            for binding in self.artifacts
            if binding.role is ReplayArtifactRole.SEMANTIC_RESULT
        )
        renderer_binding = next(
            binding for binding in self.artifacts if binding.role is ReplayArtifactRole.RENDERER
        )
        if semantic_binding.identity != self.semantic_result_identity:
            raise LongRangeReplayError(
                "semantic_result_identity does not match semantic_result artifact"
            )
        if (
            self.presentation_identity is not None
            and renderer_binding.preservation is ReplayPreservationStatus.UNAVAILABLE
        ):
            raise LongRangeReplayError(
                "presentation identity cannot be bound when renderer material is unavailable"
            )
        self.verify()

    @classmethod
    def build(
        cls,
        *,
        case_id: str,
        case_replay_manifest_identity: ContentAddress,
        coverage_matrix_identity: ContentAddress,
        code_commit_sha: str,
        code_tree_sha: str,
        artifacts: Sequence[ReplayArtifactBindingV1],
        semantic_result_identity: ContentAddress,
        presentation_identity: ContentAddress | None = None,
    ) -> LongRangeReplayManifestV1:
        ordered = tuple(sorted(artifacts, key=lambda item: item.role.value))
        normalized_case_id = _text(case_id, field_name="case_id")
        normalized_commit = _git_sha(code_commit_sha, field_name="code_commit_sha")
        normalized_tree = _git_sha(code_tree_sha, field_name="code_tree_sha")
        body = {
            "schema": LONG_RANGE_REPLAY_MANIFEST_SCHEMA_V1,
            "case_id": normalized_case_id,
            "case_replay_manifest_identity": case_replay_manifest_identity.canonical_dict(),
            "coverage_matrix_identity": coverage_matrix_identity.canonical_dict(),
            "code_commit_sha": normalized_commit,
            "code_tree_sha": normalized_tree,
            "artifacts": [item.canonical_dict() for item in ordered],
            "semantic_result_identity": semantic_result_identity.canonical_dict(),
            "presentation_identity": (
                presentation_identity.canonical_dict()
                if presentation_identity is not None
                else None
            ),
        }
        return cls(
            case_id=normalized_case_id,
            case_replay_manifest_identity=case_replay_manifest_identity,
            coverage_matrix_identity=coverage_matrix_identity,
            code_commit_sha=normalized_commit,
            code_tree_sha=normalized_tree,
            artifacts=ordered,
            semantic_result_identity=semantic_result_identity,
            presentation_identity=presentation_identity,
            manifest_identity=ContentAddress.for_value(body),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> LongRangeReplayManifestV1:
        raw = _copy_mapping(value, field_name="LRD manifest")
        _require_exact_keys(raw, expected=_MANIFEST_KEYS, field_name="LRD manifest")
        if raw.get("schema") != LONG_RANGE_REPLAY_MANIFEST_SCHEMA_V1:
            raise LongRangeReplayError("unsupported LRD manifest schema")
        raw_artifacts = raw.get("artifacts")
        if not isinstance(raw_artifacts, list):
            raise LongRangeReplayError("LRD manifest artifacts must be a list")
        artifacts: list[ReplayArtifactBindingV1] = []
        for index, item in enumerate(raw_artifacts):
            if not isinstance(item, Mapping):
                raise LongRangeReplayError(f"LRD manifest artifact {index} must be an object")
            artifacts.append(
                ReplayArtifactBindingV1.from_dict(cast(Mapping[str, object], item))
            )
        return cls(
            case_id=_text(raw.get("case_id"), field_name="case_id"),
            case_replay_manifest_identity=_address(
                raw.get("case_replay_manifest_identity"),
                field_name="case_replay_manifest_identity",
            ),
            coverage_matrix_identity=_address(
                raw.get("coverage_matrix_identity"),
                field_name="coverage_matrix_identity",
            ),
            code_commit_sha=_git_sha(raw.get("code_commit_sha"), field_name="code_commit_sha"),
            code_tree_sha=_git_sha(raw.get("code_tree_sha"), field_name="code_tree_sha"),
            artifacts=tuple(artifacts),
            semantic_result_identity=_address(
                raw.get("semantic_result_identity"), field_name="semantic_result_identity"
            ),
            presentation_identity=_optional_address(
                raw.get("presentation_identity"), field_name="presentation_identity"
            ),
            manifest_identity=_address(
                raw.get("manifest_identity"), field_name="manifest_identity"
            ),
        )

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "case_replay_manifest_identity": self.case_replay_manifest_identity.canonical_dict(),
            "coverage_matrix_identity": self.coverage_matrix_identity.canonical_dict(),
            "code_commit_sha": self.code_commit_sha,
            "code_tree_sha": self.code_tree_sha,
            "artifacts": [item.canonical_dict() for item in self.artifacts],
            "semantic_result_identity": self.semantic_result_identity.canonical_dict(),
            "presentation_identity": (
                self.presentation_identity.canonical_dict()
                if self.presentation_identity is not None
                else None
            ),
        }

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "manifest_identity": self.manifest_identity.canonical_dict()}

    def verify(self) -> None:
        expected = ContentAddress.for_value(self.body_dict())
        if expected != self.manifest_identity:
            raise LongRangeReplayError("LRD manifest identity mismatch")

    @property
    def all_material_preserved(self) -> bool:
        return all(
            item.preservation is ReplayPreservationStatus.PRESERVED for item in self.artifacts
        )

    @property
    def semantic_identity(self) -> ContentAddress:
        return self.semantic_result_identity


@dataclass(frozen=True, slots=True)
class ReplayAssuranceEvidenceV1:
    """Evidence-derived assurance inputs; callers do not choose the output level."""

    exact_identity_complete: bool
    deterministic_stages_reconstructed: bool
    required_material_complete: bool
    external_execution_present: bool
    external_outputs_verified: bool
    semantic_identity_verified: bool

    @property
    def level(self) -> ReplayAssuranceLevel:
        if not self.exact_identity_complete or not self.required_material_complete:
            return ReplayAssuranceLevel.UNVERIFIABLE
        if self.external_execution_present:
            if self.external_outputs_verified:
                return ReplayAssuranceLevel.VERIFIED_EXTERNAL
            if self.semantic_identity_verified:
                return ReplayAssuranceLevel.SEMANTIC
            return ReplayAssuranceLevel.ABSTAIN
        if self.deterministic_stages_reconstructed:
            return ReplayAssuranceLevel.EXACT
        if self.semantic_identity_verified:
            return ReplayAssuranceLevel.SEMANTIC
        return ReplayAssuranceLevel.ABSTAIN


@dataclass(frozen=True, slots=True)
class ReplayCapsuleV1:
    """Immutable published replay capsule with append-only supersession lineage."""

    manifest: LongRangeReplayManifestV1
    supersedes_digest: ContentAddress | None
    capsule_identity: ContentAddress
    schema: str = REPLAY_CAPSULE_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != REPLAY_CAPSULE_SCHEMA_V1:
            raise LongRangeReplayError(f"unsupported replay capsule schema: {self.schema}")
        self.manifest.verify()
        self.verify()
        if self.supersedes_digest == self.capsule_identity:
            raise LongRangeReplayError("replay capsule cannot supersede itself")

    @classmethod
    def build(
        cls,
        *,
        manifest: LongRangeReplayManifestV1,
        supersedes_digest: ContentAddress | None = None,
    ) -> ReplayCapsuleV1:
        manifest.verify()
        body = {
            "schema": REPLAY_CAPSULE_SCHEMA_V1,
            "manifest": manifest.canonical_dict(),
            "supersedes_digest": (
                supersedes_digest.canonical_dict() if supersedes_digest is not None else None
            ),
        }
        return cls(
            manifest=manifest,
            supersedes_digest=supersedes_digest,
            capsule_identity=ContentAddress.for_value(body),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ReplayCapsuleV1:
        raw = _copy_mapping(value, field_name="replay capsule")
        _require_exact_keys(raw, expected=_CAPSULE_KEYS, field_name="replay capsule")
        if raw.get("schema") != REPLAY_CAPSULE_SCHEMA_V1:
            raise LongRangeReplayError("unsupported replay capsule schema")
        raw_manifest = raw.get("manifest")
        if not isinstance(raw_manifest, Mapping):
            raise LongRangeReplayError("replay capsule manifest must be an object")
        return cls(
            manifest=LongRangeReplayManifestV1.from_dict(
                cast(Mapping[str, object], raw_manifest)
            ),
            supersedes_digest=_optional_address(
                raw.get("supersedes_digest"), field_name="supersedes_digest"
            ),
            capsule_identity=_address(
                raw.get("capsule_identity"), field_name="capsule_identity"
            ),
        )

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "manifest": self.manifest.canonical_dict(),
            "supersedes_digest": (
                self.supersedes_digest.canonical_dict()
                if self.supersedes_digest is not None
                else None
            ),
        }

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "capsule_identity": self.capsule_identity.canonical_dict()}

    def verify(self) -> None:
        expected = ContentAddress.for_value(self.body_dict())
        if expected != self.capsule_identity:
            raise LongRangeReplayError("replay capsule identity mismatch")


def semantic_identity_equal(
    historical: LongRangeReplayManifestV1,
    current: LongRangeReplayManifestV1,
) -> bool:
    """Compare semantic identity only; renderer/presentation identity is non-semantic."""

    if historical.case_id != current.case_id:
        raise LongRangeReplayError("cannot compare semantic identity across cases")
    return historical.semantic_result_identity == current.semantic_result_identity
