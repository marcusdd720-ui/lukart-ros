from __future__ import annotations

from pathlib import Path

import pytest

from core.artifact_escrow_v1 import (
    ArtifactEscrowManifestV1,
    EscrowArtifactBindingV1,
    EscrowLimitsV1,
    FileSystemEscrowBackendV1,
)
from core.case_ledger import CanonicalCaseLedger, CaseId, CaseLedgerBundle, ContentAddress, ObjectId
from core.long_range_drift_v1 import (
    CanonicalSemanticResultV1,
    CurrentPathResultV1,
    DriftClassification,
    DriftReportV1,
    FrozenExecutionStatus,
    FrozenPathResultV1,
    FrozenPathRunnerV1,
    LongRangeDriftError,
)
from core.long_range_replay_v1 import (
    LongRangeReplayManifestV1,
    ReplayArtifactBindingV1,
    ReplayArtifactRole,
    ReplayAssuranceLevel,
    ReplayPreservationStatus,
)
from core.p3.contracts import RuntimeIdentity, canonical_json
from core.p3.versioning import CaseMigrationRegistry
from core.product_runtime_v1 import ProductRuntimeRunV1, converge_product_runtime_v1
from knowledge.epistemic import KnowledgeStatus
from knowledge.epistemic_assertions import (
    EpistemicLedgerService,
    EpistemicPolicyV2,
    EvidenceEventRef,
)
from knowledge.evidence_trust_graph import TrustPolicyV1, event_node_id
from reasoning.models import ReasoningArtifact

COMMIT_SHA = "1" * 40
TREE_SHA = "2" * 40
CASE_ID = CaseId("CASE-LRD-01D-0001")


def _runtime(*, providers: bool = True, code: str = "a") -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha=code * 40,
        schema_version="case.v1",
        config_digest="b" * 64,
        corpus_digest="c" * 64,
        provider_identities=(("provider-a@1",) if providers else ()),
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
    case_id: CaseId = CASE_ID,
    runtime: RuntimeIdentity | None = None,
) -> tuple[CaseLedgerBundle, ContentAddress]:
    selected_runtime = runtime or _runtime()
    tmp_path.mkdir(parents=True, exist_ok=True)
    with CanonicalCaseLedger(tmp_path / f"{case_id.value}.db") as ledger:
        evidence = ledger.append_event(
            case_id=case_id,
            event_type="evidence.ingested.v1",
            runtime_identity=selected_runtime,
            payload={"source": "lrd-01d-fixture", "digest": "9" * 64},
            expected_head=None,
        )
        service = EpistemicLedgerService(ledger)
        service.create_assertion(
            case_id=case_id,
            subject_id=ObjectId("OBJ-LRD-01D"),
            assertion_type="fact.v1",
            content={"value": "verified historical fixture"},
            initial_status=KnowledgeStatus.FACT,
            evidence_refs=(EvidenceEventRef(case_id=case_id, event_id=evidence.event_id),),
            runtime_identity=selected_runtime,
            expected_head=evidence.event_id,
        )
        return ledger.export_case(case_id), evidence.event_id


def _reasoning(
    evidence_id: ContentAddress,
    *,
    conclusion_statement: str = "Stable semantic conclusion",
) -> tuple[ReasoningArtifact, ...]:
    fact = ReasoningArtifact(
        artifact_id="F1",
        statement="Verified historical fact",
        status=KnowledgeStatus.FACT,
        evidence_refs=(event_node_id(evidence_id),),
    )
    conclusion = ReasoningArtifact(
        artifact_id="C1",
        statement=conclusion_statement,
        status=KnowledgeStatus.CONCLUSION,
        support_ids=(fact.artifact_id,),
    )
    return fact, conclusion


def _product_run(
    tmp_path: Path,
    *,
    case_id: CaseId = CASE_ID,
    providers: bool = True,
    code: str = "a",
    conclusion_statement: str = "Stable semantic conclusion",
) -> ProductRuntimeRunV1:
    runtime = _runtime(providers=providers, code=code)
    ledger_bundle, evidence_id = _ledger_bundle(
        tmp_path,
        case_id=case_id,
        runtime=runtime,
    )
    return converge_product_runtime_v1(
        ledger_bundle=ledger_bundle,
        runtime_identity=runtime,
        migration_registry=CaseMigrationRegistry(),
        epistemic_policy=EpistemicPolicyV2.reference(),
        trust_policy=TrustPolicyV1.reference(),
        reasoning_artifacts=_reasoning(
            evidence_id,
            conclusion_statement=conclusion_statement,
        ),
        reasoning_target_id="C1",
    )


def _address(label: str) -> ContentAddress:
    return ContentAddress.for_value({"lrd-01d": label})


