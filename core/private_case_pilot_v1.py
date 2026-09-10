"""Private local end-to-end pilot evidence for CASE-OPS-06.

The pilot composes verified CASE-OPS private evidence, an exact exported Canonical
Case Ledger bundle, Product Runtime v1, and Case Replay v2.  It never creates CCL
events and never persists private evidence or reasoning text in its receipt.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from core.case_ledger import CaseLedgerBundle, CaseLedgerContractError, LedgerEvent
from core.p3.contracts import RUNTIME_IDENTITY_V3, RuntimeIdentity, canonical_json, content_digest
from core.p3.versioning import CaseMigrationRegistry
from core.private_case_runtime_bridge_v1 import (
    EVENT_PRIVATE_EVIDENCE_REGISTERED,
    VerifiedLocalEvidenceProjectionV1,
    load_verified_projection,
)
from core.private_evidence_v1 import PrivateEvidenceStore, digest_hex, digest_object
from core.product_runtime_v1 import ProductRuntimeRunV1, converge_product_runtime_v1
from knowledge.epistemic import KnowledgeStatus
from knowledge.epistemic_assertions import EpistemicPolicyV2
from knowledge.evidence_trust_graph import TrustPolicyV1, event_node_id
from reasoning.models import ReasoningArtifact

PILOT_SCHEMA_V1 = "lukart.private-local-case-pilot.v1"
PILOT_PROFILE_V1 = "PRIVATE_LOCAL_CCL_PRODUCT_REPLAY_V1"
PILOT_INPUT_SYNTHETIC = "SYNTHETIC_TEST"
PILOT_INPUT_PRIVATE = "OPERATOR_DECLARED_PRIVATE_LOCAL_CASE"
PILOT_INPUT_CLASSES = frozenset({PILOT_INPUT_SYNTHETIC, PILOT_INPUT_PRIVATE})
PILOT_RECEIPT_SUFFIX = ".mvros-private-pilot.json"


class PrivateCasePilotError(RuntimeError):
    """Fail-closed CASE-OPS-06 pilot boundary violation."""


@dataclass(frozen=True, slots=True)
class PrivateCasePilotReceiptV1:
    schema: str
    profile: str
    input_class: str
    case_scope_digest: str
    private_projection_id: str
    private_document_count: int
    ccl_bundle_digest: str
    ccl_head_digest: str | None
    projection_registration_event_digest: str
    runtime_identity_digest: str
    product_runtime_proof_digest: str
    replay_manifest_digest: str
    replay_bundle_digest: str
    epistemic_projection_digest: str
    trust_graph_digest: str
    reasoning_result_digest: str
    reasoning_outcome: str
    result: str

    def canonical_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "profile": self.profile,
            "input_class": self.input_class,
            "case_scope_digest": self.case_scope_digest,
            "private_projection_id": self.private_projection_id,
            "private_document_count": self.private_document_count,
            "ccl_bundle_digest": self.ccl_bundle_digest,
            "ccl_head_digest": self.ccl_head_digest,
            "projection_registration_event_digest": self.projection_registration_event_digest,
            "runtime_identity_digest": self.runtime_identity_digest,
            "product_runtime_proof_digest": self.product_runtime_proof_digest,
            "replay_manifest_digest": self.replay_manifest_digest,
            "replay_bundle_digest": self.replay_bundle_digest,
            "epistemic_projection_digest": self.epistemic_projection_digest,
            "trust_graph_digest": self.trust_graph_digest,
            "reasoning_result_digest": self.reasoning_result_digest,
            "reasoning_outcome": self.reasoning_outcome,
            "result": self.result,
        }

    @property
    def receipt_id(self) -> str:
        return digest_object(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class PrivateCasePilotRunV1:
    receipt: PrivateCasePilotReceiptV1
    product_runtime: ProductRuntimeRunV1
    private_projection: VerifiedLocalEvidenceProjectionV1
    registration_event: LedgerEvent

    def verify(self) -> None:
        self.product_runtime.verify()
        self.registration_event.verify()
        if self.receipt.result != "PASS":
            raise PrivateCasePilotError("pilot receipt is not PASS")
        if self.receipt.private_projection_id != self.private_projection.projection_id:
            raise PrivateCasePilotError("pilot private projection identity mismatch")
        if self.receipt.product_runtime_proof_digest != (
            self.product_runtime.proof.proof_identity.digest
        ):
            raise PrivateCasePilotError("pilot Product runtime proof identity mismatch")


def _strict_mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise PrivateCasePilotError(f"{label} must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise PrivateCasePilotError(f"{label} keys must be strings")
    return cast(Mapping[str, object], value)


def _string_list(value: object, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise PrivateCasePilotError(f"{label} must be a string list")
    return tuple(cast(list[str], value))


def load_runtime_identity_mapping(value: Mapping[str, object]) -> RuntimeIdentity:
    """Parse the exact canonical RuntimeIdentity v3 shape and reject unknown fields."""
    expected = {
        "identity_schema",
        "code_sha",
        "schema_version",
        "config_digest",
        "corpus_digest",
        "provider_identities",
        "plugin_identities",
        "input_digests",
        "evidence_digests",
        "inventories_declared",
        "execution_environment",
    }
    if set(value) != expected:
        raise PrivateCasePilotError("runtime identity has unknown or missing fields")
    inventories = _strict_mapping(value["inventories_declared"], label="runtime inventories")
    if set(inventories) != {"providers", "plugins", "inputs", "evidence", "execution_environment"}:
        raise PrivateCasePilotError("runtime inventory declaration shape is invalid")
    environment = _strict_mapping(value["execution_environment"], label="execution environment")
    environment_fields = {
        "dependency_lock_digest",
        "python_implementation",
        "python_version",
        "platform_tag",
        "project_version",
        "build_backend",
    }
    if set(environment) != environment_fields:
        raise PrivateCasePilotError("execution environment shape is invalid")

    def require_string(mapping: Mapping[str, object], key: str) -> str:
        raw = mapping[key]
        if not isinstance(raw, str):
            raise PrivateCasePilotError(f"runtime field {key} must be text")
        return raw

    def require_bool(key: str) -> bool:
        raw = inventories[key]
        if not isinstance(raw, bool):
            raise PrivateCasePilotError(f"runtime inventory flag {key} must be boolean")
        return raw

    identity = RuntimeIdentity(
        identity_schema=require_string(value, "identity_schema"),
        code_sha=require_string(value, "code_sha"),
        schema_version=require_string(value, "schema_version"),
        config_digest=require_string(value, "config_digest"),
        corpus_digest=require_string(value, "corpus_digest"),
        provider_identities=_string_list(value["provider_identities"], label="providers"),
        plugin_identities=_string_list(value["plugin_identities"], label="plugins"),
        input_digests=_string_list(value["input_digests"], label="inputs"),
        evidence_digests=_string_list(value["evidence_digests"], label="evidence"),
        provider_inventory_declared=require_bool("providers"),
        plugin_inventory_declared=require_bool("plugins"),
        input_inventory_declared=require_bool("inputs"),
        evidence_inventory_declared=require_bool("evidence"),
        dependency_lock_digest=require_string(environment, "dependency_lock_digest"),
        python_implementation=require_string(environment, "python_implementation"),
        python_version=require_string(environment, "python_version"),
        platform_tag=require_string(environment, "platform_tag"),
        project_version=require_string(environment, "project_version"),
        build_backend=require_string(environment, "build_backend"),
        execution_environment_declared=require_bool("execution_environment"),
    )
    if identity.identity_schema != RUNTIME_IDENTITY_V3 or not identity.complete_for_replay:
        raise PrivateCasePilotError(
            "pilot requires a complete RuntimeIdentity v3 for exact replay"
        )
    return identity


def load_runtime_identity_file(path: Path) -> RuntimeIdentity:
    return load_runtime_identity_mapping(_read_json_mapping(path, label="runtime identity"))


def load_ledger_bundle_file(path: Path) -> CaseLedgerBundle:
    mapping = _read_json_mapping(path, label="CCL bundle")
    try:
        bundle = CaseLedgerBundle.from_dict(mapping)
    except CaseLedgerContractError as exc:
        raise PrivateCasePilotError("CCL bundle verification failed") from exc
    bundle.verify()
    return bundle


def _read_json_mapping(path: Path, *, label: str) -> Mapping[str, object]:
    candidate = path.expanduser()
    if candidate.is_symlink() or not candidate.is_file():
        raise PrivateCasePilotError(f"{label} must be a regular non-symlink file")
    try:
        raw = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrivateCasePilotError(f"{label} is invalid JSON") from exc
    return _strict_mapping(raw, label=label)


def _matching_registration_event(
    bundle: CaseLedgerBundle,
    projection: VerifiedLocalEvidenceProjectionV1,
) -> LedgerEvent:
    expected_payload = canonical_json(projection.ccl_payload())
    matches = tuple(
        event
        for event in bundle.events
        if event.event_type == EVENT_PRIVATE_EVIDENCE_REGISTERED
        and canonical_json(event.payload) == expected_payload
    )
    if len(matches) != 1:
        raise PrivateCasePilotError(
            "CCL bundle must contain exactly one event registering the exact private projection"
        )
    return matches[0]


def run_private_local_pilot(
    *,
    evidence_store: PrivateEvidenceStore,
    ledger_bundle: CaseLedgerBundle,
    runtime_identity: RuntimeIdentity,
    input_class: str,
) -> PrivateCasePilotRunV1:
    """Verify the real local trust chain without creating authoritative case history."""
    if input_class not in PILOT_INPUT_CLASSES:
        raise PrivateCasePilotError("unsupported pilot input class")
    if runtime_identity.identity_schema != RUNTIME_IDENTITY_V3 or not runtime_identity.complete_for_replay:
        raise PrivateCasePilotError("pilot runtime identity is incomplete for replay")

    projection = load_verified_projection(evidence_store)
    if ledger_bundle.case_id.value != projection.case_id:
        raise PrivateCasePilotError("private projection and CCL bundle case mismatch")
    projection_digest = digest_hex(projection.projection_id)
    if projection_digest not in runtime_identity.evidence_digests:
        raise PrivateCasePilotError("runtime identity does not bind private projection evidence")

    ledger_bundle.verify()
    registration = _matching_registration_event(ledger_bundle, projection)
    if registration.runtime_identity_digest.digest != runtime_identity.digest():
        raise PrivateCasePilotError(
            "projection registration event does not bind the supplied runtime identity"
        )

    registration_ref = event_node_id(registration.event_id)
    artifacts = (
        ReasoningArtifact(
            artifact_id="CASE-OPS-06-F1",
            statement="Verified private evidence projection is registered in Canonical Case Ledger.",
            status=KnowledgeStatus.FACT,
            evidence_refs=(registration_ref,),
        ),
        ReasoningArtifact(
            artifact_id="CASE-OPS-06-C1",
            statement="Private local case trust chain is ready for bounded Product runtime evaluation.",
            status=KnowledgeStatus.CONCLUSION,
            support_ids=("CASE-OPS-06-F1",),
        ),
    )
    product = converge_product_runtime_v1(
        ledger_bundle=ledger_bundle,
        runtime_identity=runtime_identity,
        migration_registry=CaseMigrationRegistry(),
        epistemic_policy=EpistemicPolicyV2.reference(),
        trust_policy=TrustPolicyV1.reference(),
        reasoning_artifacts=artifacts,
        reasoning_target_id="CASE-OPS-06-C1",
    )
    product.verify()
    proof = product.proof
    receipt = PrivateCasePilotReceiptV1(
        schema=PILOT_SCHEMA_V1,
        profile=PILOT_PROFILE_V1,
        input_class=input_class,
        case_scope_digest=projection.case_scope_digest,
        private_projection_id=projection.projection_id,
        private_document_count=len(projection.documents),
        ccl_bundle_digest=ledger_bundle.bundle_digest.digest,
        ccl_head_digest=(ledger_bundle.head_event_id.digest if ledger_bundle.head_event_id else None),
        projection_registration_event_digest=registration.event_id.digest,
        runtime_identity_digest=runtime_identity.digest(),
        product_runtime_proof_digest=proof.proof_identity.digest,
        replay_manifest_digest=proof.replay_manifest_identity.digest,
        replay_bundle_digest=proof.replay_bundle_identity.digest,
        epistemic_projection_digest=proof.epistemic_projection_identity.digest,
        trust_graph_digest=proof.trust_graph_identity.digest,
        reasoning_result_digest=proof.reasoning_result_digest,
        reasoning_outcome=proof.reasoning_outcome.value,
        result="PASS",
    )
    run = PrivateCasePilotRunV1(
        receipt=receipt,
        product_runtime=product,
        private_projection=projection,
        registration_event=registration,
    )
    run.verify()
    return run


def write_pilot_receipt(
    receipt: PrivateCasePilotReceiptV1,
    path: Path,
    *,
    repo_root: Path,
) -> Path:
    """Write one canonical digest-only pilot receipt outside the public repository."""
    root = repo_root.expanduser().resolve()
    target = Path(os.path.abspath(path.expanduser()))
    parent = target.parent
    if parent.is_symlink() or not parent.is_dir():
        raise PrivateCasePilotError("pilot receipt parent must be an existing directory")
    resolved_parent = parent.resolve()
    candidate = resolved_parent / target.name
    if candidate == root or root in candidate.parents:
        raise PrivateCasePilotError("pilot receipt must be outside the public repository")
    if candidate.exists() or candidate.is_symlink():
        raise PrivateCasePilotError("pilot receipt already exists")
    payload = canonical_json(receipt.canonical_dict()).encode("utf-8") + b"\n"
    fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        candidate.unlink(missing_ok=True)
        raise
    return candidate


def reasoning_contract_digest() -> str:
    """Expose identity of the fixed non-substantive pilot reasoning contract."""
    return content_digest(
        {
            "fact": "CASE-OPS-06-F1",
            "conclusion": "CASE-OPS-06-C1",
            "purpose": "trust-chain-readiness-only",
        }
    )
