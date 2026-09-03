from __future__ import annotations

from dataclasses import replace

import pytest

from knowledge.case_replay import CaseReplayRecord, ReplayAgentBinding
from learning.experiment import (
    ExperimentContract,
    ExperimentMeasurement,
    ExperimentResult,
    MetricDirection,
    MetricGuardrail,
)
from learning.models import ChangeKind, LearningSource, MeasuredFailure, MetricValue
from learning.promotion import PromotionGate, PromotionStatus
from learning.semantic_self_healing import (
    ComponentDependency,
    ComponentDependencyGraph,
    ComponentNode,
    DiagnosisRule,
    DiagnosisStatus,
    RepairReadinessStatus,
    RevalidationMode,
    RootCauseCategory,
    SemanticFailureDiagnoser,
    SemanticSelfHealingGate,
    plan_revalidation,
    repair_candidate_from_diagnosis,
    validation_evidence_from_replays,
)

A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64
BASE_SHA = "1" * 40
REPAIR_SHA = "2" * 40


def failure(*, case_id: str = "CASE-1", code: str = "unsupported_conclusion") -> MeasuredFailure:
    return MeasuredFailure(
        failure_id=f"MF-{case_id}",
        source=LearningSource.REASONING_KQM,
        corpus_id="reasoning-gold",
        corpus_version="1.0.0",
        split="development",
        evaluator_version="reasoning-kqm-1",
        source_sha="3" * 40,
        case_id=case_id,
        code=code,
        expected="abstain",
        actual="conclusion",
        result_digest=A,
        report_digest=B,
    )


def diagnoser() -> SemanticFailureDiagnoser:
    return SemanticFailureDiagnoser(
        (
            DiagnosisRule(
                rule_id="DXR-REASONING-UNSUPPORTED",
                source=LearningSource.REASONING_KQM,
                failure_code="unsupported_conclusion",
                root_cause=RootCauseCategory.REASONING,
                target_component="reasoning.engine",
                rationale="unsupported conclusions originate in reasoning support validation",
            ),
        )
    )


def graph(*, complete: bool = True) -> ComponentDependencyGraph:
    return ComponentDependencyGraph(
        graph_version="1.0.0",
        nodes=(
            ComponentNode(
                component_id="extraction.engine",
                validators=("extraction_kqm:development",),
            ),
            ComponentNode(
                component_id="reasoning.engine",
                validators=("reasoning_kqm:development", "case_replay"),
            ),
            ComponentNode(
                component_id="renderer.reasoning",
                validators=("renderer_contract",),
            ),
        ),
        dependencies=(
            ComponentDependency(
                upstream="reasoning.engine",
                downstream="renderer.reasoning",
            ),
        ),
        complete=complete,
        completeness_evidence_digest=C if complete else None,
    )


def replay(
    git_commit: str,
    *,
    contract_sha256: str = A,
    graph_sha256: str = C,
) -> CaseReplayRecord:
    return CaseReplayRecord(
        case_key="CASE-1",
        snapshot_id="SNAP-1",
        manifest_sha256=A,
        source_sha256=(("doc-1", B),),
        pipeline_version="pipeline-1.0.0",
        graph_sha256=graph_sha256,
        agent_bindings=(
            ReplayAgentBinding(
                agent_id="reasoner",
                agent_version="1.0.0",
                contract_sha256=contract_sha256,
            ),
        ),
        renderer_version="renderer-1.0.0",
        git_commit=git_commit,
    )


def candidate_and_plan():
    measured = failure()
    diagnosis = diagnoser().diagnose(measured)
    plan = plan_revalidation(diagnosis, graph())
    candidate = repair_candidate_from_diagnosis(
        measured,
        diagnosis,
        change_kind=ChangeKind.PROMPT,
        hypothesis="require explicit evidence support before emitting a conclusion",
        success_criteria=("unsupported_conclusion_rate=0",),
    )
    return measured, diagnosis, candidate, plan


def experiment_for(candidate) -> ExperimentContract:
    return ExperimentContract(
        experiment_id="EXP-P6-1",
        candidate_digest=candidate.digest(),
        target_component=candidate.target_component,
        baseline_revision=BASE_SHA,
        candidate_revision=REPAIR_SHA,
        sandbox_id="sandbox-p6",
        allowed_splits=("development", "validation"),
        guardrails=(
            MetricGuardrail(
                name="decision_accuracy",
                direction=MetricDirection.HIGHER_IS_BETTER,
                max_regression=0.0,
            ),
        ),
        max_runs=2,
    )


def eligible_promotion(contract: ExperimentContract):
    result = ExperimentResult(
        contract_digest=contract.digest(),
        baseline=ExperimentMeasurement(
            revision=BASE_SHA,
            metrics=(MetricValue("decision_accuracy", 0.8),),
        ),
        candidate=ExperimentMeasurement(
            revision=REPAIR_SHA,
            metrics=(MetricValue("decision_accuracy", 0.9),),
        ),
        run_count=1,
    )
    decision = PromotionGate().evaluate(contract, result)
    assert decision.status is PromotionStatus.ELIGIBLE_FOR_PROMOTION
    return decision


