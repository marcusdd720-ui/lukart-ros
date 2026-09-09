"""LRD-01D Frozen Path / Current Path deterministic replay and drift evidence.

This module composes existing immutable LRD-01B identities, LRD-01C content-addressed
escrow and Case Replay v2 offline rebuild with the current Product runtime. It is
verification-only and exposes no Canonical Case Ledger write path.
"""

from __future__ import annotations

import json
import re
import socket
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from core.artifact_escrow_v1 import (
    ArtifactEscrowManifestV1,
    EscrowLimitsV1,
    FileSystemEscrowBackendV1,
)
from core.case_ledger.contracts import ContentAddress
from core.case_replay_v2 import CaseReplayV2Error, verify_case_replay_bundle
from core.enterprise.isolation import (
    IsolatedExecutionError,
    IsolatedTask,
    IsolationPolicy,
    ProcessIsolationExecutor,
)
from core.long_range_replay_v1 import (
    LongRangeReplayManifestV1,
    ReplayArtifactBindingV1,
    ReplayArtifactRole,
    ReplayAssuranceEvidenceV1,
    ReplayAssuranceLevel,
    ReplayPreservationStatus,
)
from core.p3.contracts import canonical_json
from core.product_runtime_v1 import ProductRuntimeRunV1
from reasoning.models import ReasoningOutcome

SEMANTIC_RESULT_SCHEMA_V1 = "lukart.lrd-semantic-result.v1"
FROZEN_PATH_RESULT_SCHEMA_V1 = "lukart.lrd-frozen-path-result.v1"
CURRENT_PATH_RESULT_SCHEMA_V1 = "lukart.lrd-current-path-result.v1"
DRIFT_REPORT_SCHEMA_V1 = "lukart.lrd-drift-report.v1"
FROZEN_PATH_ENTRYPOINT_V1 = "core.long_range_drift_v1:frozen_path_worker"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SEMANTIC_KEYS = frozenset(
    {
        "schema",
        "case_id",
        "reasoning_target_id",
        "reasoning_result_digest",
        "reasoning_outcome",
        "semantic_identity",
    }
)
_FROZEN_KEYS = frozenset(
    {
        "schema",
        "case_id",
        "long_range_manifest_identity",
        "escrow_manifest_identity",
        "execution_status",
        "case_replay_bundle_identity",
        "case_replay_manifest_identity",
        "epistemic_projection_identity",
        "trust_graph_identity",
        "runtime_identity_digest",
        "semantic_result_identity",
        "presentation_identity",
        "external_execution_present",
        "external_outputs_verified",
        "assurance_level",
        "task_digest",
        "output_digest",
        "network_mode",
        "network_enforcement",
        "process_enforcement",
        "native_ffi_enforcement",
        "filesystem_enforcement",
        "kernel_sandbox",
        "result_identity",
    }
)
_CURRENT_KEYS = frozenset(
    {
        "schema",
        "case_id",
        "product_runtime_proof_identity",
        "runtime_identity_digest",
        "semantic_result",
        "presentation_identity",
        "current_path_identity",
    }
)
_DRIFT_KEYS = frozenset(
    {
        "schema",
        "case_id",
        "frozen_path_identity",
        "current_path_identity",
        "frozen_assurance_level",
        "classification",
        "semantic_equal",
        "presentation_equal",
        "historical_semantic_identity",
        "current_semantic_identity",
        "historical_presentation_identity",
        "current_presentation_identity",
        "report_identity",
    }
)


class LongRangeDriftError(ValueError):
    """Fail-closed LRD-01D contract violation."""


class FrozenExecutionStatus(StrEnum):
    VERIFIED = "VERIFIED"
    UNVERIFIABLE = "UNVERIFIABLE"


class DriftClassification(StrEnum):
    NO_DRIFT = "NO_DRIFT"
    PRESENTATION_ONLY = "PRESENTATION_ONLY"
    SEMANTIC_DRIFT = "SEMANTIC_DRIFT"
    UNVERIFIABLE = "UNVERIFIABLE"
    ABSTAIN = "ABSTAIN"


def _canonical_copy(value: Mapping[str, object], *, field_name: str) -> dict[str, object]:
    if any(not isinstance(key, str) for key in value):
        raise LongRangeDriftError(f"{field_name} keys must be strings")
    try:
        decoded: object = json.loads(canonical_json(dict(value)))
    except (TypeError, ValueError) as exc:
        raise LongRangeDriftError(f"{field_name} is not canonically serializable") from exc
    if not isinstance(decoded, dict):
        raise LongRangeDriftError(f"{field_name} must be an object")
    return cast(dict[str, object], decoded)


def _strict_keys(
    value: Mapping[str, object],
    *,
    expected: frozenset[str],
    field_name: str,
) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = ",".join(sorted(expected - actual)) or "-"
    unknown = ",".join(sorted(actual - expected)) or "-"
    raise LongRangeDriftError(
        f"{field_name} key contract violation: missing={missing}; unknown={unknown}"
    )


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LongRangeDriftError(f"{field_name} must be a nonblank string")
    if value != value.strip():
        raise LongRangeDriftError(f"{field_name} must already be canonical")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise LongRangeDriftError(f"{field_name} cannot contain control characters")
    return value


def _address(value: object, *, field_name: str) -> ContentAddress:
    if not isinstance(value, Mapping):
        raise LongRangeDriftError(f"{field_name} must be a content-address object")
    if set(value) != {"algorithm", "digest"}:
        raise LongRangeDriftError(f"{field_name} content-address fields are invalid")
    try:
        return ContentAddress.from_dict(cast(Mapping[str, object], value))
    except ValueError as exc:
        raise LongRangeDriftError(str(exc)) from exc


