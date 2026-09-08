from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.case_ledger import CanonicalCaseLedger, CaseId, ContentAddress, ObjectId
from core.p3.contracts import RuntimeIdentity
from core.p3.versioning import CaseMigrationRegistry
from core.product_runtime_v1 import (
    PRODUCT_RUNTIME_ARTIFACT_TYPE,
    PRODUCT_RUNTIME_ARTIFACT_VERSION,
    ProductRuntimeProofV1,
    ProductRuntimeV1Error,
    converge_product_runtime_v1,
)
from knowledge.epistemic import KnowledgeStatus
from knowledge.epistemic_assertions import (
    EpistemicLedgerService,
    EpistemicPolicyV2,
    EvidenceEventRef,
)
from knowledge.evidence_trust_graph import TrustPolicyV1, event_node_id
from reasoning.models import ReasoningArtifact, ReasoningOutcome


def _runtime() -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha="a" * 40,
        schema_version="case.v1",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        provider_identities=("provider-a@1",),
        plugin_identities=(),
        input_digests=("d" * 64,),
        evidence_digests=("e" * 64,),
        provider_inventory_declared=True,
        plugin_inventory_declared=True,
        input_inventory_declared=True,
        evidence_inventory_declared=True,
        dependency_lock_digest="f" * 64,
        python_implementation="CPython",
        python_version="3.13.7",
        platform_tag="linux-x86_64",
        project_version="1.1.0.dev0",
        build_backend="lukart_build_backend",
        execution_environment_declared=True,
    )


def _ledger_bundle(tmp_path: Path, *, case_id: CaseId | None = None):
    selected = case_id or CaseId("CASE-PRC-001")
    with CanonicalCaseLedger(tmp_path / f"{selected.value}.db") as ledger:
        evidence = ledger.append_event(
            case_id=selected,
            event_type="evidence.ingested.v1",
            runtime_identity=_runtime(),
            payload={"source": "synthetic", "digest": "9" * 64},
            expected_head=None,
        )
        service = EpistemicLedgerService(ledger)
        service.create_assertion(
            case_id=selected,
            subject_id=ObjectId("OBJ-FACT"),
            assertion_type="fact.v1",
            content={"value": "verified fixture"},
            initial_status=KnowledgeStatus.FACT,
            evidence_refs=(EvidenceEventRef(case_id=selected, event_id=evidence.event_id),),
            runtime_identity=_runtime(),
            expected_head=evidence.event_id,
        )
        return ledger.export_case(selected), evidence.event_id


def _reasoning(evidence_id: ContentAddress) -> tuple[ReasoningArtifact, ...]:
    fact = ReasoningArtifact(
        artifact_id="F1",
        statement="Verified fixture fact",
        status=KnowledgeStatus.FACT,
        evidence_refs=(event_node_id(evidence_id),),
    )
    conclusion = ReasoningArtifact(
        artifact_id="C1",
        statement="Evidence-backed fixture conclusion",
        status=KnowledgeStatus.CONCLUSION,
        support_ids=(fact.artifact_id,),
    )
    return fact, conclusion


def _run(tmp_path: Path):
    ledger_bundle, evidence_id = _ledger_bundle(tmp_path)
    return converge_product_runtime_v1(
        ledger_bundle=ledger_bundle,
        runtime_identity=_runtime(),
        migration_registry=CaseMigrationRegistry(),
        epistemic_policy=EpistemicPolicyV2.reference(),
        trust_policy=TrustPolicyV1.reference(),
        reasoning_artifacts=_reasoning(evidence_id),
        reasoning_target_id="C1",
    )


def _proof_body_with_case(proof: ProductRuntimeProofV1, case_id: CaseId) -> dict[str, object]:
    body = proof.canonical_body()
    body["case_id"] = case_id.value
    return body


