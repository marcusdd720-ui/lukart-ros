from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.case_ledger import (
    CanonicalCaseLedger,
    CaseId,
    CaseLedgerBundle,
    ContentAddress,
    ObjectId,
)
from core.p3.contracts import RuntimeIdentity
from core.p3.versioning import CaseMigrationRegistry
from core.product_runtime_v1 import ProductRuntimeRunV1, converge_product_runtime_v1
from core.product_verification_evidence_v1 import (
    ProductVerificationCheckId,
    ProductVerificationEvidenceV1Error,
    ProductVerificationInputsV1,
    ProductVerificationRegistryV1,
    verify_product_evidence_v1,
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


def _ledger_bundle(
    tmp_path: Path,
    *,
    case_id: CaseId,
) -> tuple[CaseLedgerBundle, ContentAddress]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    with CanonicalCaseLedger(tmp_path / f"{case_id.value}.db") as ledger:
        evidence = ledger.append_event(
            case_id=case_id,
            event_type="evidence.ingested.v1",
            runtime_identity=_runtime(),
            payload={"source": "synthetic-pve", "digest": "9" * 64},
            expected_head=None,
        )
        service = EpistemicLedgerService(ledger)
        service.create_assertion(
            case_id=case_id,
            subject_id=ObjectId("OBJ-PVE-FACT"),
            assertion_type="fact.v1",
            content={"value": "synthetic PVE fixture"},
            initial_status=KnowledgeStatus.FACT,
            evidence_refs=(EvidenceEventRef(case_id=case_id, event_id=evidence.event_id),),
            runtime_identity=_runtime(),
            expected_head=evidence.event_id,
        )
        return ledger.export_case(case_id), evidence.event_id


def _run(
    tmp_path: Path,
    *,
    case_id: CaseId,
    abstain: bool,
) -> ProductRuntimeRunV1:
    bundle, evidence_id = _ledger_bundle(tmp_path, case_id=case_id)
    if abstain:
        support = ReasoningArtifact(
            artifact_id="U1",
            statement="Material point remains unresolved",
            status=KnowledgeStatus.UNRESOLVED,
            evidence_refs=(event_node_id(evidence_id),),
        )
    else:
        support = ReasoningArtifact(
            artifact_id="F1",
            statement="Synthetic evidence-backed fact",
            status=KnowledgeStatus.FACT,
            evidence_refs=(event_node_id(evidence_id),),
        )
    conclusion = ReasoningArtifact(
        artifact_id="C1",
        statement="Synthetic PVE conclusion",
        status=KnowledgeStatus.CONCLUSION,
        support_ids=(support.artifact_id,),
    )
    return converge_product_runtime_v1(
        ledger_bundle=bundle,
        runtime_identity=_runtime(),
        migration_registry=CaseMigrationRegistry(),
        epistemic_policy=EpistemicPolicyV2.reference(),
        trust_policy=TrustPolicyV1.reference(),
        reasoning_artifacts=(support, conclusion),
        reasoning_target_id="C1",
    )


def _inputs(tmp_path: Path) -> ProductVerificationInputsV1:
    return ProductVerificationInputsV1(
        supported_run=_run(
            tmp_path / "supported",
            case_id=CaseId("CASE-PVE-SUPPORTED"),
            abstain=False,
        ),
        abstain_run=_run(
            tmp_path / "abstain",
            case_id=CaseId("CASE-PVE-ABSTAIN"),
            abstain=True,
        ),
    )


def _candidate_sha() -> str:
    return "a" * 40


def test_reference_registry_is_exact_and_content_addressed() -> None:
    registry = ProductVerificationRegistryV1.reference()

    assert tuple(item.check_id for item in registry.definitions) == tuple(
        sorted(ProductVerificationCheckId, key=lambda item: item.value)
    )
    assert len(registry.definitions) == 5
    registry.verify()


def test_complete_product_verification_report_is_deterministic(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)

    first = verify_product_evidence_v1(
        inputs=inputs,
        code_sha=_candidate_sha(),
        expected_code_sha=_candidate_sha(),
    )
    second = verify_product_evidence_v1(
        inputs=inputs,
        code_sha=_candidate_sha(),
        expected_code_sha=_candidate_sha(),
    )

    assert first == second
    assert first.report_identity == second.report_identity
    assert first.supported_proof_identity == inputs.supported_run.proof.proof_identity
    assert first.abstain_proof_identity == inputs.abstain_run.proof.proof_identity
    assert tuple(result.check_id for result in first.results) == tuple(
        item.check_id for item in ProductVerificationRegistryV1.reference().definitions
    )
    first.verify()


def test_abstain_evidence_preserves_open_questions(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    assert inputs.abstain_run.proof.reasoning_outcome is ReasoningOutcome.ABSTAIN
    assert inputs.abstain_run.reasoning_result.open_questions

    report = verify_product_evidence_v1(
        inputs=inputs,
        code_sha=_candidate_sha(),
        expected_code_sha=_candidate_sha(),
    )
    result = next(
        item
        for item in report.results
        if item.check_id is ProductVerificationCheckId.ABSTAIN_OPEN_QUESTIONS
    )
    result.verify()


def test_exact_candidate_sha_mismatch_fails_before_report(tmp_path: Path) -> None:
    with pytest.raises(ProductVerificationEvidenceV1Error, match="externally expected"):
        verify_product_evidence_v1(
            inputs=_inputs(tmp_path),
            code_sha="a" * 40,
            expected_code_sha="b" * 40,
        )


def test_malformed_candidate_sha_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ProductVerificationEvidenceV1Error, match="Git object id"):
        verify_product_evidence_v1(
            inputs=_inputs(tmp_path),
            code_sha="not-a-git-object",
            expected_code_sha="not-a-git-object",
        )


def test_wrong_scenario_outcome_cannot_enter_pass_report(tmp_path: Path) -> None:
    supported = _run(
        tmp_path / "one",
        case_id=CaseId("CASE-PVE-ONE"),
        abstain=False,
    )
    invalid = ProductVerificationInputsV1(
        supported_run=supported,
        abstain_run=supported,
    )

    with pytest.raises(ProductVerificationEvidenceV1Error, match="ABSTAIN outcome"):
        verify_product_evidence_v1(
            inputs=invalid,
            code_sha=_candidate_sha(),
            expected_code_sha=_candidate_sha(),
        )


def test_report_identity_tampering_is_rejected(tmp_path: Path) -> None:
    report = verify_product_evidence_v1(
        inputs=_inputs(tmp_path),
        code_sha=_candidate_sha(),
        expected_code_sha=_candidate_sha(),
    )
    with pytest.raises(ProductVerificationEvidenceV1Error, match="content-address mismatch"):
        replace(report, report_identity=ContentAddress.for_value({"tampered": True}))


def test_report_cannot_drop_required_check(tmp_path: Path) -> None:
    report = verify_product_evidence_v1(
        inputs=_inputs(tmp_path),
        code_sha=_candidate_sha(),
        expected_code_sha=_candidate_sha(),
    )
    error = "missing, duplicated or reorders"
    with pytest.raises(ProductVerificationEvidenceV1Error, match=error):
        replace(report, results=report.results[:-1])


def test_pve_verifier_has_no_canonical_ledger_write_or_sqlite_authority() -> None:
    source = Path("core/product_verification_evidence_v1.py").read_text(encoding="utf-8")

    assert "CanonicalCaseLedger" not in source
    assert ".append_event(" not in source
    assert "sqlite" not in source.lower()