def _optional_address(value: object, *, field_name: str) -> ContentAddress | None:
    if value is None:
        return None
    return _address(value, field_name=field_name)


def _optional_text(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _text(value, field_name=field_name)


def _bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise LongRangeDriftError(f"{field_name} must be boolean")
    return value


def _mapping(value: object, *, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise LongRangeDriftError(f"{field_name} must be an object")
    return cast(Mapping[str, object], value)


def _role_binding(
    long_range: LongRangeReplayManifestV1,
    role: ReplayArtifactRole,
) -> ReplayArtifactBindingV1:
    return next(item for item in long_range.artifacts if item.role is role)


@dataclass(frozen=True, slots=True)
class CanonicalSemanticResultV1:
    """Canonical semantic comparison artifact independent from renderer bytes."""

    case_id: str
    reasoning_target_id: str
    reasoning_result_digest: str
    reasoning_outcome: ReasoningOutcome
    semantic_identity: ContentAddress
    schema: str = SEMANTIC_RESULT_SCHEMA_V1

    @classmethod
    def build(
        cls,
        *,
        case_id: str,
        reasoning_target_id: str,
        reasoning_result_digest: str,
        reasoning_outcome: ReasoningOutcome,
    ) -> CanonicalSemanticResultV1:
        normalized_case = _text(case_id, field_name="case_id")
        normalized_target = _text(reasoning_target_id, field_name="reasoning_target_id")
        if _SHA256_RE.fullmatch(reasoning_result_digest) is None:
            raise LongRangeDriftError("reasoning_result_digest must be lowercase sha256")
        body = {
            "schema": SEMANTIC_RESULT_SCHEMA_V1,
            "case_id": normalized_case,
            "reasoning_target_id": normalized_target,
            "reasoning_result_digest": reasoning_result_digest,
            "reasoning_outcome": reasoning_outcome.value,
        }
        return cls(
            case_id=normalized_case,
            reasoning_target_id=normalized_target,
            reasoning_result_digest=reasoning_result_digest,
            reasoning_outcome=reasoning_outcome,
            semantic_identity=ContentAddress.for_value(body),
        )

    @classmethod
    def from_product_run(cls, run: ProductRuntimeRunV1) -> CanonicalSemanticResultV1:
        run.verify()
        return cls.build(
            case_id=run.proof.case_id.value,
            reasoning_target_id=run.proof.reasoning_target_id,
            reasoning_result_digest=run.reasoning_result.digest(),
            reasoning_outcome=run.reasoning_result.decision.outcome,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> CanonicalSemanticResultV1:
        raw = _canonical_copy(value, field_name="semantic result")
        _strict_keys(raw, expected=_SEMANTIC_KEYS, field_name="semantic result")
        if raw.get("schema") != SEMANTIC_RESULT_SCHEMA_V1:
            raise LongRangeDriftError("unsupported semantic result schema")
        try:
            outcome = ReasoningOutcome(
                _text(raw.get("reasoning_outcome"), field_name="reasoning_outcome")
            )
        except ValueError as exc:
            raise LongRangeDriftError("unknown reasoning outcome") from exc
        return cls(
            case_id=_text(raw.get("case_id"), field_name="case_id"),
            reasoning_target_id=_text(
                raw.get("reasoning_target_id"),
                field_name="reasoning_target_id",
            ),
            reasoning_result_digest=_text(
                raw.get("reasoning_result_digest"),
                field_name="reasoning_result_digest",
            ),
            reasoning_outcome=outcome,
            semantic_identity=_address(
                raw.get("semantic_identity"),
                field_name="semantic_identity",
            ),
        )

    def __post_init__(self) -> None:
        _text(self.case_id, field_name="case_id")
        _text(self.reasoning_target_id, field_name="reasoning_target_id")
        if _SHA256_RE.fullmatch(self.reasoning_result_digest) is None:
            raise LongRangeDriftError("reasoning_result_digest must be lowercase sha256")
        if ContentAddress.for_value(self.body_dict()) != self.semantic_identity:
            raise LongRangeDriftError("semantic result identity mismatch")

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "reasoning_target_id": self.reasoning_target_id,
            "reasoning_result_digest": self.reasoning_result_digest,
            "reasoning_outcome": self.reasoning_outcome.value,
        }

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.body_dict(),
            "semantic_identity": self.semantic_identity.canonical_dict(),
        }


@dataclass(frozen=True, slots=True)
class FrozenPathResultV1:
    """Immutable evidence that historical deterministic replay was rebuilt offline."""

    case_id: str
    long_range_manifest_identity: ContentAddress
    escrow_manifest_identity: ContentAddress
    execution_status: FrozenExecutionStatus
    case_replay_bundle_identity: ContentAddress | None
    case_replay_manifest_identity: ContentAddress | None
    epistemic_projection_identity: ContentAddress | None
    trust_graph_identity: ContentAddress | None
    runtime_identity_digest: ContentAddress | None
    semantic_result_identity: ContentAddress | None
    presentation_identity: ContentAddress | None
    external_execution_present: bool
    external_outputs_verified: bool
    assurance_level: ReplayAssuranceLevel
    task_digest: str | None
    output_digest: str | None
    network_mode: str
    network_enforcement: str
    process_enforcement: str
    native_ffi_enforcement: str
    filesystem_enforcement: str
    kernel_sandbox: bool
    result_identity: ContentAddress
    schema: str = FROZEN_PATH_RESULT_SCHEMA_V1

    @classmethod
    def build(
        cls,
        *,
        case_id: str,
        long_range_manifest_identity: ContentAddress,
        escrow_manifest_identity: ContentAddress,
        execution_status: FrozenExecutionStatus,
        case_replay_bundle_identity: ContentAddress | None,
        case_replay_manifest_identity: ContentAddress | None,
        epistemic_projection_identity: ContentAddress | None,
        trust_graph_identity: ContentAddress | None,
        runtime_identity_digest: ContentAddress | None,
        semantic_result_identity: ContentAddress | None,
        presentation_identity: ContentAddress | None,
        external_execution_present: bool,
        external_outputs_verified: bool,
        assurance_level: ReplayAssuranceLevel,
        task_digest: str | None,
        output_digest: str | None,
        network_mode: str,
        network_enforcement: str,
        process_enforcement: str,
        native_ffi_enforcement: str,
        filesystem_enforcement: str,
        kernel_sandbox: bool,
    ) -> FrozenPathResultV1:
        normalized_case = _text(case_id, field_name="case_id")
        body = {
            "schema": FROZEN_PATH_RESULT_SCHEMA_V1,
            "case_id": normalized_case,
            "long_range_manifest_identity": long_range_manifest_identity.canonical_dict(),
            "escrow_manifest_identity": escrow_manifest_identity.canonical_dict(),
            "execution_status": execution_status.value,
            "case_replay_bundle_identity": (
                case_replay_bundle_identity.canonical_dict()
                if case_replay_bundle_identity is not None
                else None
            ),
            "case_replay_manifest_identity": (
                case_replay_manifest_identity.canonical_dict()
                if case_replay_manifest_identity is not None
                else None
            ),
            "epistemic_projection_identity": (
                epistemic_projection_identity.canonical_dict()
                if epistemic_projection_identity is not None
                else None
            ),
            "trust_graph_identity": (
                trust_graph_identity.canonical_dict()
                if trust_graph_identity is not None
                else None
            ),
            "runtime_identity_digest": (
                runtime_identity_digest.canonical_dict()
                if runtime_identity_digest is not None
                else None
            ),
            "semantic_result_identity": (
                semantic_result_identity.canonical_dict()
                if semantic_result_identity is not None
                else None
            ),
            "presentation_identity": (
                presentation_identity.canonical_dict()
                if presentation_identity is not None
                else None
            ),
            "external_execution_present": external_execution_present,
            "external_outputs_verified": external_outputs_verified,
            "assurance_level": assurance_level.value,
            "task_digest": task_digest,
            "output_digest": output_digest,
            "network_mode": network_mode,
            "network_enforcement": network_enforcement,
            "process_enforcement": process_enforcement,
            "native_ffi_enforcement": native_ffi_enforcement,
            "filesystem_enforcement": filesystem_enforcement,
            "kernel_sandbox": kernel_sandbox,
        }
        return cls(
            case_id=normalized_case,
            long_range_manifest_identity=long_range_manifest_identity,
            escrow_manifest_identity=escrow_manifest_identity,
            execution_status=execution_status,
            case_replay_bundle_identity=case_replay_bundle_identity,
            case_replay_manifest_identity=case_replay_manifest_identity,
            epistemic_projection_identity=epistemic_projection_identity,
            trust_graph_identity=trust_graph_identity,
            runtime_identity_digest=runtime_identity_digest,
            semantic_result_identity=semantic_result_identity,
            presentation_identity=presentation_identity,
            external_execution_present=external_execution_present,
            external_outputs_verified=external_outputs_verified,
            assurance_level=assurance_level,
            task_digest=task_digest,
            output_digest=output_digest,
            network_mode=network_mode,
            network_enforcement=network_enforcement,
            process_enforcement=process_enforcement,
            native_ffi_enforcement=native_ffi_enforcement,
            filesystem_enforcement=filesystem_enforcement,
            kernel_sandbox=kernel_sandbox,
            result_identity=ContentAddress.for_value(body),
        )

    def __post_init__(self) -> None:
        if self.schema != FROZEN_PATH_RESULT_SCHEMA_V1:
            raise LongRangeDriftError("unsupported Frozen Path result schema")
        if self.kernel_sandbox:
            raise LongRangeDriftError(
                "LRD-01D cannot claim a kernel sandbox not provided by the executor"
            )
        exact_fields = (
            self.case_replay_bundle_identity,
            self.case_replay_manifest_identity,
            self.epistemic_projection_identity,
            self.trust_graph_identity,
            self.runtime_identity_digest,
            self.semantic_result_identity,
        )
        if self.execution_status is FrozenExecutionStatus.VERIFIED:
            if any(item is None for item in exact_fields):
                raise LongRangeDriftError(
                    "verified Frozen Path requires complete rebuilt identities"
                )
            if self.network_mode != "OFF":
                raise LongRangeDriftError("verified Frozen Path must declare network OFF")
            if self.network_enforcement != "python-runtime-guard":
                raise LongRangeDriftError("Frozen Path network enforcement was not observed")
            if self.process_enforcement != "python-audit-hook-deny":
                raise LongRangeDriftError("Frozen Path must deny process spawn")
            if self.native_ffi_enforcement != "python-audit-hook-deny":
                raise LongRangeDriftError("Frozen Path must deny native FFI")
            if not self.filesystem_enforcement.startswith("python-audit-hook-read-roots"):
                raise LongRangeDriftError("Frozen Path filesystem boundary was not observed")
            if self.task_digest is None or self.output_digest is None:
                raise LongRangeDriftError("verified Frozen Path requires task/output digests")
        else:
            if any(item is not None for item in exact_fields):
                raise LongRangeDriftError(
                    "unverifiable Frozen Path cannot contain fabricated rebuilt identities"
                )
            if self.assurance_level is not ReplayAssuranceLevel.UNVERIFIABLE:
                raise LongRangeDriftError(
                    "unexecuted missing-material Frozen Path must be UNVERIFIABLE"
                )
        if self.external_outputs_verified and not self.external_execution_present:
            raise LongRangeDriftError(
                "external outputs cannot be verified when no external execution existed"
            )
        if ContentAddress.for_value(self.body_dict()) != self.result_identity:
            raise LongRangeDriftError("Frozen Path result identity mismatch")

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> FrozenPathResultV1:
        raw = _canonical_copy(value, field_name="Frozen Path result")
        _strict_keys(raw, expected=_FROZEN_KEYS, field_name="Frozen Path result")
        if raw.get("schema") != FROZEN_PATH_RESULT_SCHEMA_V1:
            raise LongRangeDriftError("unsupported Frozen Path result schema")
        try:
            execution_status = FrozenExecutionStatus(
                _text(raw.get("execution_status"), field_name="execution_status")
            )
            assurance = ReplayAssuranceLevel(
                _text(raw.get("assurance_level"), field_name="assurance_level")
            )
        except ValueError as exc:
            raise LongRangeDriftError("unknown Frozen Path enum value") from exc
        return cls(
            case_id=_text(raw.get("case_id"), field_name="case_id"),
            long_range_manifest_identity=_address(
                raw.get("long_range_manifest_identity"),
                field_name="long_range_manifest_identity",
            ),
            escrow_manifest_identity=_address(
                raw.get("escrow_manifest_identity"),
                field_name="escrow_manifest_identity",
            ),
            execution_status=execution_status,
            case_replay_bundle_identity=_optional_address(
                raw.get("case_replay_bundle_identity"),
                field_name="case_replay_bundle_identity",
            ),
            case_replay_manifest_identity=_optional_address(
                raw.get("case_replay_manifest_identity"),
                field_name="case_replay_manifest_identity",
            ),
            epistemic_projection_identity=_optional_address(
                raw.get("epistemic_projection_identity"),
                field_name="epistemic_projection_identity",
            ),
            trust_graph_identity=_optional_address(
                raw.get("trust_graph_identity"),
                field_name="trust_graph_identity",
            ),
            runtime_identity_digest=_optional_address(
                raw.get("runtime_identity_digest"),
                field_name="runtime_identity_digest",
            ),
            semantic_result_identity=_optional_address(
                raw.get("semantic_result_identity"),
                field_name="semantic_result_identity",
            ),
            presentation_identity=_optional_address(
                raw.get("presentation_identity"),
                field_name="presentation_identity",
            ),
            external_execution_present=_bool(
                raw.get("external_execution_present"),
                field_name="external_execution_present",
            ),
            external_outputs_verified=_bool(
                raw.get("external_outputs_verified"),
                field_name="external_outputs_verified",
            ),
            assurance_level=assurance,
            task_digest=_optional_text(raw.get("task_digest"), field_name="task_digest"),
            output_digest=_optional_text(raw.get("output_digest"), field_name="output_digest"),
            network_mode=_text(raw.get("network_mode"), field_name="network_mode"),
            network_enforcement=_text(
                raw.get("network_enforcement"),
                field_name="network_enforcement",
            ),
            process_enforcement=_text(
                raw.get("process_enforcement"),
                field_name="process_enforcement",
            ),
            native_ffi_enforcement=_text(
                raw.get("native_ffi_enforcement"),
                field_name="native_ffi_enforcement",
            ),
            filesystem_enforcement=_text(
                raw.get("filesystem_enforcement"),
                field_name="filesystem_enforcement",
            ),
            kernel_sandbox=_bool(raw.get("kernel_sandbox"), field_name="kernel_sandbox"),
            result_identity=_address(raw.get("result_identity"), field_name="result_identity"),
        )

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "long_range_manifest_identity": self.long_range_manifest_identity.canonical_dict(),
            "escrow_manifest_identity": self.escrow_manifest_identity.canonical_dict(),
            "execution_status": self.execution_status.value,
            "case_replay_bundle_identity": (
                self.case_replay_bundle_identity.canonical_dict()
                if self.case_replay_bundle_identity is not None
                else None
            ),
            "case_replay_manifest_identity": (
                self.case_replay_manifest_identity.canonical_dict()
                if self.case_replay_manifest_identity is not None
                else None
            ),
            "epistemic_projection_identity": (
                self.epistemic_projection_identity.canonical_dict()
                if self.epistemic_projection_identity is not None
                else None
            ),
            "trust_graph_identity": (
                self.trust_graph_identity.canonical_dict()
                if self.trust_graph_identity is not None
                else None
            ),
            "runtime_identity_digest": (
                self.runtime_identity_digest.canonical_dict()
                if self.runtime_identity_digest is not None
                else None
            ),
            "semantic_result_identity": (
                self.semantic_result_identity.canonical_dict()
                if self.semantic_result_identity is not None
                else None
            ),
            "presentation_identity": (
                self.presentation_identity.canonical_dict()
                if self.presentation_identity is not None
                else None
            ),
            "external_execution_present": self.external_execution_present,
            "external_outputs_verified": self.external_outputs_verified,
            "assurance_level": self.assurance_level.value,
            "task_digest": self.task_digest,
            "output_digest": self.output_digest,
            "network_mode": self.network_mode,
            "network_enforcement": self.network_enforcement,
            "process_enforcement": self.process_enforcement,
            "native_ffi_enforcement": self.native_ffi_enforcement,
            "filesystem_enforcement": self.filesystem_enforcement,
            "kernel_sandbox": self.kernel_sandbox,
        }

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "result_identity": self.result_identity.canonical_dict()}


