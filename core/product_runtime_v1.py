"""PRC-01 converged Product runtime over the canonical trust chain.

This module is projection/verification-only. It composes existing CCL, Epistemic v2,
Evidence Trust Graph, Reasoning and Case Replay v2 contracts without creating another
writable authority. Canonical Case Ledger remains the sole authoritative case-history
write path.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.case_ledger import CaseId, CaseLedgerBundle, ContentAddress
from core.case_replay_v2 import CaseReplayBundleV2
from core.p3.contracts import RuntimeIdentity
from core.p3.versioning import CaseMigrationRegistry
from knowledge.epistemic_assertions import EpistemicPolicyV2, EpistemicProjectionV2
from knowledge.evidence_trust_graph import (
    EvidenceTrustGraph,
    TrustNodeKind,
    TrustPolicyV1,
)
from reasoning.engine import ReasoningEngine
from reasoning.models import ReasoningArtifact, ReasoningOutcome, ReasoningRunResult

PRODUCT_RUNTIME_PROOF_SCHEMA_V1 = "lukart.product-runtime-proof.v1"
PRODUCT_RUNTIME_ARTIFACT_TYPE = "product_runtime"
PRODUCT_RUNTIME_ARTIFACT_VERSION = 1


class ProductRuntimeV1Error(ValueError):
    """Fail-closed PRC-01 runtime convergence contract violation."""


def _require_canonical_identifier(value: str, *, field_name: str) -> str:
    if not value or value != value.strip():
        raise ProductRuntimeV1Error(f"{field_name} must be nonblank and canonical")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ProductRuntimeV1Error(f"{field_name} cannot contain control characters")
    return value


def _is_lower_sha256_hex(value: str) -> bool:
    return len(value) == 64 and all(
        "0" <= character <= "9" or "a" <= character <= "f" for character in value
    )


def _reasoning_evidence_nodes(
    result: ReasoningRunResult,
    trust_graph: EvidenceTrustGraph,
) -> tuple[str, ...]:
    nodes = {node.node_id: node for node in trust_graph.nodes}
    refs = tuple(
        sorted(
            {
                evidence_ref
                for artifact in result.artifacts
                for evidence_ref in artifact.evidence_refs
            }
        )
    )
    for evidence_ref in refs:
        node = nodes.get(evidence_ref)
        if node is None:
            raise ProductRuntimeV1Error(
                "reasoning evidence_ref does not resolve in the exact Evidence Trust Graph: "
                + evidence_ref
            )
        if node.kind not in {TrustNodeKind.EVENT, TrustNodeKind.ASSERTION}:
            raise ProductRuntimeV1Error(
                "reasoning evidence_ref must resolve to EVENT or ASSERTION trust node: "
                + evidence_ref
            )
    return refs


@dataclass(frozen=True, slots=True)
class ProductRuntimeProofV1:
    """Content-addressed binding of one exact converged Product runtime execution."""

    case_id: CaseId
    ledger_head: ContentAddress | None
    ledger_bundle_digest: ContentAddress
    epistemic_projection_identity: ContentAddress
    trust_graph_identity: ContentAddress
    replay_manifest_identity: ContentAddress
    replay_bundle_identity: ContentAddress
    runtime_identity_digest: ContentAddress
    reasoning_target_id: str
    reasoning_result_digest: str
    reasoning_outcome: ReasoningOutcome
    reasoning_evidence_node_ids: tuple[str, ...]
    proof_identity: ContentAddress
    schema: str = PRODUCT_RUNTIME_PROOF_SCHEMA_V1

    def __post_init__(self) -> None:
        if self.schema != PRODUCT_RUNTIME_PROOF_SCHEMA_V1:
            raise ProductRuntimeV1Error(f"unsupported product runtime proof schema: {self.schema}")
        object.__setattr__(
            self,
            "reasoning_target_id",
            _require_canonical_identifier(
                self.reasoning_target_id,
                field_name="reasoning_target_id",
            ),
        )
        if not _is_lower_sha256_hex(self.reasoning_result_digest):
            raise ProductRuntimeV1Error("reasoning_result_digest must be lowercase sha256 hex")
        normalized_refs = tuple(sorted(set(self.reasoning_evidence_node_ids)))
        if normalized_refs != self.reasoning_evidence_node_ids:
            raise ProductRuntimeV1Error(
                "reasoning_evidence_node_ids must be unique and sorted"
            )
        for ref in normalized_refs:
            _require_canonical_identifier(ref, field_name="reasoning_evidence_node_id")
        self.verify()

    @property
    def artifact_id(self) -> str:
        return f"case:{self.case_id.value}"

    @property
    def artifact_type(self) -> str:
        return PRODUCT_RUNTIME_ARTIFACT_TYPE

    @property
    def artifact_version(self) -> int:
        return PRODUCT_RUNTIME_ARTIFACT_VERSION

    @property
    def artifact_digest(self) -> str:
        return self.proof_identity.digest

    def canonical_body(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "case_id": self.case_id.value,
            "ledger_head": self.ledger_head.canonical_dict() if self.ledger_head else None,
            "ledger_bundle_digest": self.ledger_bundle_digest.canonical_dict(),
            "epistemic_projection_identity": self.epistemic_projection_identity.canonical_dict(),
            "trust_graph_identity": self.trust_graph_identity.canonical_dict(),
            "replay_manifest_identity": self.replay_manifest_identity.canonical_dict(),
            "replay_bundle_identity": self.replay_bundle_identity.canonical_dict(),
            "runtime_identity_digest": self.runtime_identity_digest.canonical_dict(),
            "reasoning_target_id": self.reasoning_target_id,
            "reasoning_result_digest": self.reasoning_result_digest,
            "reasoning_outcome": self.reasoning_outcome.value,
            "reasoning_evidence_node_ids": list(self.reasoning_evidence_node_ids),
            "authority": "derived-verification-only",
            "canonical_case_authority": "canonical-case-ledger",
        }

    def canonical_dict(self) -> dict[str, object]:
        return {
            **self.canonical_body(),
            "proof_identity": self.proof_identity.canonical_dict(),
        }

    def verify(self) -> None:
        if self.proof_identity != ContentAddress.for_value(self.canonical_body()):
            raise ProductRuntimeV1Error("product runtime proof content-address mismatch")


@dataclass(frozen=True, slots=True)
class ProductRuntimeRunV1:
    """In-memory converged runtime result; no Product persistence authority."""

    proof: ProductRuntimeProofV1
    epistemic_projection: EpistemicProjectionV2
    trust_graph: EvidenceTrustGraph
    reasoning_result: ReasoningRunResult
    replay_bundle: CaseReplayBundleV2

    def verify(self) -> None:
        self.proof.verify()
        self.epistemic_projection.verify()
        self.trust_graph.verify()
        replay = self.replay_bundle.verify()

        if self.proof.case_id != self.epistemic_projection.case_id:
            raise ProductRuntimeV1Error("runtime proof case does not match epistemic projection")
        if self.proof.case_id != self.trust_graph.case_id:
            raise ProductRuntimeV1Error("runtime proof case does not match trust graph")
        if self.proof.case_id != self.replay_bundle.manifest.case_id:
            raise ProductRuntimeV1Error("runtime proof case does not match Case Replay")
        if self.proof.ledger_head != replay.ledger_head:
            raise ProductRuntimeV1Error("runtime proof ledger head does not match Case Replay")
        if self.proof.ledger_bundle_digest != self.replay_bundle.ledger_bundle.bundle_digest:
            raise ProductRuntimeV1Error("runtime proof ledger bundle digest does not match replay")
        if (
            self.proof.epistemic_projection_identity
            != self.epistemic_projection.projection_identity
        ):
            raise ProductRuntimeV1Error("runtime proof epistemic identity mismatch")
        if self.proof.trust_graph_identity != self.trust_graph.graph_identity:
            raise ProductRuntimeV1Error("runtime proof trust graph identity mismatch")
        if self.proof.replay_manifest_identity != replay.manifest_identity:
            raise ProductRuntimeV1Error("runtime proof replay manifest identity mismatch")
        if self.proof.replay_bundle_identity != self.replay_bundle.bundle_identity:
            raise ProductRuntimeV1Error("runtime proof replay bundle identity mismatch")
        if self.proof.runtime_identity_digest != replay.runtime_identity_digest:
            raise ProductRuntimeV1Error("runtime proof runtime identity mismatch")

        expected_reasoning = ReasoningEngine(self.reasoning_result.artifacts).evaluate(
            self.proof.reasoning_target_id
        )
        if expected_reasoning.digest() != self.reasoning_result.digest():
            raise ProductRuntimeV1Error("reasoning result is not the deterministic engine result")
        if self.proof.reasoning_result_digest != self.reasoning_result.digest():
            raise ProductRuntimeV1Error("runtime proof reasoning digest mismatch")
        if self.proof.reasoning_outcome is not self.reasoning_result.decision.outcome:
            raise ProductRuntimeV1Error("runtime proof reasoning outcome mismatch")
        refs = _reasoning_evidence_nodes(self.reasoning_result, self.trust_graph)
        if refs != self.proof.reasoning_evidence_node_ids:
            raise ProductRuntimeV1Error("runtime proof reasoning evidence binding mismatch")


def converge_product_runtime_v1(
    *,
    ledger_bundle: CaseLedgerBundle,
    runtime_identity: RuntimeIdentity,
    migration_registry: CaseMigrationRegistry,
    epistemic_policy: EpistemicPolicyV2,
    trust_policy: TrustPolicyV1,
    reasoning_artifacts: tuple[ReasoningArtifact, ...],
    reasoning_target_id: str,
) -> ProductRuntimeRunV1:
    """Build one exact Product trust chain without introducing a new write path."""

    target = _require_canonical_identifier(
        reasoning_target_id,
        field_name="reasoning_target_id",
    )
    ledger_bundle.verify()

    epistemic = EpistemicProjectionV2.build(
        case_id=ledger_bundle.case_id,
        events=ledger_bundle.events,
        policy=epistemic_policy,
    )
    trust = EvidenceTrustGraph.build(
        case_id=ledger_bundle.case_id,
        events=ledger_bundle.events,
        epistemic_projection=epistemic,
        policy=trust_policy,
    )
    replay_bundle = CaseReplayBundleV2.build(
        ledger_bundle=ledger_bundle,
        runtime_identity=runtime_identity,
        migration_registry=migration_registry,
        epistemic_policy=epistemic_policy,
        trust_policy=trust_policy,
    )
    replay = replay_bundle.verify()

    reasoning_result = ReasoningEngine(reasoning_artifacts).evaluate(target)
    evidence_node_ids = _reasoning_evidence_nodes(reasoning_result, trust)

    body = {
        "schema": PRODUCT_RUNTIME_PROOF_SCHEMA_V1,
        "case_id": ledger_bundle.case_id.value,
        "ledger_head": replay.ledger_head.canonical_dict() if replay.ledger_head else None,
        "ledger_bundle_digest": ledger_bundle.bundle_digest.canonical_dict(),
        "epistemic_projection_identity": epistemic.projection_identity.canonical_dict(),
        "trust_graph_identity": trust.graph_identity.canonical_dict(),
        "replay_manifest_identity": replay.manifest_identity.canonical_dict(),
        "replay_bundle_identity": replay_bundle.bundle_identity.canonical_dict(),
        "runtime_identity_digest": replay.runtime_identity_digest.canonical_dict(),
        "reasoning_target_id": target,
        "reasoning_result_digest": reasoning_result.digest(),
        "reasoning_outcome": reasoning_result.decision.outcome.value,
        "reasoning_evidence_node_ids": list(evidence_node_ids),
        "authority": "derived-verification-only",
        "canonical_case_authority": "canonical-case-ledger",
    }
    proof = ProductRuntimeProofV1(
        case_id=ledger_bundle.case_id,
        ledger_head=replay.ledger_head,
        ledger_bundle_digest=ledger_bundle.bundle_digest,
        epistemic_projection_identity=epistemic.projection_identity,
        trust_graph_identity=trust.graph_identity,
        replay_manifest_identity=replay.manifest_identity,
        replay_bundle_identity=replay_bundle.bundle_identity,
        runtime_identity_digest=replay.runtime_identity_digest,
        reasoning_target_id=target,
        reasoning_result_digest=reasoning_result.digest(),
        reasoning_outcome=reasoning_result.decision.outcome,
        reasoning_evidence_node_ids=evidence_node_ids,
        proof_identity=ContentAddress.for_value(body),
    )
    run = ProductRuntimeRunV1(
        proof=proof,
        epistemic_projection=epistemic,
        trust_graph=trust,
        reasoning_result=reasoning_result,
        replay_bundle=replay_bundle,
    )
    run.verify()
    return run