def valid_evidence(candidate, plan):
    return validation_evidence_from_replays(
        candidate,
        plan,
        baseline_sha=BASE_SHA,
        repair_sha=REPAIR_SHA,
        baseline_replay=replay(BASE_SHA),
        repair_replay=replay(REPAIR_SHA, contract_sha256=D),
        expected_replay_drift_fields=("agent_bindings", "git_commit"),
        kqm_result_digest=C,
        kqm_report_digest=D,
        executed_validators=plan.validators,
        passed_validators=plan.validators,
    )


def test_semantic_diagnosis_is_bound_to_measured_failure_and_evidence() -> None:
    measured = failure()
    diagnosis = diagnoser().diagnose(measured, additional_evidence_digests=(C,))

    assert diagnosis.status is DiagnosisStatus.DIAGNOSED
    assert diagnosis.root_cause is RootCauseCategory.REASONING
    assert diagnosis.target_component == "reasoning.engine"
    assert diagnosis.failure_digest == measured.digest()
    assert set(diagnosis.evidence_digests) == {A, B, C}


def test_unknown_failure_abstains_instead_of_guessing_root_cause() -> None:
    diagnosis = diagnoser().diagnose(failure(code="novel_failure"))

    assert diagnosis.status is DiagnosisStatus.INCONCLUSIVE
    assert diagnosis.root_cause is RootCauseCategory.UNKNOWN
    assert diagnosis.target_component is None
    assert diagnosis.rule_id is None


def test_duplicate_or_ambiguous_diagnosis_rules_are_rejected() -> None:
    rule = DiagnosisRule(
        rule_id="R1",
        source=LearningSource.REASONING_KQM,
        failure_code="unsupported_conclusion",
        root_cause=RootCauseCategory.REASONING,
        target_component="reasoning.engine",
        rationale="first mapping",
    )
    duplicate_key = replace(rule, rule_id="R2", rationale="second mapping")

    with pytest.raises(ValueError, match="unique by source and failure code"):
        SemanticFailureDiagnoser((rule, duplicate_key))


def test_complete_graph_produces_true_selective_downstream_plan() -> None:
    diagnosis = diagnoser().diagnose(failure())
    plan = plan_revalidation(diagnosis, graph(complete=True))

    assert plan.mode is RevalidationMode.SELECTIVE
    assert plan.changed_component == "reasoning.engine"
    assert plan.impacted_components == ("reasoning.engine", "renderer.reasoning")
    assert "extraction.engine" not in plan.impacted_components
    assert set(plan.validators) == {
        "case_replay",
        "reasoning_kqm:development",
        "renderer_contract",
    }


def test_incomplete_graph_forces_broad_revalidation() -> None:
    diagnosis = diagnoser().diagnose(failure())
    plan = plan_revalidation(diagnosis, graph(complete=False))

    assert plan.mode is RevalidationMode.BROAD_REVALIDATION_REQUIRED
    assert set(plan.impacted_components) == {
        "extraction.engine",
        "reasoning.engine",
        "renderer.reasoning",
    }
    assert "extraction_kqm:development" in plan.validators


def test_inconclusive_diagnosis_forces_broad_revalidation() -> None:
    diagnosis = diagnoser().diagnose(failure(code="unknown-code"))
    plan = plan_revalidation(diagnosis, graph(complete=True))

    assert plan.mode is RevalidationMode.BROAD_REVALIDATION_REQUIRED
    assert plan.changed_component is None
    assert set(plan.impacted_components) == set(graph().component_ids())


def test_dependency_graph_rejects_cycles_and_unknown_components() -> None:
    nodes = (
        ComponentNode("a", ("validate-a",)),
        ComponentNode("b", ("validate-b",)),
    )
    with pytest.raises(ValueError, match="acyclic"):
        ComponentDependencyGraph(
            graph_version="1",
            nodes=nodes,
            dependencies=(ComponentDependency("a", "b"), ComponentDependency("b", "a")),
            complete=True,
            completeness_evidence_digest=A,
        )

    with pytest.raises(ValueError, match="unknown component"):
        ComponentDependencyGraph(
            graph_version="1",
            nodes=nodes,
            dependencies=(ComponentDependency("a", "missing"),),
            complete=True,
            completeness_evidence_digest=A,
        )


def test_complete_graph_requires_completeness_evidence() -> None:
    with pytest.raises(ValueError, match="completeness evidence"):
        ComponentDependencyGraph(
            graph_version="1",
            nodes=(ComponentNode("a", ("validate-a",)),),
            dependencies=(),
            complete=True,
        )


