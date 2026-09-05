import pytest

from knowledge.epistemic import KnowledgeStatus
from knowledge.models.action_plan import ActionPlan, PlanTask
from knowledge.models.case_model_projection import CaseModelProjection, ProjectedCognitiveRef
from knowledge.models.case_scope import (
    CaseReference,
    CaseScope,
    ReferenceAuthorization,
    ReferenceSet,
    ScopePolicy,
)
from knowledge.models.decision_model import DecisionModel, DecisionOption, DecisionStatus
from knowledge.models.document_binding import ArtifactRef, DocumentBinding
from knowledge.models.evidence_assessment import AssessmentState, EvidenceAssessment
from knowledge.models.problem_model import EvidenceNeed, ProblemModel
from knowledge.models.strategy_model import StrategyApproach, StrategyModel, StrategyStatus


def _scope() -> CaseScope:
    reference = CaseReference(
        reference_id="REF-1",
        reference_type="source_document",
        source_ref="source:document:v1",
        reason="bounded synthetic E2E source",
        authorization=ReferenceAuthorization.AUTHORIZED,
        integrity_sha256="a" * 64,
    )
    scope = CaseScope(
        case_id="CASE-E2E",
        owner="synthetic:owner",
        scope_policy=ScopePolicy(
            allowed_reference_types=frozenset({"source_document"}),
        ),
        reference_set=ReferenceSet(),
    )
    return scope.with_reference(reference)


def _build_chain() -> tuple[
    CaseScope,
    CaseModelProjection,
    ProblemModel,
    EvidenceAssessment,
    DecisionModel,
    StrategyModel,
    ActionPlan,
    DocumentBinding,
]:
    scope = _scope()
    cognitive_ref = ProjectedCognitiveRef(
        object_id="FACT-1",
        object_version="v1",
        case_reference_id="REF-1",
        epistemic_status=KnowledgeStatus.FACT,
        provenance_refs=("source:document:v1",),
        valid_time="2026-09-01",
        knowledge_time="2026-09-02",
    )
    case_model = CaseModelProjection.build(
        scope,
        object_refs=(cognitive_ref,),
        unresolved_items=("OPEN-1",),
        version=2,
    )
    problem = ProblemModel.build(
        "PROBLEM-1",
        case_model,
        "choose a safe next action",
        evidence_needs=(
            EvidenceNeed(
                proposition_ref="PROP-1",
                burden_ref="BURDEN-1",
                supporting_refs=("FACT-1",),
            ),
        ),
        open_questions=("OPEN-1",),
        version=3,
    )
    evidence = EvidenceAssessment.build(
        "ASSESS-1",
        problem,
        "PROP-1",
        support_refs=("FACT-1",),
        contradiction_refs=("CONTRA-1",),
        provenance_state=AssessmentState.SATISFIED,
        authenticity_state=AssessmentState.SATISFIED,
        relevance_state=AssessmentState.SATISFIED,
        completeness_state=AssessmentState.PARTIAL,
        strength_state=AssessmentState.PARTIAL,
        burden_ref="BURDEN-1",
        missing_evidence=("SOURCE-2",),
        limitations=("one material source remains unavailable",),
        version=4,
    )
    option = DecisionOption("OPT-A", "collect missing source before filing")
    decision = DecisionModel.build(
        "DECISION-1",
        problem,
        evidence_assessments=(evidence,),
        options=(option,),
        selected_option="OPT-A",
        rationale="partial evidence requires one bounded acquisition step",
        authority="human:reviewer",
        status=DecisionStatus.SELECTED,
        version=5,
    )
    approach = StrategyApproach("APP-A", "collect, verify, then communicate")
    strategy = StrategyModel.build(
        "STRATEGY-1",
        decision,
        objectives=("close the material evidence gap",),
        approach_options=(approach,),
        selected_approach="APP-A",
        evidence_actions=("obtain SOURCE-2",),
        fallback_paths=("request human review if SOURCE-2 remains unavailable",),
        rationale="the selected approach implements the authorized decision",
        status=StrategyStatus.SELECTED,
        version=6,
    )
    task = PlanTask(
        task_id="TASK-1",
        purpose="obtain and verify SOURCE-2",
        owner="human:case-owner",
        required_inputs=("SOURCE-2 request",),
        expected_output="verified SOURCE-2 or explicit unavailable result",
        completion_criteria=("result recorded with provenance",),
    )
    plan = ActionPlan.build(
        "PLAN-1",
        strategy,
        tasks=(task,),
        monitoring_hooks=("reassess evidence after TASK-1",),
        version=7,
    )
    binding = DocumentBinding(
        document_id="DOC-1",
        renderer_id="reasoning-markdown",
        renderer_version="renderer-v1",
        template_id="synthetic-e2e",
        template_version="v1",
        input_refs=(
            ArtifactRef("case_model", case_model.case_id, case_model.version, "digest-case"),
            ArtifactRef("problem", problem.problem_id, problem.version, "digest-problem"),
            ArtifactRef("evidence", evidence.assessment_id, evidence.version, "digest-evidence"),
            ArtifactRef("decision", decision.decision_id, decision.version, "digest-decision"),
            ArtifactRef("strategy", strategy.strategy_id, strategy.version, "digest-strategy"),
            ArtifactRef("plan", plan.plan_id, plan.version, "digest-plan"),
        ),
        source_digest="digest-render-input",
        generated_at="2026-09-05T04:40:00Z",
        communication_target="human-review",
        unresolved_refs=case_model.unresolved_items,
        contradiction_refs=evidence.contradiction_refs,
        limitation_refs=evidence.limitations,
    )
    return scope, case_model, problem, evidence, decision, strategy, plan, binding