@dataclass(frozen=True, slots=True)
class CurrentPathResultV1:
    """New identity produced by executing the current supported Product runtime."""

    case_id: str
    product_runtime_proof_identity: ContentAddress
    runtime_identity_digest: ContentAddress
    semantic_result: CanonicalSemanticResultV1
    presentation_identity: ContentAddress | None
    current_path_identity: ContentAddress
    schema: str = CURRENT_PATH_RESULT_SCHEMA_V1

    @classmethod
    def build(
        cls,
        *,
        run: ProductRuntimeRunV1,
        presentation_identity: ContentAddress | None = None,
    ) -> CurrentPathResultV1:
        run.verify()
        semantic = CanonicalSemanticResultV1.from_product_run(run)
        body = {
            "schema": CURRENT_PATH_RESULT_SCHEMA_V1,
            "case_id": run.proof.case_id.value,
            "product_runtime_proof_identity": run.proof.proof_identity.canonical_dict(),
            "runtime_identity_digest": run.proof.runtime_identity_digest.canonical_dict(),
            "semantic_result": semantic.canonical_dict(),
            "presentation_identity": (
                presentation_identity.canonical_dict()
                if presentation_identity is not None
                else None
            ),
        }
        return cls(
            case_id=run.proof.case_id.value,
            product_runtime_proof_identity=run.proof.proof_identity,
            runtime_identity_digest=run.proof.runtime_identity_digest,
            semantic_result=semantic,
            presentation_identity=presentation_identity,
            current_path_identity=ContentAddress.for_value(body),
        )

    def __post_init__(self) -> None:
        if self.schema != CURRENT_PATH_RESULT_SCHEMA_V1:
            raise LongRangeDriftError("unsupported Current Path result schema")
        if self.semantic_result.case_id != self.case_id:
            raise LongRangeDriftError("Current Path semantic result belongs to another case")
        if ContentAddress.for_value(self.body_dict()) != self.current_path_identity:
            raise LongRangeDriftError("Current Path result identity mismatch")

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> CurrentPathResultV1:
        raw = _canonical_copy(value, field_name="Current Path result")
        _strict_keys(raw, expected=_CURRENT_KEYS, field_name="Current Path result")
        if raw.get("schema") != CURRENT_PATH_RESULT_SCHEMA_V1:
            raise LongRangeDriftError("unsupported Current Path result schema")
        semantic_raw = _mapping(raw.get("semantic_result"), field_name="semantic_result")
        return cls(
            case_id=_text(raw.get("case_id"), field_name="case_id"),
            product_runtime_proof_identity=_address(
                raw.get("product_runtime_proof_identity"),
                field_name="product_runtime_proof_identity",
            ),
            runtime_identity_digest=_address(
                raw.get("runtime_identity_digest"),
                field_name="runtime_identity_digest",
            ),
            semantic_result=CanonicalSemanticResultV1.from_dict(semantic_raw),
            presentation_identity=_optional_address(
                raw.get("presentation_identity"),
                field_name="presentation_identity",
            ),
            current_path_identity=_address(
                raw.get("current_path_identity"),
                field_name="current_path_identity",
            ),
        )

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "product_runtime_proof_identity": self.product_runtime_proof_identity.canonical_dict(),
            "runtime_identity_digest": self.runtime_identity_digest.canonical_dict(),
            "semantic_result": self.semantic_result.canonical_dict(),
            "presentation_identity": (
                self.presentation_identity.canonical_dict()
                if self.presentation_identity is not None
                else None
            ),
        }

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.body_dict(),
            "current_path_identity": self.current_path_identity.canonical_dict(),
        }


