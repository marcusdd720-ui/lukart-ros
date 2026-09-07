from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from core.case_ledger import CanonicalCaseLedger, CaseId, ObjectId
from core.case_ledger.contracts import CaseLedgerContractError, ContentAddress
from core.case_replay_v2 import CaseReplayBundleV2
from core.critical_invariants import (
    CriticalInvariantId,
    CriticalInvariantInputs,
    CriticalInvariantRegistry,
    CriticalInvariantVerificationError,
    EpistemicInvariantProbe,
    MigrationInvariantProbe,
    SemanticInvariantProbe,
    verify_critical_invariants,
)
from core.p3.contracts import RuntimeIdentity, canonical_json
from core.p3.versioning import CaseMigrationRegistry, MigrationStep, VersionedCase
from core.semantic_change_v2 import (
    ArtifactKind,
    ImmutableArtifactRef,
    SemanticChangeGraphV2,
    SemanticPropagationPolicyV2,
)
from knowledge.epistemic import KnowledgeStatus
from knowledge.epistemic_assertions import EpistemicLedgerService, EpistemicPolicyV2
from knowledge.evidence_trust_graph import TrustPolicyV1


def _runtime(*, code: str = "a") -> RuntimeIdentity:
    return RuntimeIdentity(
        code_sha=code * 40,
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


def _serialized(value: object) -> dict[str, object]:
    canonical = value.canonical_dict()  # type: ignore[attr-defined]
    decoded = json.loads(canonical_json(canonical))
    assert isinstance(decoded, dict)
    return decoded


def _registry() -> CaseMigrationRegistry:
    registry = CaseMigrationRegistry()
    registry.register(
        MigrationStep(
            source_version="case.v1",
            target_version="case.v2",
            migrate=lambda payload: {**payload, "schema_upgraded": True},
        )
    )
    return registry


def _build_inputs(tmp_path: Path) -> CriticalInvariantInputs:
    runtime = _runtime()
    case_id = CaseId("CASE-IV01-001")
    policy = EpistemicPolicyV2.reference()

    with CanonicalCaseLedger(tmp_path / "source.db") as source_ledger:
        service = EpistemicLedgerService(source_ledger)
        service.create_assertion(
            case_id=case_id,
            subject_id=ObjectId("OBJ-IV01-1"),
            assertion_type="claim.v1",
            content={"value": "fixture"},
            initial_status=KnowledgeStatus.CLAIM,
            evidence_refs=(),
            runtime_identity=runtime,
            expected_head=None,
        )
        ledger_bundle = source_ledger.export_case(case_id)

    source_serialized = _serialized(ledger_bundle)
    with CanonicalCaseLedger(tmp_path / "restored.db") as restored_ledger:
        restored_ledger.restore_case(case_id, source_serialized)
        restored_bundle = restored_ledger.export_case(case_id)

    replay_bundle = CaseReplayBundleV2.build(
        ledger_bundle=ledger_bundle,
        runtime_identity=runtime,
        migration_registry=_registry(),
        epistemic_policy=policy,
        trust_policy=TrustPolicyV1.reference(),
    )

    changed = ImmutableArtifactRef(
        case_id=case_id,
        kind=ArtifactKind.EVENT,
        identity=ledger_bundle.events[0].event_id,
    )
    result = ImmutableArtifactRef(
        case_id=case_id,
        kind=ArtifactKind.RESULT,
        identity=ContentAddress.for_value({"result": "v1"}),
    )
    graph = SemanticChangeGraphV2(
        case_id=case_id,
        dependencies={
            changed: (),
            result: (changed,),
        },
    )

    return CriticalInvariantInputs(
        ledger_bundle=source_serialized,
        recovery_source_bundle=source_serialized,
        recovery_restored_bundle=_serialized(restored_bundle),
        replay_bundle=_serialized(replay_bundle),
        migration=MigrationInvariantProbe(
            registry=_registry(),
            source=VersionedCase.build(
                case_id=case_id.value,
                schema_version="case.v1",
                payload={"value": 1},
            ),
            target_version="case.v2",
        ),
        epistemic=EpistemicInvariantProbe(
            case_id=case_id,
            events=ledger_bundle.events,
            policy=policy,
        ),
        semantic=SemanticInvariantProbe(
            graph=graph,
            changed=(changed,),
            policy=SemanticPropagationPolicyV2.build(
                max_nodes=4,
                max_depth=4,
                max_work=8,
            ),
            replay_manifest_identity=replay_bundle.manifest.manifest_identity,
        ),
    )


def test_reference_registry_is_exact_content_addressed_and_complete() -> None:
    first = CriticalInvariantRegistry.reference()
    second = CriticalInvariantRegistry.reference()

    assert first == second
    assert first.registry_identity == second.registry_identity
    assert tuple(item.invariant_id for item in first.definitions) == tuple(
        sorted(CriticalInvariantId, key=lambda item: item.value)
    )
    first.verify()


def test_full_invariant_report_is_deterministic_and_exact_sha_bound(tmp_path: Path) -> None:
    inputs = _build_inputs(tmp_path)
    sha = "1" * 40

    first = verify_critical_invariants(
        code_sha=sha,
        expected_code_sha=sha,
        inputs=inputs,
    )
    second = verify_critical_invariants(
        code_sha=sha,
        expected_code_sha=sha,
        inputs=inputs,
    )

    assert first == second
    assert first.report_identity == second.report_identity
    assert all(result.outcome.value == "PASS" for result in first.results)
    assert len(first.results) == len(CriticalInvariantId)
    first.verify()

    other = verify_critical_invariants(
        code_sha="2" * 40,
        expected_code_sha="2" * 40,
        inputs=inputs,
    )
    assert other.report_identity != first.report_identity


def test_exact_sha_mismatch_fails_before_verification(tmp_path: Path) -> None:
    with pytest.raises(CriticalInvariantVerificationError, match="does not match"):
        verify_critical_invariants(
            code_sha="1" * 40,
            expected_code_sha="2" * 40,
            inputs=_build_inputs(tmp_path),
        )


@pytest.mark.parametrize(
    "value",
    (
        "A" * 40,
        "g" * 40,
        "1" * 39,
        "1" * 41,
        "  " + "1" * 40,
    ),
)
def test_invalid_code_identity_fails_closed(tmp_path: Path, value: str) -> None:
    with pytest.raises(CriticalInvariantVerificationError, match="code_sha"):
        verify_critical_invariants(
            code_sha=value,
            expected_code_sha=value,
            inputs=_build_inputs(tmp_path),
        )


def test_tampered_ccl_bundle_prevents_partial_pass_report(tmp_path: Path) -> None:
    inputs = _build_inputs(tmp_path)
    tampered = deepcopy(inputs.ledger_bundle)
    events = tampered["events"]
    assert isinstance(events, list)
    event = events[0]
    assert isinstance(event, dict)
    event["payload"] = {"tampered": True}

    with pytest.raises(CriticalInvariantVerificationError, match="CCL_BUNDLE_INTEGRITY"):
        verify_critical_invariants(
            code_sha="1" * 40,
            expected_code_sha="1" * 40,
            inputs=replace(inputs, ledger_bundle=tampered),
        )


def test_recovery_equivalence_rejects_two_individually_valid_histories(tmp_path: Path) -> None:
    inputs = _build_inputs(tmp_path)
    case_id = inputs.epistemic.case_id
    runtime = _runtime()

    with CanonicalCaseLedger(tmp_path / "extended.db") as ledger:
        ledger.restore_case(case_id, inputs.recovery_source_bundle)
        current_head = ledger.head(case_id)
        assert current_head is not None
        ledger.append_event(
            case_id=case_id,
            event_type="case.note.v1",
            runtime_identity=runtime,
            payload={"note": "extra valid event"},
            expected_head=current_head,
        )
        extended = ledger.export_case(case_id)

    with pytest.raises(CriticalInvariantVerificationError, match="recovery identity mismatch"):
        verify_critical_invariants(
            code_sha="1" * 40,
            expected_code_sha="1" * 40,
            inputs=replace(inputs, recovery_restored_bundle=_serialized(extended)),
        )


def test_tampered_replay_bundle_fails_closed(tmp_path: Path) -> None:
    inputs = _build_inputs(tmp_path)
    tampered = deepcopy(inputs.replay_bundle)
    manifest = tampered["manifest"]
    assert isinstance(manifest, dict)
    manifest["case_schema_version"] = "case.tampered"

    with pytest.raises(CriticalInvariantVerificationError, match="REPLAY_REBUILD_EQUIVALENCE"):
        verify_critical_invariants(
            code_sha="1" * 40,
            expected_code_sha="1" * 40,
            inputs=replace(inputs, replay_bundle=tampered),
        )


def test_nondeterministic_migration_is_rejected_by_production_contract(tmp_path: Path) -> None:
    inputs = _build_inputs(tmp_path)
    counter = 0

    def unstable(payload: Mapping[str, object]) -> Mapping[str, object]:
        nonlocal counter
        counter += 1
        return {**payload, "counter": counter}

    registry = CaseMigrationRegistry()
    registry.register(MigrationStep("case.v1", "case.v2", unstable))
    migration = replace(inputs.migration, registry=registry)

    with pytest.raises(CriticalInvariantVerificationError, match="MIGRATION_DETERMINISM"):
        verify_critical_invariants(
            code_sha="1" * 40,
            expected_code_sha="1" * 40,
            inputs=replace(inputs, migration=migration),
        )


def test_cross_case_epistemic_rebuild_fails_closed(tmp_path: Path) -> None:
    inputs = _build_inputs(tmp_path)
    epistemic = replace(inputs.epistemic, case_id=CaseId("CASE-IV01-OTHER"))

    with pytest.raises(CriticalInvariantVerificationError, match="EPISTEMIC_REBUILD_EQUIVALENCE"):
        verify_critical_invariants(
            code_sha="1" * 40,
            expected_code_sha="1" * 40,
            inputs=replace(inputs, epistemic=epistemic),
        )


def test_semantic_blast_radius_is_hard_failure_not_truncated_pass(tmp_path: Path) -> None:
    inputs = _build_inputs(tmp_path)
    semantic = replace(
        inputs.semantic,
        policy=SemanticPropagationPolicyV2.build(
            max_nodes=1,
            max_depth=4,
            max_work=8,
        ),
    )

    with pytest.raises(CriticalInvariantVerificationError, match="SEMANTIC_PROPAGATION_BOUNDED"):
        verify_critical_invariants(
            code_sha="1" * 40,
            expected_code_sha="1" * 40,
            inputs=replace(inputs, semantic=semantic),
        )


def test_ccl_state_model_rejects_every_stale_head_and_preserves_chain(tmp_path: Path) -> None:
    case_id = CaseId("CASE-IV01-STATE")
    runtime = _runtime()
    expected_head = None

    with CanonicalCaseLedger(tmp_path / "state.db") as ledger:
        for index in range(12):
            stale_head = expected_head
            event = ledger.append_event(
                case_id=case_id,
                event_type="state.transition.v1",
                runtime_identity=runtime,
                payload={"step": index},
                expected_head=expected_head,
            )
            expected_head = event.event_id
            bundle = ledger.export_case(case_id)
            bundle.verify()
            assert bundle.head_event_id == expected_head
            assert tuple(item.case_sequence for item in bundle.events) == tuple(
                range(index + 1)
            )

            with pytest.raises(CaseLedgerContractError, match="head mismatch"):
                ledger.append_event(
                    case_id=case_id,
                    event_type="state.stale-write.v1",
                    runtime_identity=runtime,
                    payload={"step": index},
                    expected_head=stale_head,
                )
            assert ledger.head(case_id) == expected_head


def test_recovery_state_model_never_merges_nonempty_target(tmp_path: Path) -> None:
    inputs = _build_inputs(tmp_path)
    case_id = inputs.epistemic.case_id
    runtime = _runtime()

    with CanonicalCaseLedger(tmp_path / "nonempty.db") as ledger:
        ledger.append_event(
            case_id=case_id,
            event_type="existing.target.v1",
            runtime_identity=runtime,
            payload={"existing": True},
            expected_head=None,
        )
        before = ledger.export_case(case_id)
        with pytest.raises(CaseLedgerContractError, match="not empty"):
            ledger.restore_case(case_id, inputs.recovery_source_bundle)
        after = ledger.export_case(case_id)

    assert after == before


def test_iv01_verifier_has_no_case_write_or_persistence_authority() -> None:
    source = Path("core/critical_invariants.py").read_text(encoding="utf-8")

    for forbidden in (
        ".append_event(",
        ".publish_revision(",
        ".restore_case(",
        "SQLiteProvenanceStore",
        "sqlite3",
    ):
        assert forbidden not in source