def test_full_cognitive_chain_preserves_identity_versions_and_open_risks() -> None:
    scope, case_model, problem, evidence, decision, strategy, plan, binding = _build_chain()

    assert case_model.case_id == scope.case_id
    assert problem.case_model_version == case_model.version
    assert evidence.problem_version == problem.version
    assert decision.problem_version == problem.version
    assert decision.evidence_assessment_refs == (evidence.assessment_id,)
    assert strategy.decision_version == decision.version
    assert plan.strategy_version == strategy.version
    assert [(ref.artifact_id, ref.version) for ref in binding.input_refs] == [
        (case_model.case_id, 2),
        (problem.problem_id, 3),
        (evidence.assessment_id, 4),
        (decision.decision_id, 5),
        (strategy.strategy_id, 6),
        (plan.plan_id, 7),
    ]
    assert binding.unresolved_refs == ("OPEN-1",)
    assert binding.contradiction_refs == ("CONTRA-1",)
    assert binding.limitation_refs == ("one material source remains unavailable",)


def test_chain_does_not_mutate_upstream_epistemic_state() -> None:
    scope, case_model, problem, evidence, decision, strategy, plan, binding = _build_chain()

    assert scope.reference_set.references[0].authorization is ReferenceAuthorization.AUTHORIZED
    assert case_model.object_refs[0].epistemic_status is KnowledgeStatus.FACT
    assert problem.open_questions == ("OPEN-1",)
    assert evidence.completeness_state is AssessmentState.PARTIAL
    assert decision.status is DecisionStatus.SELECTED
    assert strategy.status is StrategyStatus.SELECTED
    assert plan.tasks[0].status.value == "pending"
    assert binding.communication_target == "human-review"


def test_abstention_blocks_strategy_selection_and_plan_execution() -> None:
    _, _, problem, evidence, _, _, _, _ = _build_chain()
    decision = DecisionModel.build(
        "DECISION-ABSTAIN",
        problem,
        evidence_assessments=(evidence,),
        rationale="material evidence is insufficient for a safe choice",
        status=DecisionStatus.ABSTAIN,
    )
    approach = StrategyApproach("UNSAFE", "proceed despite abstention")

    with pytest.raises(ValueError, match="ABSTAIN Decision"):
        StrategyModel.build(
            "STRATEGY-UNSAFE",
            decision,
            objectives=("proceed",),
            approach_options=(approach,),
            selected_approach="UNSAFE",
            rationale="unsafe override",
            status=StrategyStatus.SELECTED,
        )


def test_unauthorized_source_is_rejected_before_case_model_projection() -> None:
    scope = CaseScope(
        case_id="CASE-E2E",
        owner="synthetic:owner",
        scope_policy=ScopePolicy(
            allowed_reference_types=frozenset({"source_document"}),
            require_authorization=True,
        ),
        reference_set=ReferenceSet(),
    )
    pending = CaseReference(
        reference_id="REF-PENDING",
        reference_type="source_document",
        source_ref="source:pending",
        reason="not yet authorized",
        authorization=ReferenceAuthorization.PENDING,
    )

    with pytest.raises(ValueError, match="explicit authorization"):
        scope.with_reference(pending)