@dataclass(frozen=True, slots=True)
class DriftReportV1:
    """Content-addressed classification of semantic versus presentation drift."""

    case_id: str
    frozen_path_identity: ContentAddress
    current_path_identity: ContentAddress
    frozen_assurance_level: ReplayAssuranceLevel
    classification: DriftClassification
    semantic_equal: bool | None
    presentation_equal: bool | None
    historical_semantic_identity: ContentAddress | None
    current_semantic_identity: ContentAddress
    historical_presentation_identity: ContentAddress | None
    current_presentation_identity: ContentAddress | None
    report_identity: ContentAddress
    schema: str = DRIFT_REPORT_SCHEMA_V1

    @classmethod
    def build(
        cls,
        *,
        frozen: FrozenPathResultV1,
        current: CurrentPathResultV1,
    ) -> DriftReportV1:
        if frozen.case_id != current.case_id:
            raise LongRangeDriftError("Frozen/Current Path comparison across cases is forbidden")

        if frozen.assurance_level is ReplayAssuranceLevel.UNVERIFIABLE:
            classification = DriftClassification.UNVERIFIABLE
            semantic_equal: bool | None = None
            presentation_equal: bool | None = None
        elif frozen.assurance_level is ReplayAssuranceLevel.ABSTAIN:
            classification = DriftClassification.ABSTAIN
            semantic_equal = None
            presentation_equal = None
        else:
            if frozen.semantic_result_identity is None:
                raise LongRangeDriftError("verifiable Frozen Path lacks semantic identity")
            semantic_equal = (
                frozen.semantic_result_identity
                == current.semantic_result.semantic_identity
            )
            presentation_equal = frozen.presentation_identity == current.presentation_identity
            if not semantic_equal:
                classification = DriftClassification.SEMANTIC_DRIFT
            elif not presentation_equal:
                classification = DriftClassification.PRESENTATION_ONLY
            else:
                classification = DriftClassification.NO_DRIFT

        body = {
            "schema": DRIFT_REPORT_SCHEMA_V1,
            "case_id": frozen.case_id,
            "frozen_path_identity": frozen.result_identity.canonical_dict(),
            "current_path_identity": current.current_path_identity.canonical_dict(),
            "frozen_assurance_level": frozen.assurance_level.value,
            "classification": classification.value,
            "semantic_equal": semantic_equal,
            "presentation_equal": presentation_equal,
            "historical_semantic_identity": (
                frozen.semantic_result_identity.canonical_dict()
                if frozen.semantic_result_identity is not None
                else None
            ),
            "current_semantic_identity": current.semantic_result.semantic_identity.canonical_dict(),
            "historical_presentation_identity": (
                frozen.presentation_identity.canonical_dict()
                if frozen.presentation_identity is not None
                else None
            ),
            "current_presentation_identity": (
                current.presentation_identity.canonical_dict()
                if current.presentation_identity is not None
                else None
            ),
        }
        return cls(
            case_id=frozen.case_id,
            frozen_path_identity=frozen.result_identity,
            current_path_identity=current.current_path_identity,
            frozen_assurance_level=frozen.assurance_level,
            classification=classification,
            semantic_equal=semantic_equal,
            presentation_equal=presentation_equal,
            historical_semantic_identity=frozen.semantic_result_identity,
            current_semantic_identity=current.semantic_result.semantic_identity,
            historical_presentation_identity=frozen.presentation_identity,
            current_presentation_identity=current.presentation_identity,
            report_identity=ContentAddress.for_value(body),
        )

    def __post_init__(self) -> None:
        if self.schema != DRIFT_REPORT_SCHEMA_V1:
            raise LongRangeDriftError("unsupported drift report schema")
        if self.classification in {
            DriftClassification.UNVERIFIABLE,
            DriftClassification.ABSTAIN,
        }:
            if self.semantic_equal is not None or self.presentation_equal is not None:
                raise LongRangeDriftError("unknown drift cannot contain fabricated equality")
        else:
            if self.semantic_equal is None or self.presentation_equal is None:
                raise LongRangeDriftError(
                    "verified drift classification requires equality evidence"
                )
        if ContentAddress.for_value(self.body_dict()) != self.report_identity:
            raise LongRangeDriftError("drift report identity mismatch")

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> DriftReportV1:
        raw = _canonical_copy(value, field_name="drift report")
        _strict_keys(raw, expected=_DRIFT_KEYS, field_name="drift report")
        if raw.get("schema") != DRIFT_REPORT_SCHEMA_V1:
            raise LongRangeDriftError("unsupported drift report schema")
        try:
            assurance = ReplayAssuranceLevel(
                _text(raw.get("frozen_assurance_level"), field_name="frozen_assurance_level")
            )
            classification = DriftClassification(
                _text(raw.get("classification"), field_name="classification")
            )
        except ValueError as exc:
            raise LongRangeDriftError("unknown drift report enum value") from exc
        semantic_equal = raw.get("semantic_equal")
        presentation_equal = raw.get("presentation_equal")
        if semantic_equal is not None and not isinstance(semantic_equal, bool):
            raise LongRangeDriftError("semantic_equal must be boolean or null")
        if presentation_equal is not None and not isinstance(presentation_equal, bool):
            raise LongRangeDriftError("presentation_equal must be boolean or null")
        return cls(
            case_id=_text(raw.get("case_id"), field_name="case_id"),
            frozen_path_identity=_address(
                raw.get("frozen_path_identity"),
                field_name="frozen_path_identity",
            ),
            current_path_identity=_address(
                raw.get("current_path_identity"),
                field_name="current_path_identity",
            ),
            frozen_assurance_level=assurance,
            classification=classification,
            semantic_equal=cast(bool | None, semantic_equal),
            presentation_equal=cast(bool | None, presentation_equal),
            historical_semantic_identity=_optional_address(
                raw.get("historical_semantic_identity"),
                field_name="historical_semantic_identity",
            ),
            current_semantic_identity=_address(
                raw.get("current_semantic_identity"),
                field_name="current_semantic_identity",
            ),
            historical_presentation_identity=_optional_address(
                raw.get("historical_presentation_identity"),
                field_name="historical_presentation_identity",
            ),
            current_presentation_identity=_optional_address(
                raw.get("current_presentation_identity"),
                field_name="current_presentation_identity",
            ),
            report_identity=_address(raw.get("report_identity"), field_name="report_identity"),
        )

    def body_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id,
            "frozen_path_identity": self.frozen_path_identity.canonical_dict(),
            "current_path_identity": self.current_path_identity.canonical_dict(),
            "frozen_assurance_level": self.frozen_assurance_level.value,
            "classification": self.classification.value,
            "semantic_equal": self.semantic_equal,
            "presentation_equal": self.presentation_equal,
            "historical_semantic_identity": (
                self.historical_semantic_identity.canonical_dict()
                if self.historical_semantic_identity is not None
                else None
            ),
            "current_semantic_identity": self.current_semantic_identity.canonical_dict(),
            "historical_presentation_identity": (
                self.historical_presentation_identity.canonical_dict()
                if self.historical_presentation_identity is not None
                else None
            ),
            "current_presentation_identity": (
                self.current_presentation_identity.canonical_dict()
                if self.current_presentation_identity is not None
                else None
            ),
        }

    def canonical_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "report_identity": self.report_identity.canonical_dict()}