def _historical_manifest(
    run: ProductRuntimeRunV1,
    *,
    unavailable_role: ReplayArtifactRole | None = None,
    presentation_identity: ContentAddress | None = None,
    case_bundle_identity: ContentAddress | None = None,
) -> tuple[LongRangeReplayManifestV1, CanonicalSemanticResultV1]:
    semantic = CanonicalSemanticResultV1.from_product_run(run)
    bindings: list[ReplayArtifactBindingV1] = []
    for role in ReplayArtifactRole:
        if role is ReplayArtifactRole.CASE_REPLAY_BUNDLE:
            identity = case_bundle_identity or run.replay_bundle.bundle_identity
        elif role is ReplayArtifactRole.SEMANTIC_RESULT:
            identity = semantic.semantic_identity
        else:
            identity = _address(role.value)
        bindings.append(
            ReplayArtifactBindingV1(
                role=role,
                identity=identity,
                preservation=(
                    ReplayPreservationStatus.UNAVAILABLE
                    if role is unavailable_role
                    else ReplayPreservationStatus.PRESERVED
                ),
            )
        )
    return (
        LongRangeReplayManifestV1.build(
            case_id=run.proof.case_id.value,
            case_replay_manifest_identity=run.replay_bundle.manifest.manifest_identity,
            coverage_matrix_identity=_address("coverage"),
            code_commit_sha=COMMIT_SHA,
            code_tree_sha=TREE_SHA,
            artifacts=bindings,
            semantic_result_identity=semantic.semantic_identity,
            presentation_identity=presentation_identity,
        ),
        semantic,
    )


def _materialize(
    tmp_path: Path,
    run: ProductRuntimeRunV1,
    *,
    unavailable_role: ReplayArtifactRole | None = None,
    presentation_identity: ContentAddress | None = None,
    case_bundle_identity: ContentAddress | None = None,
    semantic_override: bytes | None = None,
) -> tuple[
    FileSystemEscrowBackendV1,
    LongRangeReplayManifestV1,
    ArtifactEscrowManifestV1,
    EscrowLimitsV1,
]:
    long_range, semantic = _historical_manifest(
        run,
        unavailable_role=unavailable_role,
        presentation_identity=presentation_identity,
        case_bundle_identity=case_bundle_identity,
    )
    limits = EscrowLimitsV1()
    backend = FileSystemEscrowBackendV1(tmp_path / "escrow")
    by_role = {item.role: item for item in long_range.artifacts}
    escrow_bindings: list[EscrowArtifactBindingV1] = []
    for role in ReplayArtifactRole:
        logical = by_role[role]
        if logical.preservation is not ReplayPreservationStatus.PRESERVED:
            continue
        if role is ReplayArtifactRole.CASE_REPLAY_BUNDLE:
            data = canonical_json(run.replay_bundle.canonical_dict()).encode("utf-8")
        elif role is ReplayArtifactRole.SEMANTIC_RESULT:
            data = (
                semantic_override
                if semantic_override is not None
                else canonical_json(semantic.canonical_dict()).encode("utf-8")
            )
        else:
            data = f"verified-lrd-01d::{role.value}".encode()
        blob = backend.publish(data, limits=limits)
        escrow_bindings.append(
            EscrowArtifactBindingV1.build(
                role=role,
                logical_identity=logical.identity,
                blob=blob,
            )
        )
    escrow = ArtifactEscrowManifestV1.build(
        long_range_manifest=long_range,
        bindings=escrow_bindings,
    )
    return backend, long_range, escrow, limits


def _frozen(
    backend: FileSystemEscrowBackendV1,
    long_range: LongRangeReplayManifestV1,
    escrow: ArtifactEscrowManifestV1,
    limits: EscrowLimitsV1,
) -> FrozenPathResultV1:
    return FrozenPathRunnerV1(limits=limits).verify(
        expected_case_id=CASE_ID.value,
        long_range_manifest=long_range,
        escrow_manifest=escrow,
        escrow_root=backend.root,
    )


def test_frozen_path_rebuilds_case_replay_offline_and_verifies_external_outputs(
    tmp_path: Path,
) -> None:
    historical = _product_run(tmp_path / "historical")
    backend, long_range, escrow, limits = _materialize(tmp_path, historical)

    frozen = _frozen(backend, long_range, escrow, limits)

    assert frozen.execution_status is FrozenExecutionStatus.VERIFIED
    assert frozen.network_mode == "OFF"
    assert frozen.network_enforcement == "python-runtime-guard"
    assert frozen.process_enforcement == "python-audit-hook-deny"
    assert frozen.native_ffi_enforcement == "python-audit-hook-deny"
    assert frozen.kernel_sandbox is False
    assert frozen.case_replay_bundle_identity == historical.replay_bundle.bundle_identity
    assert (
        frozen.case_replay_manifest_identity
        == historical.replay_bundle.manifest.manifest_identity
    )
    assert (
        frozen.epistemic_projection_identity
        == historical.replay_bundle.manifest.epistemic_projection_identity
    )
    assert frozen.trust_graph_identity == historical.replay_bundle.manifest.trust_graph_identity
    assert (
        frozen.runtime_identity_digest
        == historical.replay_bundle.manifest.runtime_identity_digest
    )
    assert frozen.assurance_level is ReplayAssuranceLevel.VERIFIED_EXTERNAL
    assert frozen.external_execution_present is True
    assert frozen.external_outputs_verified is True
    assert FrozenPathResultV1.from_dict(frozen.canonical_dict()) == frozen


