"""Deterministic, fail-closed replay verification for CIRP-06.

CIRP replay is a verification artifact, never a case-history truth store.  The
manifest carries only semantic artifact identities and content digests plus the
exact CIRP run-identity digest.  It intentionally contains no raw case material.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.cirp.contracts import CIRPContractError, CIRPRunIdentity, CIRP_VERSION_V1
from core.cirp.report import CIRP_REPORT_SCHEMA_V1
from core.p3.contracts import (
    P3ContractError,
    ReplayRelation,
    content_digest,
    require_hex_digest,
)

CIRP_REPLAY_MANIFEST_SCHEMA_V1 = "lukart.cirp.replay-manifest.v1"
CIRP_REPLAY_COMPARISON_SCHEMA_V1 = "lukart.cirp.replay-comparison.v1"


def _require_nonblank(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise CIRPContractError(f"{field_name} must be nonblank and already canonical")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CIRPContractError(f"{field_name} cannot contain control characters")
    return value


def _normalize_digest(value: str, *, field_name: str) -> str:
    try:
        return require_hex_digest(value, field_name=field_name)
    except P3ContractError as exc:
        raise CIRPContractError(str(exc)) from exc


def _unique(values: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    normalized = tuple(_require_nonblank(item, field_name=field_name) for item in values)
    if len(normalized) != len(set(normalized)):
        raise CIRPContractError(f"{field_name} cannot contain duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class CIRPReplayArtifactRef:
    """Content-addressed reference to one deterministic CIRP semantic artifact."""

    artifact_id: str
    schema: str
    digest: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "artifact_id",
            _require_nonblank(self.artifact_id, field_name="artifact_id"),
        )
        object.__setattr__(
            self,
            "schema",
            _require_nonblank(self.schema, field_name="artifact schema"),
        )
        object.__setattr__(
            self,
            "digest",
            _normalize_digest(self.digest, field_name="artifact digest"),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "schema": self.schema,
            "digest": self.digest,
        }


@dataclass(frozen=True, slots=True)
class CIRPReplayManifest:
    """Exact deterministic CIRP run projection used for replay verification."""

    run_identity_digest: str
    artifacts: tuple[CIRPReplayArtifactRef, ...]
    report_artifact_id: str
    cirp_version: str = CIRP_VERSION_V1
    schema: str = CIRP_REPLAY_MANIFEST_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CIRP_REPLAY_MANIFEST_SCHEMA_V1:
            raise CIRPContractError("unsupported CIRP replay manifest schema")
        if self.cirp_version != CIRP_VERSION_V1:
            raise CIRPContractError("unsupported CIRP replay manifest version")
        object.__setattr__(
            self,
            "run_identity_digest",
            _normalize_digest(self.run_identity_digest, field_name="run_identity_digest"),
        )
        object.__setattr__(
            self,
            "report_artifact_id",
            _require_nonblank(self.report_artifact_id, field_name="report_artifact_id"),
        )
        if not self.artifacts:
            raise CIRPContractError("CIRP replay manifest requires artifacts")
        artifact_ids = tuple(item.artifact_id for item in self.artifacts)
        if len(artifact_ids) != len(set(artifact_ids)):
            raise CIRPContractError("CIRP replay manifest cannot contain duplicate artifact_id values")
        ordered = tuple(sorted(self.artifacts, key=lambda item: item.artifact_id))
        object.__setattr__(self, "artifacts", ordered)
        report_refs = tuple(
            item for item in ordered if item.artifact_id == self.report_artifact_id
        )
        if len(report_refs) != 1:
            raise CIRPContractError("report_artifact_id must identify exactly one replay artifact")
        if report_refs[0].schema != CIRP_REPORT_SCHEMA_V1:
            raise CIRPContractError("report replay artifact must use lukart.cirp.report.v1")

    @classmethod
    def build(
        cls,
        *,
        run_identity: CIRPRunIdentity,
        artifacts: tuple[CIRPReplayArtifactRef, ...],
        report_artifact_id: str,
    ) -> CIRPReplayManifest:
        return cls(
            run_identity_digest=run_identity.digest(),
            artifacts=artifacts,
            report_artifact_id=report_artifact_id,
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "cirp_version": self.cirp_version,
            "run_identity_digest": self.run_identity_digest,
            "artifacts": [item.canonical_dict() for item in self.artifacts],
            "report_artifact_id": self.report_artifact_id,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class CIRPReplayComparison:
    relation: ReplayRelation
    expected_manifest_digest: str
    actual_manifest_digest: str
    run_identity_match: bool
    missing_artifact_ids: tuple[str, ...]
    unexpected_artifact_ids: tuple[str, ...]
    mismatched_artifact_ids: tuple[str, ...]
    report_identity_match: bool
    schema: str = CIRP_REPLAY_COMPARISON_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != CIRP_REPLAY_COMPARISON_SCHEMA_V1:
            raise CIRPContractError("unsupported CIRP replay comparison schema")
        for field_name in ("expected_manifest_digest", "actual_manifest_digest"):
            object.__setattr__(
                self,
                field_name,
                _normalize_digest(getattr(self, field_name), field_name=field_name),
            )
        for field_name in (
            "missing_artifact_ids",
            "unexpected_artifact_ids",
            "mismatched_artifact_ids",
        ):
            normalized = tuple(sorted(_unique(getattr(self, field_name), field_name=field_name)))
            object.__setattr__(self, field_name, normalized)
        if self.relation is ReplayRelation.IDENTICAL:
            if (
                not self.run_identity_match
                or not self.report_identity_match
                or self.missing_artifact_ids
                or self.unexpected_artifact_ids
                or self.mismatched_artifact_ids
                or self.expected_manifest_digest != self.actual_manifest_digest
            ):
                raise CIRPContractError("IDENTICAL replay comparison cannot contain differences")
        if self.relation is ReplayRelation.CROSS_VERSION_COMPARABLE:
            raise CIRPContractError(
                "CIRP v1 has no explicit cross-version replay compatibility contract"
            )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "relation": self.relation.value,
            "expected_manifest_digest": self.expected_manifest_digest,
            "actual_manifest_digest": self.actual_manifest_digest,
            "run_identity_match": self.run_identity_match,
            "missing_artifact_ids": list(self.missing_artifact_ids),
            "unexpected_artifact_ids": list(self.unexpected_artifact_ids),
            "mismatched_artifact_ids": list(self.mismatched_artifact_ids),
            "report_identity_match": self.report_identity_match,
        }

    def digest(self) -> str:
        return content_digest(self.canonical_dict())


class CIRPReplayVerifier:
    """Compare two complete replay manifests without inferring missing semantics."""

    @staticmethod
    def compare(
        expected: CIRPReplayManifest,
        actual: CIRPReplayManifest,
    ) -> CIRPReplayComparison:
        expected_map = {item.artifact_id: item for item in expected.artifacts}
        actual_map = {item.artifact_id: item for item in actual.artifacts}
        missing = tuple(sorted(set(expected_map) - set(actual_map)))
        unexpected = tuple(sorted(set(actual_map) - set(expected_map)))
        common = tuple(sorted(set(expected_map) & set(actual_map)))
        mismatched = tuple(
            artifact_id
            for artifact_id in common
            if expected_map[artifact_id] != actual_map[artifact_id]
        )
        run_identity_match = expected.run_identity_digest == actual.run_identity_digest
        report_identity_match = expected.report_artifact_id == actual.report_artifact_id
        expected_digest = expected.digest()
        actual_digest = actual.digest()

        if missing or unexpected:
            relation = ReplayRelation.INCOMPLETE
        elif (
            not run_identity_match
            or not report_identity_match
            or mismatched
            or expected_digest != actual_digest
        ):
            relation = ReplayRelation.DIFFERENT
        else:
            relation = ReplayRelation.IDENTICAL

        return CIRPReplayComparison(
            relation=relation,
            expected_manifest_digest=expected_digest,
            actual_manifest_digest=actual_digest,
            run_identity_match=run_identity_match,
            missing_artifact_ids=missing,
            unexpected_artifact_ids=unexpected,
            mismatched_artifact_ids=mismatched,
            report_identity_match=report_identity_match,
        )