def frozen_path_worker(payload: Mapping[str, object]) -> dict[str, object]:
    """Fixed allow-listed worker: rebuild Case Replay v2 and semantic evidence offline."""

    expected_case_id = _text(payload.get("expected_case_id"), field_name="expected_case_id")
    escrow_root = _text(payload.get("escrow_root"), field_name="escrow_root")
    limits = EscrowLimitsV1.from_dict(_mapping(payload.get("limits"), field_name="limits"))
    long_range = LongRangeReplayManifestV1.from_dict(
        _mapping(payload.get("long_range_manifest"), field_name="long_range_manifest")
    )
    escrow = ArtifactEscrowManifestV1.from_dict(
        _mapping(payload.get("escrow_manifest"), field_name="escrow_manifest")
    )
    if long_range.case_id != expected_case_id or escrow.case_id != expected_case_id:
        raise LongRangeDriftError("Frozen Path tenant/case scope mismatch")
    escrow.verify_against(long_range)

    try:
        socket.getaddrinfo("frozen-path-network-probe.invalid", 443)
    except PermissionError:
        network_probe = "DENIED"
    else:
        raise LongRangeDriftError("Frozen Path network guard is not active")

    by_role = {binding.role: binding for binding in escrow.bindings}
    case_binding = by_role.get(ReplayArtifactRole.CASE_REPLAY_BUNDLE)
    semantic_binding = by_role.get(ReplayArtifactRole.SEMANTIC_RESULT)
    if case_binding is None or semantic_binding is None:
        raise LongRangeDriftError("Frozen Path essential escrow material is unavailable")

    backend = FileSystemEscrowBackendV1(escrow_root, create=False)
    case_bytes = backend.read(case_binding.blob, limits=limits)
    semantic_bytes = backend.read(semantic_binding.blob, limits=limits)

    try:
        case_raw: object = json.loads(case_bytes.decode("utf-8"))
        semantic_raw: object = json.loads(semantic_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LongRangeDriftError("Frozen Path artifact is not canonical JSON") from exc
    case_mapping = _mapping(case_raw, field_name="case replay bundle bytes")
    semantic_mapping = _mapping(semantic_raw, field_name="semantic result bytes")
    if case_bytes != canonical_json(dict(case_mapping)).encode("utf-8"):
        raise LongRangeDriftError("Case Replay bundle bytes are not canonical JSON")
    if semantic_bytes != canonical_json(dict(semantic_mapping)).encode("utf-8"):
        raise LongRangeDriftError("semantic result bytes are not canonical JSON")

    try:
        replay = verify_case_replay_bundle(case_mapping)
    except (CaseReplayV2Error, ValueError) as exc:
        raise LongRangeDriftError(f"Frozen Case Replay rebuild failed: {exc}") from exc
    semantic = CanonicalSemanticResultV1.from_dict(semantic_mapping)

    bundle_identity = _address(
        case_mapping.get("bundle_identity"),
        field_name="case replay bundle identity",
    )
    if bundle_identity != case_binding.logical_identity:
        raise LongRangeDriftError("Frozen Case Replay bundle identity does not match LRD binding")
    if replay.manifest_identity != long_range.case_replay_manifest_identity:
        raise LongRangeDriftError(
            "Frozen Case Replay manifest identity does not match LRD manifest"
        )
    if semantic.case_id != expected_case_id:
        raise LongRangeDriftError("Frozen semantic result belongs to another case")
    if semantic.semantic_identity != long_range.semantic_result_identity:
        raise LongRangeDriftError("Frozen semantic result identity does not match LRD manifest")
    if semantic.semantic_identity != semantic_binding.logical_identity:
        raise LongRangeDriftError("Frozen semantic result does not match escrow logical identity")

    runtime_raw = _mapping(case_mapping.get("runtime_identity"), field_name="runtime_identity")
    providers = runtime_raw.get("provider_identities")
    if not isinstance(providers, list) or any(not isinstance(item, str) for item in providers):
        raise LongRangeDriftError("verified runtime provider inventory is malformed")
    external_execution_present = bool(providers)
    request_status = _role_binding(
        long_range,
        ReplayArtifactRole.PROVIDER_REQUESTS,
    ).preservation
    response_status = _role_binding(
        long_range,
        ReplayArtifactRole.PROVIDER_RESPONSES,
    ).preservation
    external_outputs_verified = (
        external_execution_present
        and request_status is ReplayPreservationStatus.PRESERVED
        and response_status is ReplayPreservationStatus.PRESERVED
        and ReplayArtifactRole.PROVIDER_REQUESTS in by_role
        and ReplayArtifactRole.PROVIDER_RESPONSES in by_role
    )

    return {
        "result": "PASS",
        "case_id": expected_case_id,
        "network_probe": network_probe,
        "case_replay_bundle_identity": bundle_identity.canonical_dict(),
        "case_replay_manifest_identity": replay.manifest_identity.canonical_dict(),
        "epistemic_projection_identity": replay.epistemic_projection_identity.canonical_dict(),
        "trust_graph_identity": replay.trust_graph_identity.canonical_dict(),
        "runtime_identity_digest": replay.runtime_identity_digest.canonical_dict(),
        "semantic_result_identity": semantic.semantic_identity.canonical_dict(),
        "external_execution_present": external_execution_present,
        "external_outputs_verified": external_outputs_verified,
    }


class FrozenPathRunnerV1:
    """Least-privilege offline Frozen Path over verified escrow bytes."""

    def __init__(self, *, limits: EscrowLimitsV1 | None = None) -> None:
        self.limits = limits or EscrowLimitsV1()

    def verify(
        self,
        *,
        expected_case_id: str,
        long_range_manifest: LongRangeReplayManifestV1,
        escrow_manifest: ArtifactEscrowManifestV1,
        escrow_root: str | Path,
    ) -> FrozenPathResultV1:
        normalized_case = _text(expected_case_id, field_name="expected_case_id")
        long_range_manifest.verify()
        escrow_manifest.verify_against(long_range_manifest)
        if long_range_manifest.case_id != normalized_case:
            raise LongRangeDriftError("Frozen Path tenant/case scope mismatch")

        essential = (
            _role_binding(
                long_range_manifest,
                ReplayArtifactRole.CASE_REPLAY_BUNDLE,
            ).preservation,
            _role_binding(
                long_range_manifest,
                ReplayArtifactRole.SEMANTIC_RESULT,
            ).preservation,
        )
        if any(status is not ReplayPreservationStatus.PRESERVED for status in essential):
            return FrozenPathResultV1.build(
                case_id=normalized_case,
                long_range_manifest_identity=long_range_manifest.manifest_identity,
                escrow_manifest_identity=escrow_manifest.escrow_manifest_identity,
                execution_status=FrozenExecutionStatus.UNVERIFIABLE,
                case_replay_bundle_identity=None,
                case_replay_manifest_identity=None,
                epistemic_projection_identity=None,
                trust_graph_identity=None,
                runtime_identity_digest=None,
                semantic_result_identity=None,
                presentation_identity=None,
                external_execution_present=False,
                external_outputs_verified=False,
                assurance_level=ReplayAssuranceLevel.UNVERIFIABLE,
                task_digest=None,
                output_digest=None,
                network_mode="OFF",
                network_enforcement="NOT_EXECUTED",
                process_enforcement="NOT_EXECUTED",
                native_ffi_enforcement="NOT_EXECUTED",
                filesystem_enforcement="NOT_EXECUTED",
                kernel_sandbox=False,
            )

        root = Path(escrow_root).expanduser().resolve(strict=False)
        if not root.is_dir():
            raise LongRangeDriftError("Frozen Path escrow root must be a directory")

        policy = IsolationPolicy(
            timeout_seconds=self.limits.runner_timeout_seconds,
            memory_bytes=self.limits.runner_memory_bytes,
            cpu_seconds=self.limits.runner_cpu_seconds,
            network_allowed=False,
            allowed_entrypoints=(FROZEN_PATH_ENTRYPOINT_V1,),
            allowed_read_roots=(str(root),),
            process_spawn_allowed=False,
            native_ffi_allowed=False,
            workspace_write_only=True,
        )
        task = IsolatedTask(
            module="core.long_range_drift_v1",
            function="frozen_path_worker",
            payload={
                "expected_case_id": normalized_case,
                "escrow_root": str(root),
                "limits": self.limits.canonical_dict(),
                "long_range_manifest": long_range_manifest.canonical_dict(),
                "escrow_manifest": escrow_manifest.canonical_dict(),
            },
        )
        try:
            isolated = ProcessIsolationExecutor(policy).run(task)
        except IsolatedExecutionError as exc:
            raise LongRangeDriftError(f"Frozen Path failed: {exc}") from exc
        output = isolated.output
        if output.get("result") != "PASS" or output.get("network_probe") != "DENIED":
            raise LongRangeDriftError("Frozen Path worker did not prove offline PASS")
        if output.get("case_id") != normalized_case:
            raise LongRangeDriftError("Frozen Path worker returned wrong case")

        rebuilt_bundle = _address(
            output.get("case_replay_bundle_identity"),
            field_name="rebuilt case replay bundle identity",
        )
        rebuilt_manifest = _address(
            output.get("case_replay_manifest_identity"),
            field_name="rebuilt case replay manifest identity",
        )
        epistemic = _address(
            output.get("epistemic_projection_identity"),
            field_name="rebuilt epistemic projection identity",
        )
        trust = _address(
            output.get("trust_graph_identity"),
            field_name="rebuilt trust graph identity",
        )
        runtime = _address(
            output.get("runtime_identity_digest"),
            field_name="rebuilt runtime identity",
        )
        semantic = _address(
            output.get("semantic_result_identity"),
            field_name="rebuilt semantic result identity",
        )
        external_present = _bool(
            output.get("external_execution_present"),
            field_name="external_execution_present",
        )
        external_verified = _bool(
            output.get("external_outputs_verified"),
            field_name="external_outputs_verified",
        )

        evidence = ReplayAssuranceEvidenceV1(
            exact_identity_complete=True,
            deterministic_stages_reconstructed=True,
            required_material_complete=long_range_manifest.all_material_preserved,
            external_execution_present=external_present,
            external_outputs_verified=external_verified,
            semantic_identity_verified=True,
        )
        return FrozenPathResultV1.build(
            case_id=normalized_case,
            long_range_manifest_identity=long_range_manifest.manifest_identity,
            escrow_manifest_identity=escrow_manifest.escrow_manifest_identity,
            execution_status=FrozenExecutionStatus.VERIFIED,
            case_replay_bundle_identity=rebuilt_bundle,
            case_replay_manifest_identity=rebuilt_manifest,
            epistemic_projection_identity=epistemic,
            trust_graph_identity=trust,
            runtime_identity_digest=runtime,
            semantic_result_identity=semantic,
            presentation_identity=long_range_manifest.presentation_identity,
            external_execution_present=external_present,
            external_outputs_verified=external_verified,
            assurance_level=evidence.level,
            task_digest=isolated.task_digest,
            output_digest=isolated.output_digest,
            network_mode="OFF",
            network_enforcement=isolated.controls.network_control,
            process_enforcement=isolated.controls.process_control,
            native_ffi_enforcement=isolated.controls.native_ffi_control,
            filesystem_enforcement=isolated.controls.filesystem_control,
            kernel_sandbox=isolated.controls.kernel_sandbox,
        )