def test_no_external_provider_history_can_reach_exact_assurance(tmp_path: Path) -> None:
    historical = _product_run(tmp_path / "historical", providers=False)
    backend, long_range, escrow, limits = _materialize(tmp_path, historical)

    frozen = _frozen(backend, long_range, escrow, limits)

    assert frozen.external_execution_present is False
    assert frozen.external_outputs_verified is False
    assert frozen.assurance_level is ReplayAssuranceLevel.EXACT


def test_external_history_without_preserved_response_is_unverifiable_not_exact(
    tmp_path: Path,
) -> None:
    historical = _product_run(tmp_path / "historical")
    backend, long_range, escrow, limits = _materialize(
        tmp_path,
        historical,
        unavailable_role=ReplayArtifactRole.PROVIDER_RESPONSES,
    )

    frozen = _frozen(backend, long_range, escrow, limits)

    assert frozen.execution_status is FrozenExecutionStatus.VERIFIED
    assert frozen.external_execution_present is True
    assert frozen.external_outputs_verified is False
    assert frozen.assurance_level is ReplayAssuranceLevel.UNVERIFIABLE


def test_missing_essential_frozen_material_returns_unverifiable_without_guessing(
    tmp_path: Path,
) -> None:
    historical = _product_run(tmp_path / "historical")
    backend, long_range, escrow, limits = _materialize(
        tmp_path,
        historical,
        unavailable_role=ReplayArtifactRole.CASE_REPLAY_BUNDLE,
    )

    frozen = _frozen(backend, long_range, escrow, limits)

    assert frozen.execution_status is FrozenExecutionStatus.UNVERIFIABLE
    assert frozen.assurance_level is ReplayAssuranceLevel.UNVERIFIABLE
    assert frozen.case_replay_manifest_identity is None
    assert frozen.semantic_result_identity is None
    assert frozen.task_digest is None
    assert frozen.network_enforcement == "NOT_EXECUTED"


def test_tampered_case_replay_bytes_fail_closed_inside_offline_child(tmp_path: Path) -> None:
    historical = _product_run(tmp_path / "historical")
    backend, long_range, escrow, limits = _materialize(tmp_path, historical)
    binding = next(
        item
        for item in escrow.bindings
        if item.role is ReplayArtifactRole.CASE_REPLAY_BUNDLE
    )
    stored = backend.root / "sha256" / binding.blob.digest[:2] / binding.blob.digest
    stored.chmod(0o600)
    mutated = bytearray(stored.read_bytes())
    mutated[-2] ^= 0x01
    stored.write_bytes(mutated)

    with pytest.raises(LongRangeDriftError, match="Frozen Path failed"):
        _frozen(backend, long_range, escrow, limits)


def test_case_replay_logical_identity_substitution_fails_closed(tmp_path: Path) -> None:
    historical = _product_run(tmp_path / "historical")
    backend, long_range, escrow, limits = _materialize(
        tmp_path,
        historical,
        case_bundle_identity=_address("forged-case-bundle"),
    )

    with pytest.raises(LongRangeDriftError, match="Frozen Path failed"):
        _frozen(backend, long_range, escrow, limits)


def test_unknown_semantic_schema_field_fails_closed(tmp_path: Path) -> None:
    historical = _product_run(tmp_path / "historical")
    semantic = CanonicalSemanticResultV1.from_product_run(historical).canonical_dict()
    semantic["implicit_equivalence"] = True
    forged_bytes = canonical_json(semantic).encode("utf-8")
    backend, long_range, escrow, limits = _materialize(
        tmp_path,
        historical,
        semantic_override=forged_bytes,
    )

    with pytest.raises(LongRangeDriftError, match="Frozen Path failed"):
        _frozen(backend, long_range, escrow, limits)


def test_current_path_consumes_verified_product_runtime_and_gets_new_identity(
    tmp_path: Path,
) -> None:
    current_run = _product_run(tmp_path / "current", code="b")
    current = CurrentPathResultV1.build(
        run=current_run,
        presentation_identity=_address("presentation-current"),
    )

    assert current.product_runtime_proof_identity == current_run.proof.proof_identity
    assert current.runtime_identity_digest == current_run.proof.runtime_identity_digest
    assert current.semantic_result == CanonicalSemanticResultV1.from_product_run(current_run)
    assert CurrentPathResultV1.from_dict(current.canonical_dict()) == current