def test_converged_runtime_binds_exact_chain_and_is_deterministic(tmp_path: Path) -> None:
    first = _run(tmp_path)
    second = _run(tmp_path)

    assert first.proof == second.proof
    assert first.proof.case_id == CaseId("CASE-PRC-001")
    assert first.proof.ledger_head == first.replay_bundle.manifest.ledger_head
    assert (
        first.proof.epistemic_projection_identity
        == first.epistemic_projection.projection_identity
    )
    assert first.proof.trust_graph_identity == first.trust_graph.graph_identity
    assert first.proof.replay_manifest_identity == first.replay_bundle.manifest.manifest_identity
    assert first.proof.reasoning_outcome is ReasoningOutcome.CONCLUDE
    assert first.reasoning_result.decision.artifact_id == "C1"
    first.verify()


def test_reasoning_evidence_must_resolve_to_exact_trust_node(tmp_path: Path) -> None:
    ledger_bundle, _evidence_id = _ledger_bundle(tmp_path)
    fact = ReasoningArtifact(
        artifact_id="F1",
        statement="Legacy unbound fact ref",
        status=KnowledgeStatus.FACT,
        evidence_refs=("DOC-1#p1",),
    )
    conclusion = ReasoningArtifact(
        artifact_id="C1",
        statement="Unsafe conclusion",
        status=KnowledgeStatus.CONCLUSION,
        support_ids=("F1",),
    )

    with pytest.raises(ProductRuntimeV1Error, match="does not resolve"):
        converge_product_runtime_v1(
            ledger_bundle=ledger_bundle,
            runtime_identity=_runtime(),
            migration_registry=CaseMigrationRegistry(),
            epistemic_policy=EpistemicPolicyV2.reference(),
            trust_policy=TrustPolicyV1.reference(),
            reasoning_artifacts=(fact, conclusion),
            reasoning_target_id="C1",
        )


def test_valid_abstention_remains_first_class_runtime_result(tmp_path: Path) -> None:
    ledger_bundle, evidence_id = _ledger_bundle(tmp_path)
    unresolved = ReasoningArtifact(
        artifact_id="U1",
        statement="Material point remains unresolved",
        status=KnowledgeStatus.UNRESOLVED,
        evidence_refs=(event_node_id(evidence_id),),
    )
    conclusion = ReasoningArtifact(
        artifact_id="C1",
        statement="Premature conclusion",
        status=KnowledgeStatus.CONCLUSION,
        support_ids=("U1",),
    )

    run = converge_product_runtime_v1(
        ledger_bundle=ledger_bundle,
        runtime_identity=_runtime(),
        migration_registry=CaseMigrationRegistry(),
        epistemic_policy=EpistemicPolicyV2.reference(),
        trust_policy=TrustPolicyV1.reference(),
        reasoning_artifacts=(unresolved, conclusion),
        reasoning_target_id="C1",
    )

    assert run.proof.reasoning_outcome is ReasoningOutcome.ABSTAIN
    assert run.reasoning_result.open_questions
    run.verify()


def test_cross_case_proof_substitution_is_rejected(tmp_path: Path) -> None:
    run = _run(tmp_path)
    foreign_case = CaseId("CASE-FOREIGN")
    forged = replace(
        run.proof,
        case_id=foreign_case,
        proof_identity=ContentAddress.for_value(
            _proof_body_with_case(run.proof, foreign_case)
        ),
    )
    forged_run = replace(run, proof=forged)

    with pytest.raises(ProductRuntimeV1Error, match="case does not match"):
        forged_run.verify()


def test_proof_exposes_exact_document_binding_identity(tmp_path: Path) -> None:
    proof = _run(tmp_path).proof

    assert proof.artifact_type == PRODUCT_RUNTIME_ARTIFACT_TYPE
    assert proof.artifact_id == "case:CASE-PRC-001"
    assert proof.artifact_version == PRODUCT_RUNTIME_ARTIFACT_VERSION
    assert proof.artifact_digest == proof.proof_identity.digest


def test_product_runtime_module_has_no_canonical_ledger_write_path() -> None:
    source = Path("core/product_runtime_v1.py").read_text(encoding="utf-8")

    assert "CanonicalCaseLedger" not in source
    assert ".append_event(" not in source