def test_repair_candidate_reuses_p4_contract_and_rejects_diagnosis_mismatch() -> None:
    first = failure(case_id="CASE-1")
    second = failure(case_id="CASE-2")
    diagnosis = diagnoser().diagnose(first)

    candidate = repair_candidate_from_diagnosis(
        first,
        diagnosis,
        change_kind=ChangeKind.RULE,
        hypothesis="reject unsupported conclusions",
        success_criteria=("unsafe_conclusion_rate=0",),
    )
    assert candidate.source_failure_digest == first.digest()
    assert candidate.target_component == "reasoning.engine"

    with pytest.raises(ValueError, match="not bound to this measured failure"):
        repair_candidate_from_diagnosis(
            second,
            diagnosis,
            change_kind=ChangeKind.RULE,
            hypothesis="wrong binding",
            success_criteria=("unsafe_conclusion_rate=0",),
        )


def test_fresh_sha_validation_rejects_same_revision() -> None:
    _, _, candidate, plan = candidate_and_plan()

    with pytest.raises(ValueError, match="fresh SHA"):
        validation_evidence_from_replays(
            candidate,
            plan,
            baseline_sha=BASE_SHA,
            repair_sha=BASE_SHA,
            baseline_replay=replay(BASE_SHA),
            repair_replay=replay(BASE_SHA),
            expected_replay_drift_fields=(),
            kqm_result_digest=C,
            kqm_report_digest=D,
            executed_validators=plan.validators,
            passed_validators=plan.validators,
        )


def test_fresh_sha_validation_rejects_unexpected_replay_drift() -> None:
    _, _, candidate, plan = candidate_and_plan()

    with pytest.raises(ValueError, match="declared repair drift"):
        validation_evidence_from_replays(
            candidate,
            plan,
            baseline_sha=BASE_SHA,
            repair_sha=REPAIR_SHA,
            baseline_replay=replay(BASE_SHA),
            repair_replay=replay(REPAIR_SHA, contract_sha256=D, graph_sha256=D),
            expected_replay_drift_fields=("agent_bindings", "git_commit"),
            kqm_result_digest=C,
            kqm_report_digest=D,
            executed_validators=plan.validators,
            passed_validators=plan.validators,
        )


def test_validation_evidence_requires_all_planned_validators_to_execute() -> None:
    _, _, candidate, plan = candidate_and_plan()

    with pytest.raises(ValueError, match="not all planned validators"):
        validation_evidence_from_replays(
            candidate,
            plan,
            baseline_sha=BASE_SHA,
            repair_sha=REPAIR_SHA,
            baseline_replay=replay(BASE_SHA),
            repair_replay=replay(REPAIR_SHA, contract_sha256=D),
            expected_replay_drift_fields=("agent_bindings", "git_commit"),
            kqm_result_digest=C,
            kqm_report_digest=D,
            executed_validators=(plan.validators[0],),
            passed_validators=(plan.validators[0],),
        )


def test_semantic_self_healing_gate_requires_existing_p4_promotion() -> None:
    _, _, candidate, plan = candidate_and_plan()
    contract = experiment_for(candidate)
    eligible = eligible_promotion(contract)
    evidence = valid_evidence(candidate, plan)

    ready = SemanticSelfHealingGate().evaluate(
        candidate,
        contract,
        eligible,
        plan,
        evidence,
    )
    assert ready.status is RepairReadinessStatus.READY_FOR_EXISTING_PROMOTION

    rejected_promotion = replace(
        eligible,
        status=PromotionStatus.REJECTED,
        reason="guardrail regression",
    )
    rejected = SemanticSelfHealingGate().evaluate(
        candidate,
        contract,
        rejected_promotion,
        plan,
        evidence,
    )
    assert rejected.status is RepairReadinessStatus.REJECTED
    assert "P4 PromotionGate" in rejected.reason


def test_semantic_self_healing_gate_rejects_missing_planned_pass() -> None:
    _, _, candidate, plan = candidate_and_plan()
    contract = experiment_for(candidate)
    promotion = eligible_promotion(contract)
    evidence = valid_evidence(candidate, plan)
    failed_validator = plan.validators[-1]
    degraded_evidence = replace(
        evidence,
        passed_validators=tuple(
            validator for validator in evidence.passed_validators if validator != failed_validator
        ),
    )

    decision = SemanticSelfHealingGate().evaluate(
        candidate,
        contract,
        promotion,
        plan,
        degraded_evidence,
    )
    assert decision.status is RepairReadinessStatus.REJECTED
    assert "did not pass" in decision.reason


def test_p6_cannot_use_locked_evaluation_as_repair_experiment_input() -> None:
    _, _, candidate, _ = candidate_and_plan()

    with pytest.raises(ValueError, match="development/validation"):
        ExperimentContract(
            experiment_id="EXP-LOCKED",
            candidate_digest=candidate.digest(),
            target_component=candidate.target_component,
            baseline_revision=BASE_SHA,
            candidate_revision=REPAIR_SHA,
            sandbox_id="sandbox-p6",
            allowed_splits=("locked_evaluation",),
            guardrails=(
                MetricGuardrail(
                    name="decision_accuracy",
                    direction=MetricDirection.HIGHER_IS_BETTER,
                ),
            ),
            max_runs=1,
        )