def test_same_semantics_with_renderer_change_is_presentation_only(tmp_path: Path) -> None:
    historical = _product_run(tmp_path / "historical")
    old_presentation = _address("presentation-old")
    new_presentation = _address("presentation-new")
    backend, long_range, escrow, limits = _materialize(
        tmp_path,
        historical,
        presentation_identity=old_presentation,
    )
    frozen = _frozen(backend, long_range, escrow, limits)
    current = CurrentPathResultV1.build(
        run=_product_run(tmp_path / "current"),
        presentation_identity=new_presentation,
    )

    report = DriftReportV1.build(frozen=frozen, current=current)

    assert report.classification is DriftClassification.PRESENTATION_ONLY
    assert report.semantic_equal is True
    assert report.presentation_equal is False
    assert DriftReportV1.from_dict(report.canonical_dict()) == report


def test_true_reasoning_semantic_change_is_separate_semantic_drift(tmp_path: Path) -> None:
    historical = _product_run(tmp_path / "historical")
    presentation = _address("presentation-same")
    backend, long_range, escrow, limits = _materialize(
        tmp_path,
        historical,
        presentation_identity=presentation,
    )
    frozen = _frozen(backend, long_range, escrow, limits)
    changed_current = _product_run(
        tmp_path / "current",
        conclusion_statement="Materially changed semantic conclusion",
    )
    current = CurrentPathResultV1.build(
        run=changed_current,
        presentation_identity=presentation,
    )

    report = DriftReportV1.build(frozen=frozen, current=current)

    assert report.classification is DriftClassification.SEMANTIC_DRIFT
    assert report.semantic_equal is False
    assert report.presentation_equal is True


def test_identical_current_semantics_and_presentation_are_no_drift(tmp_path: Path) -> None:
    historical = _product_run(tmp_path / "historical")
    presentation = _address("presentation-same")
    backend, long_range, escrow, limits = _materialize(
        tmp_path,
        historical,
        presentation_identity=presentation,
    )
    frozen = _frozen(backend, long_range, escrow, limits)
    current = CurrentPathResultV1.build(
        run=_product_run(tmp_path / "current"),
        presentation_identity=presentation,
    )

    report = DriftReportV1.build(frozen=frozen, current=current)

    assert report.classification is DriftClassification.NO_DRIFT
    assert report.semantic_equal is True
    assert report.presentation_equal is True


def test_unverifiable_frozen_path_never_fabricates_drift_equality(tmp_path: Path) -> None:
    historical = _product_run(tmp_path / "historical")
    backend, long_range, escrow, limits = _materialize(
        tmp_path,
        historical,
        unavailable_role=ReplayArtifactRole.CASE_REPLAY_BUNDLE,
    )
    frozen = _frozen(backend, long_range, escrow, limits)
    current = CurrentPathResultV1.build(run=_product_run(tmp_path / "current"))

    report = DriftReportV1.build(frozen=frozen, current=current)

    assert report.classification is DriftClassification.UNVERIFIABLE
    assert report.semantic_equal is None
    assert report.presentation_equal is None


def test_cross_case_frozen_current_comparison_fails_closed(tmp_path: Path) -> None:
    historical = _product_run(tmp_path / "historical")
    backend, long_range, escrow, limits = _materialize(tmp_path, historical)
    frozen = _frozen(backend, long_range, escrow, limits)
    current = CurrentPathResultV1.build(
        run=_product_run(
            tmp_path / "foreign",
            case_id=CaseId("CASE-LRD-01D-FOREIGN"),
        )
    )

    with pytest.raises(LongRangeDriftError, match="across cases"):
        DriftReportV1.build(frozen=frozen, current=current)


def test_canonical_semantic_identity_is_order_stable_and_unknown_fields_fail_closed(
    tmp_path: Path,
) -> None:
    run = _product_run(tmp_path / "run")
    semantic = CanonicalSemanticResultV1.from_product_run(run)
    raw = semantic.canonical_dict()
    reordered = {key: raw[key] for key in reversed(tuple(raw))}

    assert CanonicalSemanticResultV1.from_dict(reordered) == semantic

    unknown = dict(raw)
    unknown["locale_guess"] = "pl_PL"
    with pytest.raises(LongRangeDriftError, match="unknown=locale_guess"):
        CanonicalSemanticResultV1.from_dict(unknown)


def test_lrd_01d_module_has_no_canonical_ledger_write_path() -> None:
    source = Path("core/long_range_drift_v1.py").read_text(encoding="utf-8")

    assert "CanonicalCaseLedger" not in source
    assert ".append_event(" not in source
