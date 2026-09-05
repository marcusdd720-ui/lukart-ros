"""Registry for the post-P7 production validation and certification program."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProgramPriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    RELEASE = "RELEASE"


class GateKind(StrEnum):
    EXTERNAL_REVIEW = "external_review"
    IMPLEMENTATION = "implementation"
    MEASUREMENT = "measurement"
    CERTIFICATION = "certification"
    VALIDATION = "validation"
    PRIVACY = "privacy"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class ProgramStep:
    number: int
    name: str
    priority: ProgramPriority
    objective: str
    gate_kind: GateKind
    evidence_kind: str
    required_checks: tuple[str, ...]


PROGRAM_STEPS: tuple[ProgramStep, ...] = (
    ProgramStep(
        1,
        "Extraction Gold Corpus review/acceptance and freeze",
        ProgramPriority.P0,
        "Freeze a trustworthy extraction benchmark after the selected profile accepts it.",
        GateKind.EXTERNAL_REVIEW,
        "independent_extraction_corpus_review",
        (),
    ),
    ProgramStep(
        2,
        "ReferenceFactAgent improvement",
        ProgramPriority.P0,
        "Improve precision, recall, F1, and critical recall on development/validation only.",
        GateKind.IMPLEMENTATION,
        "reference_fact_agent_improvement",
        (
            "agent_version_changed",
            "development_metrics_recorded",
            "validation_metrics_recorded",
            "locked_evaluation_untouched",
        ),
    ),
    ProgramStep(
        3,
        "Extraction KQM certification attempt",
        ProgramPriority.P0,
        "Measure the candidate extractor and issue a certification decision.",
        GateKind.CERTIFICATION,
        "extraction_certification",
        (
            "frozen_extraction_corpus_bound",
            "thresholds_evaluated",
            "certification_decision_recorded",
        ),
    ),
    ProgramStep(
        4,
        "Reasoning Gold Corpus v2",
        ProgramPriority.P0,
        "Build a broader and harder reasoning benchmark candidate.",
        GateKind.IMPLEMENTATION,
        "reasoning_gold_v2_candidate",
        (
            "reasoning_corpus_v2_created",
            "development_split_present",
            "validation_split_present",
            "locked_split_sealed",
        ),
    ),
    ProgramStep(
        5,
        "Review/acceptance and freeze Reasoning Corpus",
        ProgramPriority.P0,
        "Review, accept under the selected certification profile, and freeze the benchmark.",
        GateKind.EXTERNAL_REVIEW,
        "independent_reasoning_corpus_review",
        (),
    ),
    ProgramStep(
        6,
        "Reasoning Engine KQM certification",
        ProgramPriority.P0,
        "Measure reasoning correctness, abstention, and contradiction handling.",
        GateKind.CERTIFICATION,
        "reasoning_certification",
        (
            "frozen_reasoning_corpus_bound",
            "reasoning_metrics_recorded",
            "abstention_measured",
            "contradiction_handling_measured",
            "certification_decision_recorded",
        ),
    ),
    ProgramStep(
        7,
        "End-to-End Gold Cases",
        ProgramPriority.P0,
        "Measure the complete product path on versioned Gold Cases.",
        GateKind.MEASUREMENT,
        "end_to_end_gold_measurement",
        (
            "gold_cases_versioned",
            "full_pipeline_executed",
            "evidence_traceability_verified",
            "product_kqm_recorded",
        ),
    ),
    ProgramStep(
        8,
        "Agent Certification Program",
        ProgramPriority.P1,
        "Certify controlled agents against explicit capability-specific benchmarks.",
        GateKind.CERTIFICATION,
        "agent_certification_bundle",
        (
            "agent_benchmarks_versioned",
            "certification_decisions_recorded",
            "router_eligibility_updated",
        ),
    ),
    ProgramStep(
        9,
        "Adversarial Gold Cases",
        ProgramPriority.P1,
        "Stress evidence, contradiction, abstention, and adversarial verification behavior.",
        GateKind.MEASUREMENT,
        "adversarial_gold_measurement",
        (
            "adversarial_cases_versioned",
            "evidence_veto_tested",
            "abstention_tested",
            "unresolved_challenge_tested",
        ),
    ),
    ProgramStep(
        10,
        "Case Replay regression suite",
        ProgramPriority.P1,
        "Prove deterministic replay and classify expected versus unexpected drift.",
        GateKind.VALIDATION,
        "case_replay_regression",
        (
            "baseline_replay_recorded",
            "candidate_replay_recorded",
            "unexpected_drift_zero",
        ),
    ),
    ProgramStep(
        11,
        "Change Propagation stress tests",
        ProgramPriority.P1,
        "Validate downstream impact selection and broad fallback behavior.",
        GateKind.VALIDATION,
        "change_propagation_stress",
        (
            "complete_graph_selective_revalidation_tested",
            "incomplete_graph_broad_fallback_tested",
            "cycle_rejection_tested",
        ),
    ),
    ProgramStep(
        12,
        "Controlled Learning experiments",
        ProgramPriority.P1,
        "Exercise real measured P4-P7 improvement cycles without production mutation.",
        GateKind.MEASUREMENT,
        "controlled_learning_experiment",
        (
            "measured_failure_bound",
            "candidate_experiment_executed",
            "promotion_gate_applied",
            "production_mutation_absent",
        ),
    ),
    ProgramStep(
        13,
        "Model and strategy benchmark and routing",
        ProgramPriority.P2,
        "Benchmark interchangeable strategies and route only on measured capability.",
        GateKind.MEASUREMENT,
        "strategy_routing_benchmark",
        (
            "strategies_versioned",
            "same_gold_cases_used",
            "routing_policy_metric_bound",
            "locked_tuning_absent",
        ),
    ),
    ProgramStep(
        14,
        "Automatic candidate generation",
        ProgramPriority.P2,
        "Generate bounded improvement candidates without granting deployment authority.",
        GateKind.IMPLEMENTATION,
        "automatic_candidate_generation",
        (
            "candidate_generator_bounded",
            "provenance_bound",
            "deployment_authority_absent",
            "promotion_path_required",
        ),
    ),
    ProgramStep(
        15,
        "Local private-case pilot",
        ProgramPriority.P2,
        "Validate real cases locally without publishing private evidence or PII.",
        GateKind.PRIVACY,
        "local_private_case_attestation",
        (
            "local_only_execution_attested",
            "pii_not_committed",
            "private_evidence_not_committed",
            "pilot_results_recorded",
        ),
    ),
    ProgramStep(
        16,
        "Renderer and final report quality",
        ProgramPriority.P2,
        "Validate human-facing evidence, timeline, reasoning, and dossier quality.",
        GateKind.MEASUREMENT,
        "renderer_quality_measurement",
        (
            "json_renderer_measured",
            "markdown_renderer_measured",
            "dossier_traceability_measured",
            "human_review_recorded",
        ),
    ),
    ProgramStep(
        17,
        "Performance budgets and SLA",
        ProgramPriority.P3,
        "Measure runtime, model calls, cost units, memory, and declared service budgets.",
        GateKind.MEASUREMENT,
        "performance_budget_measurement",
        (
            "runtime_budget_measured",
            "memory_budget_measured",
            "model_call_budget_measured",
            "cost_budget_measured",
        ),
    ),
    ProgramStep(
        18,
        "Security and privacy hardening",
        ProgramPriority.P3,
        "Harden secrets, PII, sandbox, local-data boundaries, and auditability.",
        GateKind.PRIVACY,
        "security_privacy_hardening",
        (
            "pii_gate_passed",
            "secret_gate_passed",
            "local_data_boundary_passed",
            "dependency_boundary_passed",
            "auditability_reviewed",
        ),
    ),
    ProgramStep(
        19,
        "Release versioning and migration policy",
        ProgramPriority.P3,
        "Stabilize versioning and migration contracts for product artifacts.",
        GateKind.RELEASE,
        "release_versioning_migration",
        (
            "versioning_policy_defined",
            "migration_policy_defined",
            "schema_compatibility_tested",
            "rollback_policy_defined",
        ),
    ),
    ProgramStep(
        20,
        "LUKART v1 Release Candidate",
        ProgramPriority.RELEASE,
        "Issue the release-candidate decision only after all critical gates pass.",
        GateKind.RELEASE,
        "release_candidate_decision",
        (
            "steps_1_19_complete",
            "release_manifest_created",
            "release_gates_passed",
            "rc_decision_recorded",
        ),
    ),
)


def get_program_step(number: int) -> ProgramStep:
    for step in PROGRAM_STEPS:
        if step.number == number:
            return step
    raise ValueError(f"unknown production validation step: {number}")


def next_program_step(number: int) -> ProgramStep | None:
    for step in PROGRAM_STEPS:
        if step.number > number:
            return step
    return None
